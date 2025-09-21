"""
Main PR Review Agent implementation.

This module contains the main PRReviewAgent class that coordinates all components
to provide comprehensive pull request review functionality.
"""

import asyncio
import logging
from typing import Dict, List, Optional, Any, Union
from datetime import datetime
from .config import Config, config as global_config
from .providers import GitProviderBase, GitHubProvider, GitLabProvider, BitbucketProvider
from .analyzers.base import AnalysisEngine, AnalysisResult, AnalysisSummary
from .analyzers.security_analyzer import PythonSecurityAnalyzer
from .ai_engine import AIEngine, AIFeedback, AIReviewSummary
from .providers.base import Review, ReviewComment


class PRReviewAgent:
    """
    Main PR Review Agent class.

    This class coordinates all components to provide comprehensive
    pull request review functionality across multiple git platforms.
    """

    def __init__(self, config: Optional[Config] = None):
        """
        Initialize the PR Review Agent.

        Args:
            config: Configuration object (uses global config if not provided)
        """
        self.config = config or global_config
        self.logger = self._setup_logging()

        # Initialize components
        self.git_providers = self._initialize_git_providers()
        self.analysis_engine = self._initialize_analysis_engine()
        self.ai_engine = self._initialize_ai_engine()

    def _setup_logging(self) -> logging.Logger:
        """Set up logging for the agent."""
        logger = logging.getLogger("pr_review_agent")
        logger.setLevel(getattr(logging, self.config.log_level))

        if not logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            )
            handler.setFormatter(formatter)
            logger.addHandler(handler)

        return logger

    def _initialize_git_providers(self) -> Dict[str, GitProviderBase]:
        """Initialize git provider instances."""
        providers = {}

        for provider_config in self.config.git_providers:
            try:
                if provider_config.name == "github":
                    providers["github"] = GitHubProvider(provider_config)
                elif provider_config.name == "gitlab":
                    providers["gitlab"] = GitLabProvider(provider_config)
                elif provider_config.name == "bitbucket":
                    providers["bitbucket"] = BitbucketProvider(provider_config)
                else:
                    self.logger.warning(f"Unknown git provider: {provider_config.name}")
            except Exception as e:
                self.logger.error(f"Failed to initialize {provider_config.name} provider: {e}")

        return providers

    def _initialize_analysis_engine(self) -> AnalysisEngine:
        """Initialize the analysis engine with analyzers."""
        analyzers = []

        # Add security analyzer
        security_config = self.config.analysis.dict()
        security_config["enabled"] = self.config.analysis.enable_security_scan
        analyzers.append(PythonSecurityAnalyzer(security_config))

        # Add structure/style analyzer (AST-based)
        try:
            from .analyzers.structure_analyzer import StructureAnalyzer

            structure_config = self.config.analysis.dict()
            structure_config["enabled"] = True
            analyzers.append(StructureAnalyzer(structure_config))
        except Exception:
            # If it fails to import, continue without it
            pass

        # TODO: Add more analyzers (performance, style, complexity)
        # analyzers.append(PerformanceAnalyzer(performance_config))
        # analyzers.append(StyleAnalyzer(style_config))
        # analyzers.append(ComplexityAnalyzer(complexity_config))

        return AnalysisEngine(analyzers)

    def _initialize_ai_engine(self) -> AIEngine:
        """Initialize the AI engine."""
        return AIEngine(self.config.ai)

    async def review_pull_request(
        self,
        provider_name: str,
        owner: str,
        repo: str,
        pr_number: Union[int, str]
    ) -> Dict[str, Any]:
        """
        Review a pull request.

        Args:
            provider_name: Name of the git provider (github, gitlab, bitbucket)
            owner: Repository owner/organization
            repo: Repository name
            pr_number: Pull request/merge request number or ID

        Returns:
            Dictionary with review results
        """
        self.logger.info(f"Starting review for {provider_name}/{owner}/{repo}#{pr_number}")

        # Get the appropriate git provider
        provider = self.git_providers.get(provider_name)
        if not provider:
            raise ValueError(f"Git provider '{provider_name}' not configured")

        try:
            # Get pull request details
            pr = await provider.get_pull_request(owner, repo, pr_number)
            self.logger.info(f"Retrieved PR: {pr.title}")

            # Get file changes
            file_changes = await provider.get_pull_request_files(owner, repo, pr_number)
            self.logger.info(f"Found {len(file_changes)} changed files")

            # Analyze files
            analysis_results = await self._analyze_files(provider, file_changes, owner, repo, pr)
            self.logger.info(f"Analysis complete: {len(analysis_results)} issues found")

            # Generate AI feedback
            ai_feedback = await self._generate_ai_feedback(file_changes, analysis_results)
            self.logger.info(f"AI feedback generated: {len(ai_feedback)} suggestions")

            # Calculate overall score
            overall_score = self._calculate_overall_score(analysis_results, ai_feedback)

            # Create review
            review = await self._create_review(
                provider, owner, repo, pr_number,
                analysis_results, ai_feedback, overall_score
            )

            # Submit review only if enabled in configuration
            review_id = None
            if getattr(self.config, 'review', None) and \
               getattr(self.config.review, 'enable_summary_comment', True) and \
               getattr(self.config.review, 'post_reviews', False):
                try:
                    review_id = await provider.create_review(owner, repo, pr_number, review)
                    self.logger.info(f"Review submitted with ID: {review_id}")
                except Exception as e:
                    self.logger.warning(f"Failed to submit review: {e}")
                    review_id = "failed_to_submit"
            else:
                self.logger.info("Review creation disabled in configuration")

            return {
                "review_id": review_id,
                "pull_request": pr,
                "file_changes": file_changes,
                "analysis_results": analysis_results,
                "ai_feedback": ai_feedback,
                "overall_score": overall_score,
                "review": review
            }

        except Exception as e:
            self.logger.error(f"Review failed: {e}")
            raise

    async def _analyze_files(
        self,
        provider: GitProviderBase,
        file_changes: List[Dict[str, Any]],
        owner: str,
        repo: str,
        pr: Any
    ) -> List[AnalysisResult]:
        """
        Analyze changed files.

        Args:
            provider: Git provider instance
            file_changes: List of file changes
            owner: Repository owner
            repo: Repository name
            pr: Pull request object

        Returns:
            List of analysis results
        """
        analysis_results = []

        # Prepare files for analysis
        files_to_analyze = []
        for change in file_changes:
            # Skip deleted files
            if change.status == "removed":
                continue

            try:
                # Get file content
                if change.status == "added":
                    # For new files, get content from the PR
                    content = self._extract_content_from_patch(change.patch)
                else:
                    # For modified files, get content from target branch
                    content = await provider.get_file_content(
                        owner, repo, change.filename, pr.target_branch
                    )

                if content:
                    files_to_analyze.append({
                        "path": change.filename,
                        "content": content
                    })

            except Exception as e:
                self.logger.warning(f"Failed to get content for {change.filename}: {e}")
                continue

        # Run analysis
        if files_to_analyze:
            summary = await self.analysis_engine.analyze_files(files_to_analyze)
            analysis_results = []  # Convert summary results to list format

            # TODO: Convert AnalysisSummary to List[AnalysisResult]
            # This is a simplified version
            for file_path, issues in summary.issues_by_category.items():
                for i in range(issues):
                    analysis_results.append(AnalysisResult(
                        file_path=file_path,
                        severity="warning",
                        category="general",
                        message=f"Analysis issue {i+1} in {file_path}"
                    ))

        return analysis_results

    async def _generate_ai_feedback(
        self,
        file_changes: List[Dict[str, Any]],
        analysis_results: List[AnalysisResult]
    ) -> List[AIFeedback]:
        """
        Generate AI feedback for file changes.

        Args:
            file_changes: List of file changes
            analysis_results: Results from static analysis

        Returns:
            List of AI feedback objects
        """
        ai_feedback = []

        # Generate feedback for each changed file
        for change in file_changes:
            if change.status == "removed":
                continue

            try:
                # Extract code content from patch
                code_content = self._extract_content_from_patch(change.patch)
                if not code_content:
                    continue

                # Get AI feedback
                feedback = await self.ai_engine.generate_feedback(
                    code_content,
                    change.filename,
                    context={
                        "change_type": change.status,
                        "additions": change.additions,
                        "deletions": change.deletions
                    }
                )

                ai_feedback.extend(feedback)

            except Exception as e:
                self.logger.warning(f"Failed to generate AI feedback for {change.filename}: {e}")
                continue

        return ai_feedback

    def _extract_content_from_patch(self, patch: Optional[str]) -> str:
        """
        Extract code content from a patch.

        Args:
            patch: Git diff patch content

        Returns:
            Extracted code content
        """
        if not patch:
            return ""

        lines = patch.split('\n')
        code_lines = []

        for line in lines:
            # Skip diff headers and metadata
            if line.startswith('diff --git') or line.startswith('index ') or \
               line.startswith('---') or line.startswith('+++'):
                continue

            # Extract added lines (starting with +)
            if line.startswith('+') and not line.startswith('+++'):
                code_lines.append(line[1:])  # Remove the + prefix

        return '\n'.join(code_lines)

    def _calculate_overall_score(
        self,
        analysis_results: List[AnalysisResult],
        ai_feedback: List[AIFeedback]
    ) -> float:
        """
        Calculate overall review score.

        Args:
            analysis_results: Results from static analysis
            ai_feedback: AI-generated feedback

        Returns:
            Overall score between 0.0 and 1.0
        """
        # Weight different types of feedback
        analysis_weight = 0.6
        ai_weight = 0.4

        # Calculate analysis score
        analysis_score = 1.0
        if analysis_results:
            severity_weights = {
                "info": 0.1,
                "warning": 0.3,
                "error": 0.7,
                "critical": 1.0
            }

            total_penalty = sum(
                severity_weights.get(result.severity, 0.5)
                for result in analysis_results
            )
            analysis_score = max(0.0, 1.0 - (total_penalty / len(analysis_results)))

        # Calculate AI score
        ai_score = 1.0
        if ai_feedback:
            severity_weights = {
                "info": 0.1,
                "warning": 0.3,
                "error": 0.7
            }

            total_penalty = sum(
                severity_weights.get(feedback.severity, 0.5) * feedback.confidence
                for feedback in ai_feedback
            )
            ai_score = max(0.0, 1.0 - (total_penalty / len(ai_feedback)))

        # Combine scores
        overall_score = (analysis_score * analysis_weight) + (ai_score * ai_weight)
        return round(overall_score, 3)

    async def _create_review(
        self,
        provider: GitProviderBase,
        owner: str,
        repo: str,
        pr_number: Union[int, str],
        analysis_results: List[AnalysisResult],
        ai_feedback: List[AIFeedback],
        overall_score: float
    ) -> Review:
        """
        Create a review object.

        Args:
            provider: Git provider instance
            owner: Repository owner
            repo: Repository name
            pr_number: Pull request number
            analysis_results: Static analysis results
            ai_feedback: AI feedback
            overall_score: Overall review score

        Returns:
            Review object
        """
        # Calculate grade based on score
        if overall_score >= 0.9:
            grade = "EXCELLENT"
        elif overall_score >= 0.7:
            grade = "GOOD"
        elif overall_score >= 0.5:
            grade = "NEEDS_IMPROVEMENT"
        else:
            grade = "POOR"

        # Create review body
        review_body = self._generate_review_body(
            analysis_results, ai_feedback, overall_score, grade
        )

        # Create review comments
        review_comments = self._generate_review_comments(
            analysis_results, ai_feedback
        )

        # Convert comment dictionaries to ReviewComment objects
        comments = []
        for comment_dict in review_comments:
            comment = ReviewComment(
                path=comment_dict["path"],
                line=comment_dict.get("line"),
                body=comment_dict["body"],
                side=comment_dict.get("side", "RIGHT")
            )
            comments.append(comment)

        return Review(
            body=review_body,
            comments=comments,
            score=overall_score,
            grade=grade,
            created_at=datetime.now()
        )

    def _generate_review_body(
        self,
        analysis_results: List[AnalysisResult],
        ai_feedback: List[AIFeedback],
        overall_score: float,
        grade: str
    ) -> str:
        """
        Generate the review body text.

        Args:
            analysis_results: Static analysis results
            ai_feedback: AI feedback
            overall_score: Overall review score
            grade: Review grade

        Returns:
            Review body text
        """
        body = f"""
# PR Review Agent Analysis

## Overall Assessment
- **Score**: {overall_score:.1f}/1.0
- **Grade**: {grade}
- **Issues Found**: {len(analysis_results) + len(ai_feedback)}

## Summary
This automated review analyzed the code changes for potential issues in security, performance, style, and maintainability.

## Key Findings
"""

        # Add analysis results summary
        if analysis_results:
            body += "\n### Static Analysis Issues\n"
            for result in analysis_results[:5]:  # Limit to top 5
                body += f"- **{result.severity.upper()}**: {result.message}\n"

        # Add AI feedback summary
        if ai_feedback:
            body += "\n### AI Suggestions\n"
            for feedback in ai_feedback[:5]:  # Limit to top 5
                body += f"- **{feedback.category.title()}**: {feedback.message}\n"

        body += """
## Recommendations
- Address critical and error-level issues first
- Consider the suggestions for improved code quality
- Test changes thoroughly before merging

---
*This review was generated automatically by PR Review Agent*
"""

        return body

    def _generate_review_comments(
        self,
        analysis_results: List[AnalysisResult],
        ai_feedback: List[AIFeedback]
    ) -> List[Dict[str, Any]]:
        """
        Generate review comments.

        Args:
            analysis_results: Static analysis results
            ai_feedback: AI feedback

        Returns:
            List of review comment dictionaries
        """
        comments = []

        # Convert analysis results to comments
        for result in analysis_results:
            comments.append({
                "path": result.file_path,
                "line": result.line,
                "body": f"**{result.severity.upper()}**: {result.message}\n\n{result.suggestion or ''}",
                "side": "RIGHT"
            })

        # Convert AI feedback to comments
        for feedback in ai_feedback:
            comments.append({
                "path": feedback.file_path,
                "line": feedback.line_start,
                "body": f"**{feedback.category.title()}**: {feedback.message}\n\nSuggestion: {feedback.suggestion}",
                "side": "RIGHT"
            })

        return comments

    async def close(self):
        """Close all components."""
        # Close git providers
        for provider in self.git_providers.values():
            await provider.close()

        # Close AI engine
        await self.ai_engine.close()

    async def __aenter__(self):
        """Async context manager entry."""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.close()


# Convenience function for quick usage
async def review_pr(
    provider_name: str,
    owner: str,
    repo: str,
    pr_number: Union[int, str],
    config: Optional[Config] = None
) -> Dict[str, Any]:
    """
    Convenience function to review a pull request.

    Args:
        provider_name: Name of the git provider
        owner: Repository owner
        repo: Repository name
        pr_number: Pull request number
        config: Optional configuration

    Returns:
        Review results dictionary
    """
    async with PRReviewAgent(config) as agent:
        return await agent.review_pull_request(provider_name, owner, repo, pr_number)


# Main entry point for CLI usage
def main():
    """Main entry point for CLI usage."""
    import argparse

    parser = argparse.ArgumentParser(description="PR Review Agent")
    parser.add_argument("--provider", required=True, help="Git provider (github, gitlab, bitbucket)")
    parser.add_argument("--owner", required=True, help="Repository owner")
    parser.add_argument("--repo", required=True, help="Repository name")
    parser.add_argument("--pr", required=True, help="Pull request number")
    parser.add_argument("--config", help="Configuration file path")

    args = parser.parse_args()

    # Load configuration
    config = Config.from_file("config.yaml")
    # Fill missing provider tokens from environment (allow GITHUB_TOKEN or PROVIDER_TOKEN)
    import os
    for provider in config.git_providers:
        if not provider.api_token:
            provider.api_token = os.getenv(f"{provider.name.upper()}_TOKEN") or os.getenv("GITHUB_TOKEN")

    # Run review
    async def run_review():
        async with PRReviewAgent(config) as agent:
            result = await agent.review_pull_request(
                args.provider, args.owner, args.repo, args.pr
            )

            print(f"Review completed! Score: {result['overall_score']:.3f}")
            print(f"Grade: {result['review'].grade}")
            print(f"Issues found: {len(result['analysis_results']) + len(result['ai_feedback'])}")

    asyncio.run(run_review())


if __name__ == "__main__":
    main()

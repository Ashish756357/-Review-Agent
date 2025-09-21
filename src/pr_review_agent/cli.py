"""
Command-line interface for PR Review Agent.

This module provides the CLI functionality for the PR Review Agent,
allowing users to review pull requests from the command line.
"""

import asyncio
import sys
from typing import Optional
from .config import Config
from .main import PRReviewAgent


def main():
    """Main CLI entry point."""
    import argparse

    parser = argparse.ArgumentParser(
        description="PR Review Agent - AI-powered pull request review",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Review a GitHub pull request
  pr-review-agent --provider github --owner myorg --repo myproject --pr 123

  # Review with custom configuration
  pr-review-agent --provider github --owner myorg --repo myproject --pr 123 --config config.yaml

  # Review a GitLab merge request
  pr-review-agent --provider gitlab --owner mygroup --repo myproject --pr 456

  # Review a Bitbucket pull request
  pr-review-agent --provider bitbucket --owner myworkspace --repo myproject --pr 789
        """
    )

    parser.add_argument(
        "--provider",
        required=True,
        choices=["github", "gitlab", "bitbucket"],
        help="Git provider (github, gitlab, bitbucket)"
    )

    parser.add_argument(
        "--owner",
        required=True,
        help="Repository owner/organization/workspace"
    )

    parser.add_argument(
        "--repo",
        required=True,
        help="Repository name"
    )

    parser.add_argument(
        "--pr",
        required=True,
        help="Pull request/merge request number or ID"
    )

    parser.add_argument(
        "--config",
        help="Path to configuration file (YAML format)"
    )

    parser.add_argument(
        "--output",
        choices=["text", "json", "markdown"],
        default="text",
        help="Output format (default: text)"
    )

    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Enable verbose logging"
    )

    parser.add_argument(
        "--version",
        action="version",
        version="PR Review Agent 0.1.0"
    )

    args = parser.parse_args()

    # Load configuration
    config = Config.from_env()
    if args.config:
        try:
            config = Config.from_file(args.config)
        except FileNotFoundError:
            print(f"Error: Configuration file not found: {args.config}")
            sys.exit(1)
        except Exception as e:
            print(f"Error: Failed to load configuration: {e}")
            sys.exit(1)

    # Set log level based on verbosity
    if args.verbose:
        import logging
        logging.getLogger("pr_review_agent").setLevel(logging.DEBUG)

    # Run the review
    async def run_review():
        try:
            async with PRReviewAgent(config) as agent:
                result = await agent.review_pull_request(
                    args.provider, args.owner, args.repo, args.pr
                )

                # Output results based on format
                if args.output == "json":
                    import json
                    print(json.dumps(result, indent=2, default=str))
                elif args.output == "markdown":
                    print(generate_markdown_report(result))
                else:
                    print(generate_text_report(result))

        except ValueError as e:
            print(f"Error: {e}")
            sys.exit(1)
        except Exception as e:
            print(f"Error: Review failed: {e}")
            if args.verbose:
                import traceback
                traceback.print_exc()
            sys.exit(1)

    asyncio.run(run_review())


def generate_text_report(result: dict) -> str:
    """Generate a text report of the review results."""
    lines = []

    # Header
    lines.append("=" * 60)
    lines.append("PR REVIEW AGENT - REVIEW RESULTS")
    lines.append("=" * 60)

    # Basic info
    pr = result["pull_request"]
    lines.append(f"Repository: {pr.author}/{pr.source_branch} -> {pr.target_branch}")
    lines.append(f"Title: {pr.title}")
    lines.append(f"Author: {pr.author}")
    lines.append(f"URL: {pr.url}")
    lines.append("")

    # Overall assessment
    lines.append("OVERALL ASSESSMENT")
    lines.append("-" * 20)
    lines.append(f"Score: {result['overall_score']:.3f}/1.0")
    lines.append(f"Grade: {result['review']['grade']}")
    lines.append(f"Issues Found: {len(result['analysis_results']) + len(result['ai_feedback'])}")
    lines.append("")

    # Analysis results
    if result["analysis_results"]:
        lines.append("STATIC ANALYSIS ISSUES")
        lines.append("-" * 25)
        for i, issue in enumerate(result["analysis_results"][:10], 1):
            lines.append(f"{i}. [{issue.get('severity', 'INFO').upper()}] {issue.get('message', 'N/A')}")
        if len(result["analysis_results"]) > 10:
            lines.append(f"... and {len(result['analysis_results']) - 10} more issues")
        lines.append("")

    # AI feedback
    if result["ai_feedback"]:
        lines.append("AI SUGGESTIONS")
        lines.append("-" * 15)
        for i, feedback in enumerate(result["ai_feedback"][:10], 1):
            lines.append(f"{i}. [{feedback.get('category', 'GENERAL').upper()}] {feedback.get('message', 'N/A')}")
        if len(result["ai_feedback"]) > 10:
            lines.append(f"... and {len(result['ai_feedback']) - 10} more suggestions")
        lines.append("")

    # File changes
    lines.append("FILE CHANGES")
    lines.append("-" * 12)
    for change in result["file_changes"][:5]:
        status = change.get("status", "modified").upper()
        additions = change.get("additions", 0)
        deletions = change.get("deletions", 0)
        lines.append(f"- {change.get('filename', 'unknown')} ({status}): +{additions} -{deletions}")
    if len(result["file_changes"]) > 5:
        lines.append(f"... and {len(result['file_changes']) - 5} more files")
    lines.append("")

    # Footer
    lines.append("=" * 60)
    lines.append("Review completed by PR Review Agent")

    return "\n".join(lines)


def generate_markdown_report(result: dict) -> str:
    """Generate a markdown report of the review results."""
    lines = []

    # Header
    lines.append("# PR Review Agent - Review Results")
    lines.append("")

    # Basic info
    pr = result["pull_request"]
    lines.append(f"**Repository:** {pr.author}/{pr.source_branch} → {pr.target_branch}")
    lines.append(f"**Title:** {pr.title}")
    lines.append(f"**Author:** {pr.author}")
    lines.append(f"**URL:** {pr.url}")
    lines.append("")

    # Overall assessment
    lines.append("## Overall Assessment")
    lines.append(f"- **Score:** {result['overall_score']:.3f}/1.0")
    lines.append(f"- **Grade:** {result['review']['grade']}")
    lines.append(f"- **Issues Found:** {len(result['analysis_results']) + len(result['ai_feedback'])}")
    lines.append("")

    # Analysis results
    if result["analysis_results"]:
        lines.append("## Static Analysis Issues")
        for issue in result["analysis_results"][:10]:
            severity = issue.get("severity", "info").upper()
            lines.append(f"- **{severity}:** {issue.get('message', 'N/A')}")
        if len(result["analysis_results"]) > 10:
            lines.append(f"- ... and {len(result['analysis_results']) - 10} more issues")
        lines.append("")

    # AI feedback
    if result["ai_feedback"]:
        lines.append("## AI Suggestions")
        for feedback in result["ai_feedback"][:10]:
            category = feedback.get("category", "general").title()
            lines.append(f"- **{category}:** {feedback.get('message', 'N/A')}")
        if len(result["ai_feedback"]) > 10:
            lines.append(f"- ... and {len(result['ai_feedback']) - 10} more suggestions")
        lines.append("")

    # File changes
    lines.append("## File Changes")
    for change in result["file_changes"]:
        status = change.get("status", "modified")
        additions = change.get("additions", 0)
        deletions = change.get("deletions", 0)
        lines.append(f"- `{change.get('filename', 'unknown')}` ({status}): +{additions} -{deletions}")
    lines.append("")

    # Footer
    lines.append("---")
    lines.append("*Review completed by PR Review Agent*")

    return "\n".join(lines)


if __name__ == "__main__":
    main()

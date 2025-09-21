"""
AI engine for intelligent code review.

This module provides AI-powered analysis and feedback generation for code changes,
using services like OpenAI and Anthropic to provide contextual suggestions.
"""

import asyncio
import json
import re
from typing import Dict, List, Optional, Any, Union
from dataclasses import dataclass
import httpx
from .config import AIConfig
from .analyzers.base import AnalysisResult, AnalysisSummary


@dataclass
class AIFeedback:
    """AI-generated feedback for code changes."""

    file_path: str
    line_start: Optional[int] = None
    line_end: Optional[int] = None
    category: str = "general"  # style, performance, security, maintainability
    severity: str = "info"  # info, warning, error
    message: str = ""
    suggestion: str = ""
    confidence: float = 0.5
    code_snippet: Optional[str] = None


@dataclass
class AIReviewSummary:
    """Summary of AI review results."""

    overall_score: float = 0.0
    overall_grade: str = "NEEDS_REVIEW"
    feedback_count: int = 0
    categories: Dict[str, int] = None
    key_issues: List[str] = None
    suggestions: List[str] = None

    def __post_init__(self):
        if self.categories is None:
            self.categories = {}
        if self.key_issues is None:
            self.key_issues = []
        if self.suggestions is None:
            self.suggestions = []


class AIProviderBase:
    """
    Base class for AI providers.

    All AI provider implementations must inherit from this class.
    """

    def __init__(self, config: AIConfig):
        self.config = config

    async def generate_feedback(
        self,
        code_content: str,
        file_path: str,
        context: Optional[Dict[str, Any]] = None
    ) -> List[AIFeedback]:
        """
        Generate AI feedback for code content.

        Args:
            code_content: The code content to analyze
            file_path: Path to the file
            context: Additional context for analysis

        Returns:
            List of AIFeedback objects
        """
        raise NotImplementedError

    async def generate_review_summary(
        self,
        analysis_results: List[AnalysisResult],
        file_changes: List[Dict[str, Any]]
    ) -> AIReviewSummary:
        """
        Generate a summary of the review.

        Args:
            analysis_results: Results from static analysis
            file_changes: Information about file changes

        Returns:
            AIReviewSummary object
        """
        raise NotImplementedError


class OpenAIProvider(AIProviderBase):
    """
    OpenAI API provider for AI-powered code review.
    """

    def __init__(self, config: AIConfig):
        super().__init__(config)
        self._client = None

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client."""
        if self._client is None:
            self._client = httpx.AsyncClient(
                base_url="https://api.openai.com/v1",
                headers={
                    "Authorization": f"Bearer {self.config.api_key}",
                    "Content-Type": "application/json"
                },
                timeout=60.0
            )
        return self._client

    async def generate_feedback(
        self,
        code_content: str,
        file_path: str,
        context: Optional[Dict[str, Any]] = None
    ) -> List[AIFeedback]:
        """
        Generate feedback using OpenAI API.
        """
        if not self.config.api_key:
            return []

        client = await self._get_client()

        # Prepare the prompt
        prompt = self._build_analysis_prompt(code_content, file_path, context)

        try:
            response = await client.post("/chat/completions", json={
                "model": self.config.model,
                "messages": [
                    {
                        "role": "system",
                        "content": "You are an expert code reviewer. Analyze the provided code and provide constructive feedback on style, performance, security, and maintainability. Focus on actionable suggestions."
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                "max_tokens": self.config.max_tokens,
                "temperature": self.config.temperature
            })

            if response.status_code != 200:
                return []

            data = response.json()
            feedback_text = data["choices"][0]["message"]["content"]

            return self._parse_feedback_response(feedback_text, file_path)

        except Exception:
            return []

    async def generate_review_summary(
        self,
        analysis_results: List[AnalysisResult],
        file_changes: List[Dict[str, Any]]
    ) -> AIReviewSummary:
        """
        Generate review summary using OpenAI API.
        """
        if not self.config.api_key:
            return AIReviewSummary()

        client = await self._get_client()

        # Prepare the summary prompt
        prompt = self._build_summary_prompt(analysis_results, file_changes)

        try:
            response = await client.post("/chat/completions", json={
                "model": self.config.model,
                "messages": [
                    {
                        "role": "system",
                        "content": "You are an expert code reviewer. Provide a comprehensive summary of the code review, highlighting key issues and overall quality assessment."
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                "max_tokens": self.config.max_tokens,
                "temperature": self.config.temperature
            })

            if response.status_code != 200:
                return AIReviewSummary()

            data = response.json()
            summary_text = data["choices"][0]["message"]["content"]

            return self._parse_summary_response(summary_text, analysis_results)

        except Exception:
            return AIReviewSummary()

    def _build_analysis_prompt(
        self,
        code_content: str,
        file_path: str,
        context: Optional[Dict[str, Any]]
    ) -> str:
        """Build the analysis prompt for OpenAI."""
        file_extension = file_path.split('.')[-1] if '.' in file_path else 'unknown'

        # Get context information
        change_type = context.get('change_type', 'modified') if context else 'modified'
        additions = context.get('additions', 0) if context else 0
        deletions = context.get('deletions', 0) if context else 0

        prompt = f"""
You are a senior software engineer and code reviewer. Please perform a comprehensive analysis of the following {file_extension.upper()} code.

FILE INFORMATION:
- File: {file_path}
- Type: {change_type}
- Lines of code: {len(code_content.splitlines())}
- Lines added: {additions}
- Lines deleted: {deletions}

CODE TO ANALYZE:
```python
{code_content}
```

Please provide detailed feedback in the following JSON format:
{{
    "feedback": [
        {{
            "category": "style|performance|security|maintainability|bug|documentation",
            "severity": "info|warning|error|critical",
            "line_start": 1,
            "line_end": 1,
            "message": "Detailed description of the issue or improvement opportunity",
            "suggestion": "Specific, actionable suggestion for improvement with code examples",
            "confidence": 0.8,
            "impact": "high|medium|low",
            "code_snippet": "relevant code snippet if applicable"
        }}
    ]
}}

ANALYSIS CRITERIA - Provide detailed feedback on:

1. **CODE STYLE & READABILITY:**
   - Consistent indentation and formatting
   - Meaningful variable and function names
   - Code organization and structure
   - Comments and documentation
   - Line length and complexity

2. **PERFORMANCE OPTIMIZATIONS:**
   - Algorithm efficiency
   - Memory usage patterns
   - I/O operations optimization
   - Database query efficiency
   - Caching opportunities

3. **SECURITY VULNERABILITIES:**
   - Input validation and sanitization
   - Authentication and authorization
   - Data protection and encryption
   - Injection attack prevention
   - Secure coding practices

4. **MAINTAINABILITY:**
   - Code modularity and reusability
   - Error handling patterns
   - Testing considerations
   - Configuration management
   - Dependencies and imports

5. **POTENTIAL BUGS:**
   - Logic errors and edge cases
   - Null pointer exceptions
   - Resource leaks
   - Race conditions
   - Type mismatches

6. **BEST PRACTICES:**
   - Language-specific conventions
   - Design patterns usage
   - Framework-specific guidelines
   - Industry standards compliance

Provide specific line numbers, concrete examples, and actionable suggestions. Be thorough but constructive.
"""

        return prompt

    def _build_summary_prompt(
        self,
        analysis_results: List[AnalysisResult],
        file_changes: List[Dict[str, Any]]
    ) -> str:
        """Build the summary prompt for OpenAI."""
        # Convert analysis results to detailed text
        results_text = ""
        severity_counts = {"info": 0, "warning": 0, "error": 0, "critical": 0}

        for result in analysis_results[:15]:  # Limit to first 15 results
            severity_counts[result.severity] = severity_counts.get(result.severity, 0) + 1
            results_text += f"- [{result.severity.upper()}] {result.message} ({result.category})\n"

        # Convert file changes to detailed text
        changes_text = ""
        total_additions = 0
        total_deletions = 0

        for change in file_changes[:10]:  # Limit to first 10 changes
            additions = change.get('additions', 0)
            deletions = change.get('deletions', 0)
            total_additions += additions
            total_deletions += deletions
            changes_text += f"- {change.get('filename', 'unknown')}: {change.get('status', 'modified')} "
            changes_text += f"(+{additions} -{deletions})\n"

        # Calculate overall statistics
        total_issues = len(analysis_results)
        critical_issues = severity_counts.get("critical", 0)
        error_issues = severity_counts.get("error", 0)
        warning_issues = severity_counts.get("warning", 0)

        prompt = f"""
You are a senior software engineer providing a comprehensive code review summary. Please analyze the following review data and provide a detailed assessment.

REVIEW STATISTICS:
- Total Issues Found: {total_issues}
- Critical Issues: {critical_issues}
- Error Issues: {error_issues}
- Warning Issues: {warning_issues}
- Lines Added: {total_additions}
- Lines Deleted: {total_deletions}
- Files Modified: {len(file_changes)}

DETAILED ANALYSIS RESULTS:
{results_text}

FILE CHANGES SUMMARY:
{changes_text}

Please provide a comprehensive summary in the following JSON format:
{{
    "overall_score": 0.85,
    "overall_grade": "GOOD",
    "key_issues": [
        "Most critical issue identified",
        "Second most important issue",
        "Third most important issue"
    ],
    "suggestions": [
        "Primary recommendation for improvement",
        "Secondary recommendation",
        "Additional improvement suggestions"
    ],
    "categories": {{
        "style": {severity_counts.get('style', 0)},
        "performance": {severity_counts.get('performance', 0)},
        "security": {severity_counts.get('security', 0)},
        "maintainability": {severity_counts.get('maintainability', 0)},
        "bug": {severity_counts.get('bug', 0)},
        "documentation": {severity_counts.get('documentation', 0)}
    }},
    "summary_text": "Detailed paragraph summarizing the overall code quality and key findings",
    "priority_actions": [
        "Most urgent action needed",
        "Second priority action",
        "Third priority action"
    ],
    "code_quality_score": 85,
    "maintainability_score": 78,
    "security_score": 92,
    "performance_score": 88
}}

ANALYSIS CRITERIA:
1. **Overall Assessment**: Consider the number and severity of issues found
2. **Code Quality**: Evaluate adherence to best practices and standards
3. **Maintainability**: Assess how easy the code is to understand and modify
4. **Security**: Check for potential security vulnerabilities
5. **Performance**: Identify performance bottlenecks and optimization opportunities

Provide specific, actionable insights and prioritize the most important findings.
"""

        return prompt

    def _parse_feedback_response(self, response_text: str, file_path: str) -> List[AIFeedback]:
        """Parse OpenAI response into AIFeedback objects."""
        feedback_list = []

        try:
            # Try to extract JSON from the response
            json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
            if json_match:
                data = json.loads(json_match.group())
                feedback_data = data.get("feedback", [])

                for item in feedback_data:
                    feedback = AIFeedback(
                        file_path=file_path,
                        line_start=item.get("line_start"),
                        line_end=item.get("line_end"),
                        category=item.get("category", "general"),
                        severity=item.get("severity", "info"),
                        message=item.get("message", ""),
                        suggestion=item.get("suggestion", ""),
                        confidence=item.get("confidence", 0.5)
                    )
                    feedback_list.append(feedback)

        except (json.JSONDecodeError, KeyError):
            # If JSON parsing fails, try to extract feedback manually
            lines = response_text.split('\n')
            current_feedback = None

            for line in lines:
                line = line.strip()
                if not line:
                    continue

                # Look for feedback patterns
                if any(keyword in line.lower() for keyword in
                      ['issue', 'problem', 'warning', 'error', 'suggestion']):
                    if current_feedback:
                        feedback_list.append(current_feedback)

                    current_feedback = AIFeedback(
                        file_path=file_path,
                        message=line,
                        category="general",
                        severity="info"
                    )

            if current_feedback:
                feedback_list.append(current_feedback)

        return feedback_list

    def _parse_summary_response(self, response_text: str, analysis_results: List[AnalysisResult]) -> AIReviewSummary:
        """Parse OpenAI response into AIReviewSummary object."""
        summary = AIReviewSummary()

        try:
            # Try to extract JSON from the response
            json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
            if json_match:
                data = json.loads(json_match.group())

                summary.overall_score = data.get("overall_score", 0.0)
                summary.overall_grade = data.get("overall_grade", "NEEDS_REVIEW")
                summary.key_issues = data.get("key_issues", [])
                summary.suggestions = data.get("suggestions", [])
                summary.categories = data.get("categories", {})

                # Count feedback by category
                for result in analysis_results:
                    category = result.category
                    summary.categories[category] = summary.categories.get(category, 0) + 1

                summary.feedback_count = len(analysis_results)

        except (json.JSONDecodeError, KeyError):
            # Fallback: calculate summary from analysis results
            summary.feedback_count = len(analysis_results)

            # Calculate categories
            for result in analysis_results:
                category = result.category
                summary.categories[category] = summary.categories.get(category, 0) + 1

            # Calculate score based on analysis results
            if analysis_results:
                severity_weights = {"info": 0.1, "warning": 0.3, "error": 0.7, "critical": 1.0}
                total_weight = sum(severity_weights.get(r.severity, 0.5) for r in analysis_results)
                summary.overall_score = max(0.0, 1.0 - (total_weight / len(analysis_results)))
            else:
                summary.overall_score = 1.0

            summary.overall_grade = "EXCELLENT" if summary.overall_score >= 0.9 else \
                                   "GOOD" if summary.overall_score >= 0.7 else \
                                   "NEEDS_IMPROVEMENT" if summary.overall_score >= 0.5 else "POOR"

        return summary


class AnthropicProvider(AIProviderBase):
    """
    Anthropic Claude API provider for AI-powered code review.
    """

    def __init__(self, config: AIConfig):
        super().__init__(config)
        self._client = None

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client."""
        if self._client is None:
            self._client = httpx.AsyncClient(
                base_url="https://api.anthropic.com/v1",
                headers={
                    "x-api-key": self.config.api_key,
                    "anthropic-version": "2023-06-01",
                    "Content-Type": "application/json"
                },
                timeout=60.0
            )
        return self._client

    async def generate_feedback(
        self,
        code_content: str,
        file_path: str,
        context: Optional[Dict[str, Any]] = None
    ) -> List[AIFeedback]:
        """
        Generate feedback using Anthropic Claude API.
        """
        if not self.config.api_key:
            return []

        client = await self._get_client()

        # Prepare the prompt
        prompt = self._build_analysis_prompt(code_content, file_path, context)

        try:
            response = await client.post("/messages", json={
                "model": self.config.model,
                "max_tokens": self.config.max_tokens,
                "temperature": self.config.temperature,
                "system": "You are an expert code reviewer. Analyze the provided code and provide constructive feedback on style, performance, security, and maintainability. Focus on actionable suggestions.",
                "messages": [
                    {
                        "role": "user",
                        "content": prompt
                    }
                ]
            })

            if response.status_code != 200:
                return []

            data = response.json()
            feedback_text = data["content"][0]["text"]

            return self._parse_feedback_response(feedback_text, file_path)

        except Exception:
            return []

    async def generate_review_summary(
        self,
        analysis_results: List[AnalysisResult],
        file_changes: List[Dict[str, Any]]
    ) -> AIReviewSummary:
        """
        Generate review summary using Anthropic Claude API.
        """
        if not self.config.api_key:
            return AIReviewSummary()

        client = await self._get_client()

        # Prepare the summary prompt
        prompt = self._build_summary_prompt(analysis_results, file_changes)

        try:
            response = await client.post("/messages", json={
                "model": self.config.model,
                "max_tokens": self.config.max_tokens,
                "temperature": self.config.temperature,
                "system": "You are an expert code reviewer. Provide a comprehensive summary of the code review, highlighting key issues and overall quality assessment.",
                "messages": [
                    {
                        "role": "user",
                        "content": prompt
                    }
                ]
            })

            if response.status_code != 200:
                return AIReviewSummary()

            data = response.json()
            summary_text = data["content"][0]["text"]

            return self._parse_summary_response(summary_text, analysis_results)

        except Exception:
            return AIReviewSummary()

    def _build_analysis_prompt(
        self,
        code_content: str,
        file_path: str,
        context: Optional[Dict[str, Any]]
    ) -> str:
        """Build the analysis prompt for Anthropic."""
        file_extension = file_path.split('.')[-1] if '.' in file_path else 'unknown'

        prompt = f"""
Please analyze the following {file_extension.upper()} code for potential issues and improvements:

File: {file_path}
Lines: {len(code_content.splitlines())}

Code:
```python
{code_content}
```

Please provide feedback in the following JSON format:
{{
    "feedback": [
        {{
            "category": "style|performance|security|maintainability",
            "severity": "info|warning|error",
            "line_start": 1,
            "line_end": 1,
            "message": "Brief description of the issue",
            "suggestion": "Specific suggestion for improvement",
            "confidence": 0.8
        }}
    ]
}}

Focus on:
1. Code style and readability
2. Performance optimizations
3. Security vulnerabilities
4. Maintainability and best practices
5. Potential bugs or logic issues

Provide specific, actionable feedback with line numbers when possible.
"""

        return prompt

    def _build_summary_prompt(
        self,
        analysis_results: List[AnalysisResult],
        file_changes: List[Dict[str, Any]]
    ) -> str:
        """Build the summary prompt for Anthropic."""
        # Convert analysis results to text
        results_text = ""
        for result in analysis_results[:10]:  # Limit to first 10 results
            results_text += f"- {result.severity.upper()}: {result.message} ({result.category})\n"

        changes_text = ""
        for change in file_changes[:5]:  # Limit to first 5 changes
            changes_text += f"- {change.get('filename', 'unknown')}: {change.get('status', 'modified')} "
            changes_text += f"(+{change.get('additions', 0)} -{change.get('deletions', 0)})\n"

        prompt = f"""
Please provide a comprehensive summary of this code review:

Analysis Results:
{results_text}

File Changes:
{changes_text}

Please provide a summary in the following JSON format:
{{
    "overall_score": 0.85,
    "overall_grade": "GOOD",
    "key_issues": ["Issue 1", "Issue 2"],
    "suggestions": ["Suggestion 1", "Suggestion 2"],
    "categories": {{"style": 2, "performance": 1, "security": 0}}
}}

Consider the severity and number of issues found, and provide an overall assessment of code quality.
"""

        return prompt

    def _parse_feedback_response(self, response_text: str, file_path: str) -> List[AIFeedback]:
        """Parse Anthropic response into AIFeedback objects."""
        # Use the same parsing logic as OpenAI
        return OpenAIProvider._parse_feedback_response("", response_text, file_path)

    def _parse_summary_response(self, response_text: str, analysis_results: List[AnalysisResult]) -> AIReviewSummary:
        """Parse Anthropic response into AIReviewSummary object."""
        # Use the same parsing logic as OpenAI
        return OpenAIProvider._parse_summary_response("", response_text, analysis_results)


class AIEngine:
    """
    Main AI engine that coordinates AI providers.

    This class manages AI providers and provides a unified interface
    for AI-powered code analysis and feedback generation.
    """

    def __init__(self, config: AIConfig):
        self.config = config
        self._providers = {}

    def get_provider(self, provider_name: str) -> Optional[AIProviderBase]:
        """
        Get AI provider by name.

        Args:
            provider_name: Name of the provider (openai, anthropic)

        Returns:
            AI provider instance or None if not available
        """
        if provider_name not in self._providers:
            if provider_name == "openai" and self.config.api_key:
                self._providers[provider_name] = OpenAIProvider(self.config)
            elif provider_name == "anthropic" and self.config.api_key:
                self._providers[provider_name] = AnthropicProvider(self.config)

        return self._providers.get(provider_name)

    async def generate_feedback(
        self,
        code_content: str,
        file_path: str,
        context: Optional[Dict[str, Any]] = None
    ) -> List[AIFeedback]:
        """
        Generate AI feedback for code content.

        Args:
            code_content: The code content to analyze
            file_path: Path to the file
            context: Additional context for analysis

        Returns:
            List of AIFeedback objects
        """
        if not self.config.enabled:
            return []

        provider = self.get_provider(self.config.provider)
        if not provider:
            return []

        try:
            return await provider.generate_feedback(code_content, file_path, context)
        except Exception:
            return []

    async def generate_review_summary(
        self,
        analysis_results: List[AnalysisResult],
        file_changes: List[Dict[str, Any]]
    ) -> AIReviewSummary:
        """
        Generate review summary.

        Args:
            analysis_results: Results from static analysis
            file_changes: Information about file changes

        Returns:
            AIReviewSummary object
        """
        if not self.config.enabled:
            return AIReviewSummary()

        provider = self.get_provider(self.config.provider)
        if not provider:
            return AIReviewSummary()

        try:
            return await provider.generate_review_summary(analysis_results, file_changes)
        except Exception:
            return AIReviewSummary()

    async def close(self):
        """Close all AI providers."""
        for provider in self._providers.values():
            if hasattr(provider, '_client') and provider._client:
                await provider._client.aclose()

"""
Base classes for code analysis.

This module defines the abstract base classes for different types of code analysis
including security, performance, style, and complexity analysis.
"""

import abc
import asyncio
from typing import Dict, List, Optional, Any, Union
from dataclasses import dataclass
from pathlib import Path


@dataclass
class AnalysisResult:
    """Result of code analysis."""

    file_path: str
    line: Optional[int] = None
    column: Optional[int] = None
    severity: str = "info"  # info, warning, error, critical
    category: str = "general"  # security, performance, style, complexity, etc.
    message: str = ""
    suggestion: Optional[str] = None
    code_snippet: Optional[str] = None
    impact: Optional[str] = None
    confidence: float = 0.5  # 0.0 to 1.0


@dataclass
class AnalysisSummary:
    """Summary of analysis results."""

    total_files: int = 0
    total_issues: int = 0
    issues_by_severity: Dict[str, int] = None
    issues_by_category: Dict[str, int] = None
    score: float = 0.0
    grade: str = "NEEDS_REVIEW"

    def __post_init__(self):
        if self.issues_by_severity is None:
            self.issues_by_severity = {}
        if self.issues_by_category is None:
            self.issues_by_category = {}


class CodeAnalyzerBase(abc.ABC):
    """
    Abstract base class for code analyzers.

    All code analyzers must inherit from this class and implement the analyze method.
    """

    def __init__(self, config: Dict[str, Any]):
        """
        Initialize the analyzer.

        Args:
            config: Configuration dictionary for the analyzer
        """
        self.config = config
        self.enabled = config.get("enabled", True)

    @abc.abstractmethod
    async def analyze(self, file_path: str, content: str, **kwargs) -> List[AnalysisResult]:
        """
        Analyze code content and return analysis results.

        Args:
            file_path: Path to the file being analyzed
            content: File content as string
            **kwargs: Additional arguments for analysis

        Returns:
            List of AnalysisResult objects
        """
        pass

    @abc.abstractmethod
    def get_supported_extensions(self) -> List[str]:
        """
        Get list of file extensions supported by this analyzer.

        Returns:
            List of supported file extensions (e.g., ['.py', '.js'])
        """
        pass

    def is_supported(self, file_path: str) -> bool:
        """
        Check if the analyzer supports the given file.

        Args:
            file_path: Path to the file

        Returns:
            True if the file is supported
        """
        if not self.enabled:
            return False

        path = Path(file_path)
        return path.suffix.lower() in self.get_supported_extensions()

    async def analyze_batch(self, files: List[Dict[str, str]]) -> List[AnalysisResult]:
        """
        Analyze multiple files in batch.

        Args:
            files: List of dictionaries with 'path' and 'content' keys

        Returns:
            List of AnalysisResult objects
        """
        results = []

        for file_info in files:
            if not self.is_supported(file_info["path"]):
                continue

            try:
                file_results = await self.analyze(
                    file_info["path"],
                    file_info["content"]
                )
                results.extend(file_results)
            except Exception as e:
                # Log error but continue with other files
                results.append(AnalysisResult(
                    file_path=file_info["path"],
                    severity="error",
                    category="analysis_error",
                    message=f"Analysis failed: {str(e)}",
                    suggestion="Check file format and try again"
                ))

        return results


class SecurityAnalyzerBase(CodeAnalyzerBase):
    """
    Base class for security analyzers.

    Security analyzers focus on identifying potential security vulnerabilities
    and security-related issues in code.
    """

    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.category = "security"


class PerformanceAnalyzerBase(CodeAnalyzerBase):
    """
    Base class for performance analyzers.

    Performance analyzers focus on identifying potential performance issues
    and optimization opportunities in code.
    """

    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.category = "performance"


class StyleAnalyzerBase(CodeAnalyzerBase):
    """
    Base class for style analyzers.

    Style analyzers focus on code style, formatting, and adherence to
    coding standards and best practices.
    """

    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.category = "style"


class ComplexityAnalyzerBase(CodeAnalyzerBase):
    """
    Base class for complexity analyzers.

    Complexity analyzers focus on measuring code complexity and identifying
    areas that may be difficult to maintain or understand.
    """

    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.category = "complexity"


class AnalysisEngine:
    """
    Main analysis engine that coordinates multiple analyzers.

    This class manages the execution of multiple code analyzers and
    aggregates their results into a comprehensive analysis report.
    """

    def __init__(self, analyzers: List[CodeAnalyzerBase]):
        """
        Initialize the analysis engine.

        Args:
            analyzers: List of analyzer instances
        """
        self.analyzers = analyzers

    async def analyze_files(self, files: List[Dict[str, str]]) -> AnalysisSummary:
        """
        Analyze multiple files using all configured analyzers.

        Args:
            files: List of dictionaries with 'path' and 'content' keys

        Returns:
            AnalysisSummary with aggregated results
        """
        all_results = []

        # Run all analyzers concurrently
        tasks = []
        for analyzer in self.analyzers:
            if analyzer.enabled:
                task = analyzer.analyze_batch(files)
                tasks.append(task)

        # Wait for all analysis tasks to complete
        if tasks:
            analyzer_results = await asyncio.gather(*tasks, return_exceptions=True)

            for results in analyzer_results:
                if isinstance(results, Exception):
                    # Handle analyzer errors
                    continue
                all_results.extend(results)

        # Aggregate results
        return self._aggregate_results(all_results, files)

    def _aggregate_results(
        self,
        results: List[AnalysisResult],
        files: List[Dict[str, str]]
    ) -> AnalysisSummary:
        """
        Aggregate analysis results into a summary.

        Args:
            results: List of analysis results
            files: List of analyzed files

        Returns:
            AnalysisSummary object
        """
        summary = AnalysisSummary()
        summary.total_files = len(files)
        summary.total_issues = len(results)

        # Count issues by severity
        severity_counts = {}
        category_counts = {}

        for result in results:
            # Count by severity
            severity_counts[result.severity] = severity_counts.get(result.severity, 0) + 1

            # Count by category
            category_counts[result.category] = category_counts.get(result.category, 0) + 1

        summary.issues_by_severity = severity_counts
        summary.issues_by_category = category_counts

        # Calculate score based on issues found
        summary.score = self._calculate_score(results, files)
        summary.grade = self._calculate_grade(summary.score)

        return summary

    def _calculate_score(self, results: List[AnalysisResult], files: List[Dict[str, str]]) -> float:
        """
        Calculate overall code quality score.

        Args:
            results: List of analysis results
            files: List of analyzed files

        Returns:
            Score between 0.0 and 1.0
        """
        if not files:
            return 1.0

        if not results:
            return 1.0

        # Weight different severity levels
        severity_weights = {
            "info": 0.1,
            "warning": 0.3,
            "error": 0.7,
            "critical": 1.0
        }

        total_penalty = 0
        max_penalty_per_file = 1.0

        # Group results by file
        file_results = {}
        for result in results:
            if result.file_path not in file_results:
                file_results[result.file_path] = []
            file_results[result.file_path].append(result)

        # Calculate penalty for each file
        for file_path, file_result_list in file_results.items():
            file_penalty = 0

            for result in file_result_list:
                weight = severity_weights.get(result.severity, 0.5)
                file_penalty += weight * (result.confidence or 0.5)

            # Cap penalty per file
            file_penalty = min(file_penalty, max_penalty_per_file)
            total_penalty += file_penalty

        # Calculate final score
        max_possible_penalty = len(files) * max_penalty_per_file
        score = max(0.0, 1.0 - (total_penalty / max_possible_penalty))

        return round(score, 3)

    def _calculate_grade(self, score: float) -> str:
        """
        Calculate grade based on score.

        Args:
            score: Quality score between 0.0 and 1.0

        Returns:
            Grade string
        """
        if score >= 0.9:
            return "EXCELLENT"
        elif score >= 0.7:
            return "GOOD"
        elif score >= 0.5:
            return "NEEDS_IMPROVEMENT"
        else:
            return "POOR"

    def add_analyzer(self, analyzer: CodeAnalyzerBase):
        """
        Add an analyzer to the engine.

        Args:
            analyzer: Analyzer instance to add
        """
        self.analyzers.append(analyzer)

    def remove_analyzer(self, analyzer_type: type):
        """
        Remove analyzers of a specific type.

        Args:
            analyzer_type: Type of analyzer to remove
        """
        self.analyzers = [
            analyzer for analyzer in self.analyzers
            if not isinstance(analyzer, analyzer_type)
        ]

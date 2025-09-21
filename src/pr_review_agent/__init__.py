"""
PR Review Agent - AI-powered pull request review agent for multiple git platforms.

This package provides a comprehensive solution for automated code review across
GitHub, GitLab, and Bitbucket platforms with AI-driven feedback and quality scoring.
"""

__version__ = "0.1.0"
__author__ = "PR Review Agent"
__description__ = "AI-powered pull request review agent"

from .config import Config
from .main import PRReviewAgent

__all__ = ["Config", "PRReviewAgent"]

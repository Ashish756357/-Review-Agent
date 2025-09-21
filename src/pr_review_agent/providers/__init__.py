"""
Git provider implementations.

This package contains implementations for different git hosting services
including GitHub, GitLab, and Bitbucket.
"""

from .base import (
    GitProviderBase, PullRequest, FileChange, ReviewComment, Review,
    GitProviderError, AuthenticationError, NotFoundError, RateLimitError
)
from .github import GitHubProvider
from .gitlab import GitLabProvider
from .bitbucket import BitbucketProvider

__all__ = [
    # Base classes
    "GitProviderBase",
    "PullRequest",
    "FileChange",
    "ReviewComment",
    "Review",
    "GitProviderError",
    "AuthenticationError",
    "NotFoundError",
    "RateLimitError",

    # Provider implementations
    "GitHubProvider",
    "GitLabProvider",
    "BitbucketProvider",
]

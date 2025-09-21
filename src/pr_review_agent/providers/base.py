"""
Base classes and interfaces for git providers.

This module defines the abstract base classes that all git provider implementations
must inherit from, ensuring consistent interfaces across different platforms.
"""

import abc
import asyncio
from typing import Dict, List, Optional, Any, Union
from datetime import datetime
from dataclasses import dataclass

from ..config import GitProviderConfig


@dataclass
class PullRequest:
    """Represents a pull request/merge request."""

    id: str
    number: int
    title: str
    description: str
    author: str
    source_branch: str
    target_branch: str
    url: str
    created_at: datetime
    updated_at: datetime
    state: str  # open, closed, merged
    draft: bool
    labels: List[str]
    assignees: List[str]
    reviewers: List[str]


@dataclass
class FileChange:
    """Represents a file change in a pull request."""

    filename: str
    status: str  # added, modified, deleted, renamed
    additions: int
    deletions: int
    patch: Optional[str] = None
    blob_url: Optional[str] = None
    raw_url: Optional[str] = None


@dataclass
class ReviewComment:
    """Represents a review comment."""

    id: Optional[str] = None
    path: str = ""
    line: Optional[int] = None
    side: str = "RIGHT"  # LEFT or RIGHT
    body: str = ""
    start_line: Optional[int] = None
    start_side: Optional[str] = None


@dataclass
class Review:
    """Represents a complete review."""

    id: Optional[str] = None
    body: str = ""
    comments: List[ReviewComment] = None
    score: Optional[float] = None
    grade: str = "NEEDS_REVIEW"  # EXCELLENT, GOOD, NEEDS_IMPROVEMENT, POOR
    created_at: Optional[datetime] = None

    def __post_init__(self):
        if self.comments is None:
            self.comments = []


class GitProviderError(Exception):
    """Base exception for git provider errors."""

    pass


class AuthenticationError(GitProviderError):
    """Raised when authentication fails."""

    pass


class NotFoundError(GitProviderError):
    """Raised when a resource is not found."""

    pass


class RateLimitError(GitProviderError):
    """Raised when rate limit is exceeded."""

    pass


class GitProviderBase(abc.ABC):
    """
    Abstract base class for git providers.

    All git provider implementations must inherit from this class and implement
    all abstract methods.
    """

    def __init__(self, config: GitProviderConfig):
        """
        Initialize the git provider.

        Args:
            config: Configuration for this git provider
        """
        self.config = config
        self._session = None

    @abc.abstractmethod
    async def authenticate(self) -> bool:
        """
        Authenticate with the git provider.

        Returns:
            True if authentication was successful

        Raises:
            AuthenticationError: If authentication fails
        """
        pass

    @abc.abstractmethod
    async def get_pull_request(self, owner: str, repo: str, pr_number: int) -> PullRequest:
        """
        Get a pull request by number.

        Args:
            owner: Repository owner/organization
            repo: Repository name
            pr_number: Pull request number

        Returns:
            PullRequest object

        Raises:
            NotFoundError: If PR is not found
        """
        pass

    @abc.abstractmethod
    async def get_pull_request_files(self, owner: str, repo: str, pr_number: int) -> List[FileChange]:
        """
        Get the files changed in a pull request.

        Args:
            owner: Repository owner/organization
            repo: Repository name
            pr_number: Pull request number

        Returns:
            List of FileChange objects

        Raises:
            NotFoundError: If PR is not found
        """
        pass

    @abc.abstractmethod
    async def get_file_content(self, owner: str, repo: str, path: str, ref: str) -> str:
        """
        Get the content of a file at a specific reference.

        Args:
            owner: Repository owner/organization
            repo: Repository name
            path: File path
            ref: Branch name or commit SHA

        Returns:
            File content as string

        Raises:
            NotFoundError: If file is not found
        """
        pass

    @abc.abstractmethod
    async def create_review(self, owner: str, repo: str, pr_number: int, review: Review) -> str:
        """
        Create a review for a pull request.

        Args:
            owner: Repository owner/organization
            repo: Repository name
            pr_number: Pull request number
            review: Review object

        Returns:
            Review ID

        Raises:
            GitProviderError: If review creation fails
        """
        pass

    @abc.abstractmethod
    async def create_review_comment(
        self,
        owner: str,
        repo: str,
        pr_number: int,
        comment: ReviewComment
    ) -> str:
        """
        Create a review comment on a pull request.

        Args:
            owner: Repository owner/organization
            repo: Repository name
            pr_number: Pull request number
            comment: ReviewComment object

        Returns:
            Comment ID

        Raises:
            GitProviderError: If comment creation fails
        """
        pass

    @abc.abstractmethod
    async def update_review_comment(
        self,
        owner: str,
        repo: str,
        pr_number: int,
        comment_id: str,
        comment: ReviewComment
    ) -> bool:
        """
        Update a review comment.

        Args:
            owner: Repository owner/organization
            repo: Repository name
            pr_number: Pull request number
            comment_id: Comment ID to update
            comment: Updated ReviewComment object

        Returns:
            True if update was successful

        Raises:
            GitProviderError: If comment update fails
        """
        pass

    @abc.abstractmethod
    async def delete_review_comment(
        self,
        owner: str,
        repo: str,
        pr_number: int,
        comment_id: str
    ) -> bool:
        """
        Delete a review comment.

        Args:
            owner: Repository owner/organization
            repo: Repository name
            pr_number: Pull request number
            comment_id: Comment ID to delete

        Returns:
            True if deletion was successful

        Raises:
            GitProviderError: If comment deletion fails
        """
        pass

    @abc.abstractmethod
    async def get_rate_limit_status(self) -> Dict[str, Union[int, datetime]]:
        """
        Get the current rate limit status.

        Returns:
            Dictionary with rate limit information including:
            - limit: Maximum requests per hour
            - remaining: Remaining requests
            - reset_time: When the limit resets
        """
        pass

    async def close(self):
        """Close any open connections."""
        if self._session:
            await self._session.close()
            self._session = None

    def __enter__(self):
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        asyncio.create_task(self.close())

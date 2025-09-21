"""
Bitbucket provider implementation.

This module provides integration with Bitbucket's REST API for pull request operations.
"""

import asyncio
from typing import Dict, List, Optional, Union, Any
from datetime import datetime, timedelta
import httpx
from .base import (
    GitProviderBase, PullRequest, FileChange, ReviewComment, Review,
    AuthenticationError, NotFoundError, RateLimitError, GitProviderError
)


class BitbucketProvider(GitProviderBase):
    """
    Bitbucket API provider implementation.

    Supports Bitbucket's REST API v2 for comprehensive pull request analysis
    and review operations.
    """

    def __init__(self, config):
        """Initialize Bitbucket provider."""
        super().__init__(config)
        self._client = None
        self._workspace = None

    async def authenticate(self) -> bool:
        """
        Authenticate with Bitbucket API.

        Returns:
            True if authentication was successful

        Raises:
            AuthenticationError: If authentication fails
        """
        try:
            auth = None
            if self.config.api_token:
                # Bitbucket uses app passwords or API tokens
                auth = (self.config.api_token, "")

            self._client = httpx.AsyncClient(
                base_url=self.config.base_url,
                auth=auth,
                headers={
                    "Accept": "application/json",
                    "User-Agent": "PR-Review-Agent/1.0"
                },
                timeout=30.0
            )

            # Test authentication
            response = await self._client.get("/user")
            if response.status_code == 401:
                raise AuthenticationError("Invalid Bitbucket credentials")
            elif response.status_code == 403:
                raise AuthenticationError("Bitbucket credentials lack required permissions")

            return True

        except httpx.RequestError as e:
            raise AuthenticationError(f"Failed to connect to Bitbucket: {e}")

    async def get_pull_request(self, owner: str, repo: str, pr_id: str) -> PullRequest:
        """
        Get a pull request from Bitbucket.

        Args:
            owner: Workspace/owner name
            repo: Repository name
            pr_id: Pull request ID

        Returns:
            PullRequest object

        Raises:
            NotFoundError: If PR is not found
        """
        if not self._client:
            raise AuthenticationError("Not authenticated")

        try:
            response = await self._client.get(f"/repositories/{owner}/{repo}/pullrequests/{pr_id}")

            if response.status_code == 404:
                raise NotFoundError(f"Pull request {owner}/{repo}/{pr_id} not found")
            elif response.status_code == 403:
                raise RateLimitError("Rate limit exceeded")

            response.raise_for_status()
            data = response.json()

            return PullRequest(
                id=str(data["id"]),
                number=int(pr_id),
                title=data["title"],
                description=data.get("description", ""),
                author=data["author"]["nickname"],
                source_branch=data["source"]["branch"]["name"],
                target_branch=data["destination"]["branch"]["name"],
                url=data["links"]["html"]["href"],
                created_at=datetime.fromisoformat(data["created_on"].replace('Z', '+00:00')),
                updated_at=datetime.fromisoformat(data["updated_on"].replace('Z', '+00:00')),
                state=data["state"],
                draft=False,  # Bitbucket doesn't have draft PRs
                labels=[],  # Bitbucket doesn't use labels like GitHub
                assignees=[],  # Bitbucket doesn't have assignees
                reviewers=[reviewer["nickname"] for reviewer in data.get("reviewers", [])]
            )

        except httpx.RequestError as e:
            raise GitProviderError(f"Failed to get pull request: {e}")

    async def get_pull_request_files(self, owner: str, repo: str, pr_id: str) -> List[FileChange]:
        """
        Get files changed in a Bitbucket pull request.

        Args:
            owner: Workspace/owner name
            repo: Repository name
            pr_id: Pull request ID

        Returns:
            List of FileChange objects

        Raises:
            NotFoundError: If PR is not found
        """
        if not self._client:
            raise AuthenticationError("Not authenticated")

        try:
            response = await self._client.get(f"/repositories/{owner}/{repo}/pullrequests/{pr_id}/diff")

            if response.status_code == 404:
                raise NotFoundError(f"Pull request {owner}/{repo}/{pr_id} not found")
            elif response.status_code == 403:
                raise RateLimitError("Rate limit exceeded")

            response.raise_for_status()
            diff_content = response.text

            # Parse the diff content to extract file changes
            files = []
            current_file = None

            for line in diff_content.split('\n'):
                if line.startswith('diff --git'):
                    if current_file:
                        files.append(current_file)

                    # Extract filename from diff line
                    parts = line.split()
                    if len(parts) >= 3:
                        filename = parts[2].replace('a/', '').replace('b/', '')
                        current_file = FileChange(
                            filename=filename,
                            status="modified",  # Will be updated based on content
                            additions=0,
                            deletions=0,
                            patch=None
                        )
                elif current_file and line.startswith('+++') or line.startswith('---'):
                    continue
                elif current_file and (line.startswith('++') or line.startswith('@@')):
                    continue
                elif current_file and line.startswith('+'):
                    current_file.additions += 1
                elif current_file and line.startswith('-'):
                    current_file.deletions += 1

            if current_file:
                files.append(current_file)

            return files

        except httpx.RequestError as e:
            raise GitProviderError(f"Failed to get pull request files: {e}")

    async def get_file_content(self, owner: str, repo: str, path: str, ref: str) -> str:
        """
        Get file content from Bitbucket.

        Args:
            owner: Workspace/owner name
            repo: Repository name
            path: File path
            ref: Branch name or commit SHA

        Returns:
            File content as string

        Raises:
            NotFoundError: If file is not found
        """
        if not self._client:
            raise AuthenticationError("Not authenticated")

        try:
            response = await self._client.get(
                f"/repositories/{owner}/{repo}/src/{ref}/{path}"
            )

            if response.status_code == 404:
                raise NotFoundError(f"File {path} not found in {owner}/{repo}")
            elif response.status_code == 403:
                raise RateLimitError("Rate limit exceeded")

            response.raise_for_status()
            return response.text

        except httpx.RequestError as e:
            raise GitProviderError(f"Failed to get file content: {e}")

    async def create_review(self, owner: str, repo: str, pr_id: str, review: Review) -> str:
        """
        Create a review on Bitbucket.

        Args:
            owner: Workspace/owner name
            repo: Repository name
            pr_id: Pull request ID
            review: Review object

        Returns:
            Review ID

        Raises:
            GitProviderError: If review creation fails
        """
        if not self._client:
            raise AuthenticationError("Not authenticated")

        try:
            # Map grade to Bitbucket approval status
            approval_map = {
                "EXCELLENT": True,
                "GOOD": True,
                "NEEDS_IMPROVEMENT": False,
                "POOR": False
            }

            review_data = {
                "type": "approval" if approval_map.get(review.grade, False) else "change",
                "title": "PR Review Agent Review",
                "message": review.body
            }

            response = await self._client.post(
                f"/repositories/{owner}/{repo}/pullrequests/{pr_id}/approve",
                json=review_data
            )

            if response.status_code == 403:
                raise RateLimitError("Rate limit exceeded")
            elif response.status_code == 404:
                raise NotFoundError(f"Pull request {owner}/{repo}/{pr_id} not found")
            elif response.status_code == 409:
                # Already approved or changed
                pass

            # Create comments for review feedback
            if review.comments:
                for comment in review.comments:
                    await self.create_review_comment(owner, repo, pr_id, comment)

            return str(response.json().get("id", "0")) if response.content else "0"

        except httpx.RequestError as e:
            raise GitProviderError(f"Failed to create review: {e}")

    async def create_review_comment(
        self,
        owner: str,
        repo: str,
        pr_id: str,
        comment: ReviewComment
    ) -> str:
        """
        Create a review comment on Bitbucket.

        Args:
            owner: Workspace/owner name
            repo: Repository name
            pr_id: Pull request ID
            comment: ReviewComment object

        Returns:
            Comment ID

        Raises:
            GitProviderError: If comment creation fails
        """
        if not self._client:
            raise AuthenticationError("Not authenticated")

        try:
            comment_data = {
                "content": {
                    "raw": comment.body
                },
                "inline": {
                    "to": comment.line or 1,
                    "path": comment.path
                }
            }

            response = await self._client.post(
                f"/repositories/{owner}/{repo}/pullrequests/{pr_id}/comments",
                json=comment_data
            )

            if response.status_code == 403:
                raise RateLimitError("Rate limit exceeded")
            elif response.status_code == 404:
                raise NotFoundError(f"Pull request {owner}/{repo}/{pr_id} not found")

            response.raise_for_status()
            data = response.json()

            return str(data.get("id", "0"))

        except httpx.RequestError as e:
            raise GitProviderError(f"Failed to create review comment: {e}")

    async def update_review_comment(
        self,
        owner: str,
        repo: str,
        pr_id: str,
        comment_id: str,
        comment: ReviewComment
    ) -> bool:
        """
        Update a review comment on Bitbucket.

        Args:
            owner: Workspace/owner name
            repo: Repository name
            pr_id: Pull request ID
            comment_id: Comment ID to update
            comment: Updated ReviewComment object

        Returns:
            True if update was successful

        Raises:
            GitProviderError: If comment update fails
        """
        if not self._client:
            raise AuthenticationError("Not authenticated")

        try:
            comment_data = {
                "content": {
                    "raw": comment.body
                }
            }

            response = await self._client.put(
                f"/repositories/{owner}/{repo}/pullrequests/{pr_id}/comments/{comment_id}",
                json=comment_data
            )

            if response.status_code == 403:
                raise RateLimitError("Rate limit exceeded")
            elif response.status_code == 404:
                raise NotFoundError(f"Comment {comment_id} not found")

            response.raise_for_status()
            return True

        except httpx.RequestError as e:
            raise GitProviderError(f"Failed to update review comment: {e}")

    async def delete_review_comment(
        self,
        owner: str,
        repo: str,
        pr_id: str,
        comment_id: str
    ) -> bool:
        """
        Delete a review comment on Bitbucket.

        Args:
            owner: Workspace/owner name
            repo: Repository name
            pr_id: Pull request ID
            comment_id: Comment ID to delete

        Returns:
            True if deletion was successful

        Raises:
            GitProviderError: If comment deletion fails
        """
        if not self._client:
            raise AuthenticationError("Not authenticated")

        try:
            response = await self._client.delete(
                f"/repositories/{owner}/{repo}/pullrequests/{pr_id}/comments/{comment_id}"
            )

            if response.status_code == 403:
                raise RateLimitError("Rate limit exceeded")
            elif response.status_code == 404:
                raise NotFoundError(f"Comment {comment_id} not found")

            response.raise_for_status()
            return True

        except httpx.RequestError as e:
            raise GitProviderError(f"Failed to delete review comment: {e}")

    async def get_rate_limit_status(self) -> Dict[str, Union[int, datetime]]:
        """
        Get Bitbucket rate limit status.

        Returns:
            Dictionary with rate limit information
        """
        if not self._client:
            raise AuthenticationError("Not authenticated")

        try:
            # Bitbucket doesn't have a rate limit endpoint like GitHub
            # Return default values
            return {
                "limit": 1000,  # Bitbucket's default rate limit
                "remaining": 1000,
                "reset_time": datetime.now() + timedelta(hours=1)
            }

        except Exception as e:
            raise GitProviderError(f"Failed to get rate limit status: {e}")

    async def close(self):
        """Close the HTTP client."""
        if self._client:
            await self._client.aclose()
            self._client = None

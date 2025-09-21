"""
GitHub provider implementation.

This module provides integration with GitHub's REST API for pull request operations.
"""

import asyncio
import os
from typing import Dict, List, Optional, Union, Any
from datetime import datetime, timedelta
import httpx
from .base import (
    GitProviderBase, PullRequest, FileChange, ReviewComment, Review,
    AuthenticationError, NotFoundError, RateLimitError, GitProviderError
)


class GitHubProvider(GitProviderBase):
    """
    GitHub API provider implementation.

    Supports GitHub's REST API v3 and GraphQL API v4 for comprehensive
    pull request analysis and review operations.
    """

    def __init__(self, config):
        """Initialize GitHub provider."""
        super().__init__(config)
        self._client = None
        self._rate_limit_info = {}

    async def authenticate(self) -> bool:
        """
        Authenticate with GitHub API.

        Returns:
            True if authentication was successful

        Raises:
            AuthenticationError: If authentication fails
        """
        try:
            # Check if we have a valid token
            if not self.config.api_token:
                raise AuthenticationError(
                    "GitHub token not configured. Please set GITHUB_TOKEN environment variable "
                    "or configure api_token in your configuration file."
                )

            if self.config.api_token == "test_token":
                raise AuthenticationError(
                    "Using test token. Please configure a valid GitHub token."
                )

            # Create HTTP client with authentication
            headers = {
                "Accept": "application/vnd.github.v3+json",
                "User-Agent": "PR-Review-Agent/1.0",
                "Authorization": f"token {self.config.api_token}"
            }

            # Use GitHub App authentication if configured
            if os.getenv("GITHUB_APP_ID") and os.getenv("GITHUB_PRIVATE_KEY"):
                return await self._authenticate_as_app()

            self._client = httpx.AsyncClient(
                base_url=self.config.base_url,
                headers=headers,
                timeout=30.0
            )

            # Test authentication by making a request to /user endpoint
            response = await self._client.get("/user")
            if response.status_code == 401:
                raise AuthenticationError(
                    "Invalid GitHub token. Please check that your token is correct and not expired. "
                    "You can generate a new token at: https://github.com/settings/tokens"
                )
            elif response.status_code == 403:
                raise AuthenticationError(
                    "GitHub token lacks required permissions. "
                    "Please ensure your token has 'repo' scope for private repositories "
                    "or 'public_repo' scope for public repositories."
                )
            elif response.status_code == 422:
                raise AuthenticationError(
                    "GitHub API returned validation error. Please check your token format."
                )

            return True

        except httpx.RequestError as e:
            raise AuthenticationError(f"Failed to connect to GitHub: {e}")

    async def _authenticate_as_app(self) -> bool:
        """Authenticate as a GitHub App."""
        try:
            from github import GithubIntegration
            import jwt

            app_id = os.getenv("GITHUB_APP_ID")
            private_key = os.getenv("GITHUB_PRIVATE_KEY")

            # Generate JWT for app authentication
            payload = {
                "iat": int(datetime.utcnow().timestamp()),
                "exp": int((datetime.utcnow() + timedelta(minutes=10)).timestamp()),
                "iss": app_id
            }

            jwt_token = jwt.encode(payload, private_key, algorithm="RS256")

            self._client = httpx.AsyncClient(
                base_url=self.config.base_url,
                headers={
                    "Authorization": f"Bearer {jwt_token}",
                    "Accept": "application/vnd.github.machine-man-preview+json",
                    "User-Agent": "PR-Review-Agent/1.0"
                },
                timeout=30.0
            )

            # Test app authentication
            response = await self._client.get("/app")
            return response.status_code == 200

        except Exception as e:
            raise AuthenticationError(f"GitHub App authentication failed: {e}")

    async def get_pull_request(self, owner: str, repo: str, pr_number: int) -> PullRequest:
        """
        Get a pull request from GitHub.

        Args:
            owner: Repository owner
            repo: Repository name
            pr_number: Pull request number

        Returns:
            PullRequest object

        Raises:
            NotFoundError: If PR is not found
        """
        if not self._client:
            # Auto-authenticate if not already authenticated
            await self.authenticate()

        try:
            response = await self._client.get(f"/repos/{owner}/{repo}/pulls/{pr_number}")

            if response.status_code == 404:
                raise NotFoundError(f"Pull request {owner}/{repo}#{pr_number} not found")
            elif response.status_code == 403:
                raise RateLimitError("Rate limit exceeded")

            response.raise_for_status()
            data = response.json()

            return PullRequest(
                id=str(data["id"]),
                number=data["number"],
                title=data["title"],
                description=data.get("body", ""),
                author=data["user"]["login"],
                source_branch=data["head"]["ref"],
                target_branch=data["base"]["ref"],
                url=data["html_url"],
                created_at=datetime.fromisoformat(data["created_at"].replace('Z', '+00:00')),
                updated_at=datetime.fromisoformat(data["updated_at"].replace('Z', '+00:00')),
                state=data["state"],
                draft=data.get("draft", False),
                labels=[label["name"] for label in data.get("labels", [])],
                assignees=[assignee["login"] for assignee in data.get("assignees", [])],
                reviewers=[reviewer["login"] for reviewer in data.get("requested_reviewers", [])]
            )

        except httpx.RequestError as e:
            raise GitProviderError(f"Failed to get pull request: {e}")

    async def get_pull_request_files(self, owner: str, repo: str, pr_number: int) -> List[FileChange]:
        """
        Get files changed in a GitHub pull request.

        Args:
            owner: Repository owner
            repo: Repository name
            pr_number: Pull request number

        Returns:
            List of FileChange objects

        Raises:
            NotFoundError: If PR is not found
        """
        if not self._client:
            raise AuthenticationError("Not authenticated")

        try:
            response = await self._client.get(f"/repos/{owner}/{repo}/pulls/{pr_number}/files")

            if response.status_code == 404:
                raise NotFoundError(f"Pull request {owner}/{repo}#{pr_number} not found")
            elif response.status_code == 403:
                raise RateLimitError("Rate limit exceeded")

            response.raise_for_status()
            data = response.json()

            files = []
            for file_data in data:
                files.append(FileChange(
                    filename=file_data["filename"],
                    status=file_data["status"],
                    additions=file_data["additions"],
                    deletions=file_data["deletions"],
                    patch=file_data.get("patch"),
                    blob_url=file_data.get("blob_url"),
                    raw_url=file_data.get("raw_url")
                ))

            return files

        except httpx.RequestError as e:
            raise GitProviderError(f"Failed to get pull request files: {e}")

    async def get_file_content(self, owner: str, repo: str, path: str, ref: str) -> str:
        """
        Get file content from GitHub.

        Args:
            owner: Repository owner
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
                f"/repos/{owner}/{repo}/contents/{path}",
                params={"ref": ref}
            )

            if response.status_code == 404:
                raise NotFoundError(f"File {path} not found in {owner}/{repo}")
            elif response.status_code == 403:
                raise RateLimitError("Rate limit exceeded")

            response.raise_for_status()
            data = response.json()

            if data.get("type") != "file":
                raise NotFoundError(f"{path} is not a file")

            import base64
            return base64.b64decode(data["content"]).decode("utf-8")

        except httpx.RequestError as e:
            raise GitProviderError(f"Failed to get file content: {e}")

    async def create_review(self, owner: str, repo: str, pr_number: int, review: Review) -> str:
        """
        Create a review on GitHub.

        Args:
            owner: Repository owner
            repo: Repository name
            pr_number: Pull request number
            review: Review object

        Returns:
            Review ID

        Raises:
            GitProviderError: If review creation fails
        """
        if not self._client:
            raise AuthenticationError("Not authenticated")

        try:
            # Map grade to GitHub review event
            event_map = {
                "EXCELLENT": "APPROVE",
                "GOOD": "APPROVE",
                "NEEDS_IMPROVEMENT": "REQUEST_CHANGES",
                "POOR": "REQUEST_CHANGES"
            }

            review_data = {
                "body": review.body,
                "event": event_map.get(review.grade, "COMMENT"),
                "comments": []
            }

            # Add inline comments
            for comment in review.comments:
                comment_data = {
                    "path": comment.path,
                    "body": comment.body
                }

                if comment.line:
                    comment_data["line"] = comment.line
                if comment.start_line:
                    comment_data["start_line"] = comment.start_line
                if comment.side:
                    comment_data["side"] = comment.side

                review_data["comments"].append(comment_data)

            response = await self._client.post(
                f"/repos/{owner}/{repo}/pulls/{pr_number}/reviews",
                json=review_data
            )

            if response.status_code == 403:
                raise RateLimitError("Rate limit exceeded")
            elif response.status_code == 422:
                raise GitProviderError("Invalid review data")

            response.raise_for_status()
            data = response.json()

            return str(data["id"])

        except httpx.RequestError as e:
            raise GitProviderError(f"Failed to create review: {e}")

    async def create_review_comment(
        self,
        owner: str,
        repo: str,
        pr_number: int,
        comment: ReviewComment
    ) -> str:
        """
        Create a review comment on GitHub.

        Args:
            owner: Repository owner
            repo: Repository name
            pr_number: Pull request number
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
                "body": comment.body,
                "path": comment.path,
                "side": comment.side
            }

            if comment.line:
                comment_data["line"] = comment.line
            if comment.start_line:
                comment_data["start_line"] = comment.start_line

            response = await self._client.post(
                f"/repos/{owner}/{repo}/pulls/{pr_number}/comments",
                json=comment_data
            )

            if response.status_code == 403:
                raise RateLimitError("Rate limit exceeded")
            elif response.status_code == 422:
                raise GitProviderError("Invalid comment data")

            response.raise_for_status()
            data = response.json()

            return str(data["id"])

        except httpx.RequestError as e:
            raise GitProviderError(f"Failed to create review comment: {e}")

    async def update_review_comment(
        self,
        owner: str,
        repo: str,
        pr_number: int,
        comment_id: str,
        comment: ReviewComment
    ) -> bool:
        """
        Update a review comment on GitHub.

        Args:
            owner: Repository owner
            repo: Repository name
            pr_number: Pull request number
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
            comment_data = {"body": comment.body}

            response = await self._client.patch(
                f"/repos/{owner}/{repo}/pulls/comments/{comment_id}",
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
        pr_number: int,
        comment_id: str
    ) -> bool:
        """
        Delete a review comment on GitHub.

        Args:
            owner: Repository owner
            repo: Repository name
            pr_number: Pull request number
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
                f"/repos/{owner}/{repo}/pulls/comments/{comment_id}"
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
        Get GitHub rate limit status.

        Returns:
            Dictionary with rate limit information
        """
        if not self._client:
            raise AuthenticationError("Not authenticated")

        try:
            response = await self._client.get("/rate_limit")
            response.raise_for_status()
            data = response.json()

            core = data["resources"]["core"]
            return {
                "limit": core["limit"],
                "remaining": core["remaining"],
                "reset_time": datetime.fromtimestamp(core["reset"])
            }

        except httpx.RequestError as e:
            raise GitProviderError(f"Failed to get rate limit status: {e}")

    async def close(self):
        """Close the HTTP client."""
        if self._client:
            await self._client.aclose()
            self._client = None

"""
GitLab provider implementation.

This module provides integration with GitLab's REST API for merge request operations.
"""

import asyncio
from typing import Dict, List, Optional, Union, Any
from datetime import datetime, timedelta
import httpx
from .base import (
    GitProviderBase, PullRequest, FileChange, ReviewComment, Review,
    AuthenticationError, NotFoundError, RateLimitError, GitProviderError
)


class GitLabProvider(GitProviderBase):
    """
    GitLab API provider implementation.

    Supports GitLab's REST API v4 for comprehensive merge request analysis
    and review operations.
    """

    def __init__(self, config):
        """Initialize GitLab provider."""
        super().__init__(config)
        self._client = None
        self._project_id = None

    async def authenticate(self) -> bool:
        """
        Authenticate with GitLab API.

        Returns:
            True if authentication was successful

        Raises:
            AuthenticationError: If authentication fails
        """
        try:
            headers = {
                "User-Agent": "PR-Review-Agent/1.0"
            }

            if self.config.api_token:
                headers["Private-Token"] = self.config.api_token

            self._client = httpx.AsyncClient(
                base_url=self.config.base_url,
                headers=headers,
                timeout=30.0
            )

            # Test authentication
            response = await self._client.get("/user")
            if response.status_code == 401:
                raise AuthenticationError("Invalid GitLab token")
            elif response.status_code == 403:
                raise AuthenticationError("GitLab token lacks required permissions")

            return True

        except httpx.RequestError as e:
            raise AuthenticationError(f"Failed to connect to GitLab: {e}")

    async def get_pull_request(self, owner: str, repo: str, mr_iid: int) -> PullRequest:
        """
        Get a merge request from GitLab.

        Args:
            owner: Project owner/namespace
            repo: Project name
            mr_iid: Merge request IID (internal ID)

        Returns:
            PullRequest object

        Raises:
            NotFoundError: If MR is not found
        """
        if not self._client:
            raise AuthenticationError("Not authenticated")

        try:
            # Get project ID first
            project_id = await self._get_project_id(owner, repo)

            response = await self._client.get(f"/projects/{project_id}/merge_requests/{mr_iid}")

            if response.status_code == 404:
                raise NotFoundError(f"Merge request {owner}/{repo}!{mr_iid} not found")
            elif response.status_code == 403:
                raise RateLimitError("Rate limit exceeded")

            response.raise_for_status()
            data = response.json()

            return PullRequest(
                id=str(data["id"]),
                number=data["iid"],
                title=data["title"],
                description=data.get("description", ""),
                author=data["author"]["username"],
                source_branch=data["source_branch"],
                target_branch=data["target_branch"],
                url=data["web_url"],
                created_at=datetime.fromisoformat(data["created_at"].replace('Z', '+00:00')),
                updated_at=datetime.fromisoformat(data["updated_at"].replace('Z', '+00:00')),
                state=data["state"],
                draft=data.get("draft", False),
                labels=data.get("labels", []),
                assignees=[assignee["username"] for assignee in data.get("assignees", [])],
                reviewers=[reviewer["username"] for reviewer in data.get("reviewers", [])]
            )

        except httpx.RequestError as e:
            raise GitProviderError(f"Failed to get merge request: {e}")

    async def _get_project_id(self, owner: str, repo: str) -> str:
        """
        Get GitLab project ID for a project.

        Args:
            owner: Project owner/namespace
            repo: Project name

        Returns:
            Project ID as string
        """
        if self._project_id:
            return self._project_id

        try:
            # URL encode the project path
            project_path = f"{owner}/{repo}"
            response = await self._client.get(f"/projects/{project_path.replace('/', '%2F')}")

            if response.status_code == 404:
                raise NotFoundError(f"Project {owner}/{repo} not found")
            elif response.status_code == 403:
                raise RateLimitError("Rate limit exceeded")

            response.raise_for_status()
            data = response.json()

            self._project_id = str(data["id"])
            return self._project_id

        except httpx.RequestError as e:
            raise GitProviderError(f"Failed to get project ID: {e}")

    async def get_pull_request_files(self, owner: str, repo: str, mr_iid: int) -> List[FileChange]:
        """
        Get files changed in a GitLab merge request.

        Args:
            owner: Project owner/namespace
            repo: Project name
            mr_iid: Merge request IID

        Returns:
            List of FileChange objects

        Raises:
            NotFoundError: If MR is not found
        """
        if not self._client:
            raise AuthenticationError("Not authenticated")

        try:
            project_id = await self._get_project_id(owner, repo)

            response = await self._client.get(f"/projects/{project_id}/merge_requests/{mr_iid}/changes")

            if response.status_code == 404:
                raise NotFoundError(f"Merge request {owner}/{repo}!{mr_iid} not found")
            elif response.status_code == 403:
                raise RateLimitError("Rate limit exceeded")

            response.raise_for_status()
            data = response.json()

            files = []
            for change in data["changes"]:
                files.append(FileChange(
                    filename=change["new_path"] or change["old_path"],
                    status=self._map_change_status(change["new_file"], change["deleted_file"]),
                    additions=change.get("diff", "").count("\n+") - 1 if change.get("diff") else 0,
                    deletions=change.get("diff", "").count("\n-") - 1 if change.get("diff") else 0,
                    patch=change.get("diff"),
                    blob_url=None,  # GitLab doesn't provide blob URLs in changes API
                    raw_url=None
                ))

            return files

        except httpx.RequestError as e:
            raise GitProviderError(f"Failed to get merge request files: {e}")

    def _map_change_status(self, new_file: bool, deleted_file: bool) -> str:
        """
        Map GitLab change status to standard status.

        Args:
            new_file: Whether this is a new file
            deleted_file: Whether this file was deleted

        Returns:
            Standard status string
        """
        if new_file:
            return "added"
        elif deleted_file:
            return "deleted"
        else:
            return "modified"

    async def get_file_content(self, owner: str, repo: str, path: str, ref: str) -> str:
        """
        Get file content from GitLab.

        Args:
            owner: Project owner/namespace
            repo: Project name
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
            project_id = await self._get_project_id(owner, repo)

            response = await self._client.get(
                f"/projects/{project_id}/repository/files/{path.replace('/', '%2F')}",
                params={"ref": ref}
            )

            if response.status_code == 404:
                raise NotFoundError(f"File {path} not found in {owner}/{repo}")
            elif response.status_code == 403:
                raise RateLimitError("Rate limit exceeded")

            response.raise_for_status()
            data = response.json()

            import base64
            return base64.b64decode(data["content"]).decode("utf-8")

        except httpx.RequestError as e:
            raise GitProviderError(f"Failed to get file content: {e}")

    async def create_review(self, owner: str, repo: str, mr_iid: int, review: Review) -> str:
        """
        Create a review on GitLab.

        Args:
            owner: Project owner/namespace
            repo: Repository name
            mr_iid: Merge request IID
            review: Review object

        Returns:
            Review ID

        Raises:
            GitProviderError: If review creation fails
        """
        if not self._client:
            raise AuthenticationError("Not authenticated")

        try:
            project_id = await self._get_project_id(owner, repo)

            # Map grade to GitLab approval state
            approval_map = {
                "EXCELLENT": True,
                "GOOD": True,
                "NEEDS_IMPROVEMENT": False,
                "POOR": False
            }

            review_data = {
                "body": review.body,
                "approved": approval_map.get(review.grade, False)
            }

            response = await self._client.post(
                f"/projects/{project_id}/merge_requests/{mr_iid}/approvals",
                json=review_data
            )

            if response.status_code == 403:
                raise RateLimitError("Rate limit exceeded")
            elif response.status_code == 404:
                raise NotFoundError(f"Merge request {owner}/{repo}!{mr_iid} not found")

            response.raise_for_status()
            data = response.json()

            # Create discussion for comments
            if review.comments:
                await self._create_discussion(project_id, mr_iid, review.comments)

            return str(data.get("id", "0"))

        except httpx.RequestError as e:
            raise GitProviderError(f"Failed to create review: {e}")

    async def _create_discussion(
        self,
        project_id: str,
        mr_iid: int,
        comments: List[ReviewComment]
    ) -> None:
        """
        Create discussions for review comments.

        Args:
            project_id: GitLab project ID
            mr_iid: Merge request IID
            comments: List of review comments
        """
        for comment in comments:
            comment_data = {
                "body": comment.body,
                "position": {
                    "base_sha": "",  # Would need to get from MR data
                    "start_sha": "",  # Would need to get from MR data
                    "head_sha": "",  # Would need to get from MR data
                    "position_type": "text",
                    "new_path": comment.path,
                    "new_line": comment.line or 1
                }
            }

            try:
                await self._client.post(
                    f"/projects/{project_id}/merge_requests/{mr_iid}/discussions",
                    json=comment_data
                )
            except Exception:
                # Continue with other comments if one fails
                continue

    async def create_review_comment(
        self,
        owner: str,
        repo: str,
        mr_iid: int,
        comment: ReviewComment
    ) -> str:
        """
        Create a review comment on GitLab.

        Args:
            owner: Project owner/namespace
            repo: Repository name
            mr_iid: Merge request IID
            comment: ReviewComment object

        Returns:
            Comment ID

        Raises:
            GitProviderError: If comment creation fails
        """
        if not self._client:
            raise AuthenticationError("Not authenticated")

        try:
            project_id = await self._get_project_id(owner, repo)

            comment_data = {
                "body": comment.body,
                "position": {
                    "position_type": "text",
                    "new_path": comment.path,
                    "new_line": comment.line or 1
                }
            }

            response = await self._client.post(
                f"/projects/{project_id}/merge_requests/{mr_iid}/discussions",
                json=comment_data
            )

            if response.status_code == 403:
                raise RateLimitError("Rate limit exceeded")
            elif response.status_code == 404:
                raise NotFoundError(f"Merge request {owner}/{repo}!{mr_iid} not found")

            response.raise_for_status()
            data = response.json()

            return str(data.get("id", "0"))

        except httpx.RequestError as e:
            raise GitProviderError(f"Failed to create review comment: {e}")

    async def update_review_comment(
        self,
        owner: str,
        repo: str,
        mr_iid: int,
        comment_id: str,
        comment: ReviewComment
    ) -> bool:
        """
        Update a review comment on GitLab.

        Args:
            owner: Project owner/namespace
            repo: Repository name
            mr_iid: Merge request IID
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
            project_id = await self._get_project_id(owner, repo)

            comment_data = {"body": comment.body}

            response = await self._client.put(
                f"/projects/{project_id}/merge_requests/{mr_iid}/discussions/{comment_id}/notes/0",
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
        mr_iid: int,
        comment_id: str
    ) -> bool:
        """
        Delete a review comment on GitLab.

        Args:
            owner: Project owner/namespace
            repo: Repository name
            mr_iid: Merge request IID
            comment_id: Comment ID to delete

        Returns:
            True if deletion was successful

        Raises:
            GitProviderError: If comment deletion fails
        """
        if not self._client:
            raise AuthenticationError("Not authenticated")

        try:
            project_id = await self._get_project_id(owner, repo)

            response = await self._client.delete(
                f"/projects/{project_id}/merge_requests/{mr_iid}/discussions/{comment_id}"
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
        Get GitLab rate limit status.

        Returns:
            Dictionary with rate limit information
        """
        if not self._client:
            raise AuthenticationError("Not authenticated")

        try:
            # GitLab doesn't have a rate limit endpoint like GitHub
            # Return default values
            return {
                "limit": 2000,  # GitLab's default rate limit
                "remaining": 2000,
                "reset_time": datetime.now() + timedelta(hours=1)
            }

        except Exception as e:
            raise GitProviderError(f"Failed to get rate limit status: {e}")

    async def close(self):
        """Close the HTTP client."""
        if self._client:
            await self._client.aclose()
            self._client = None

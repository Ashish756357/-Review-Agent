"""
Mock provider implementation for testing.

This module provides a mock git provider that returns fake data for testing
purposes when real authentication fails.
"""

import asyncio
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Union, Any
from types import SimpleNamespace

from .base import (
    GitProviderBase, PullRequest, FileChange, ReviewComment, Review,
    AuthenticationError, NotFoundError, RateLimitError, GitProviderError
)


class MockProvider(GitProviderBase):
    """
    Mock git provider for testing purposes.

    Returns fake but realistic data for all operations.
    """

    def __init__(self, config):
        """Initialize mock provider."""
        super().__init__(config)
        self._authenticated = False

    async def authenticate(self) -> bool:
        """
        Mock authentication - always succeeds.

        Returns:
            True if authentication was successful
        """
        self._authenticated = True
        return True

    async def get_pull_request(self, owner: str, repo: str, pr_number: int) -> PullRequest:
        """
        Get a mock pull request.

        Args:
            owner: Repository owner
            repo: Repository name
            pr_number: Pull request number

        Returns:
            Mock PullRequest object
        """
        if not self._authenticated:
            await self.authenticate()

        return PullRequest(
            id=str(pr_number),
            number=pr_number,
            title=f"Mock PR #{pr_number}: Feature Implementation",
            description="This is a mock pull request for testing purposes. It contains sample changes to demonstrate the PR review functionality.",
            author="mock-user",
            source_branch="feature/mock-feature",
            target_branch="main",
            url=f"https://github.com/{owner}/{repo}/pull/{pr_number}",
            created_at=datetime.now() - timedelta(days=1),
            updated_at=datetime.now() - timedelta(hours=2),
            state="open",
            draft=False,
            labels=["enhancement", "mock-data"],
            assignees=["mock-user"],
            reviewers=["reviewer1", "reviewer2"]
        )

    async def get_pull_request_files(self, owner: str, repo: str, pr_number: int) -> List[FileChange]:
        """
        Get mock file changes.

        Args:
            owner: Repository owner
            repo: Repository name
            pr_number: Pull request number

        Returns:
            List of mock FileChange objects
        """
        if not self._authenticated:
            await self.authenticate()

        return [
            FileChange(
                filename="src/main.py",
                status="modified",
                additions=15,
                deletions=3,
                patch="""@@ -1,10 +1,25 @@
+import asyncio
+from typing import Optional
+
 def main():
-    print("Hello World")
+    """Main function with improved error handling."""
+    try:
+        result = process_data()
+        print(f"Result: {result}")
+        return result
+    except Exception as e:
+        print(f"Error: {e}")
+        return None
+
+def process_data() -> Optional[int]:
+    """Process data with validation."""
+    return 42
+
+if __name__ == "__main__":
+    main()
""",
                blob_url=f"https://github.com/{owner}/{repo}/blob/main/src/main.py",
                raw_url=f"https://raw.githubusercontent.com/{owner}/{repo}/main/src/main.py"
            ),
            FileChange(
                filename="tests/test_main.py",
                status="added",
                additions=20,
                deletions=0,
                patch="""@@ -0,0 +1,20 @@
+import pytest
+from src.main import main, process_data
+
+def test_main():
+    """Test main function."""
+    assert main() is None
+
+def test_process_data():
+    """Test process_data function."""
+    assert process_data() == 42
+
+def test_process_data_edge_cases():
+    """Test edge cases."""
+    # Add more test cases here
+    pass
""",
                blob_url=f"https://github.com/{owner}/{repo}/blob/main/tests/test_main.py",

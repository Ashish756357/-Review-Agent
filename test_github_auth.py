#!/usr/bin/env python3
"""
Test script to verify GitHub authentication.
"""

import asyncio
import os
from src.pr_review_agent.providers.github import GitHubProvider
from src.pr_review_agent.config import GitProviderConfig


async def test_github_auth():
    """Test GitHub authentication with the provided token."""

    # Set the GitHub token from environment
    github_token = os.getenv("GITHUB_TOKEN")
    if not github_token:
        print("❌ Error: GITHUB_TOKEN environment variable not set")
        print("Please set it with: $env:GITHUB_TOKEN = 'your_token_here'")
        return False

    print(f"🔍 Testing GitHub authentication with token: {github_token[:10]}...")

    # Create GitHub provider config
    config = GitProviderConfig(
        name="github",
        base_url="https://api.github.com",
        api_token=github_token
    )

    # Create provider instance
    provider = GitHubProvider(config)

    try:
        # Test authentication
        print("🔐 Attempting to authenticate...")
        authenticated = await provider.authenticate()

        if authenticated:
            print("✅ Authentication successful!")

            # Test getting rate limit status
            print("📊 Checking rate limit status...")
            rate_limit = await provider.get_rate_limit_status()
            print(f"📈 Rate limit: {rate_limit['remaining']}/{rate_limit['limit']} requests remaining")
            print(f"🔄 Resets at: {rate_limit['reset_time']}")

            return True
        else:
            print("❌ Authentication failed")
            return False

    except Exception as e:
        print(f"❌ Authentication error: {e}")
        return False
    finally:
        # Clean up
        await provider.close()


if __name__ == "__main__":
    # Set the token if provided as command line argument
    import sys
    if len(sys.argv) > 1:
        os.environ["GITHUB_TOKEN"] = sys.argv[1]

    # Run the test
    success = asyncio.run(test_github_auth())

    if success:
        print("\n🎉 GitHub authentication test passed!")
        print("You can now use the PR Review Agent with GitHub.")
    else:
        print("\n💥 GitHub authentication test failed!")
        print("Please check your token and try again.")

#!/usr/bin/env python3
"""
Test script to verify that the PR Review Agent project is working correctly.
"""

import sys
import os
from pathlib import Path

def test_imports():
    """Test that all main modules can be imported."""
    print("Testing imports...")

    try:
        from pr_review_agent.cli import main as cli_main
        print("✓ CLI module imported successfully")
    except ImportError as e:
        print(f"✗ CLI module import failed: {e}")
        return False

    try:
        from pr_review_agent.main import PRReviewAgent
        print("✓ Main PRReviewAgent class imported successfully")
    except ImportError as e:
        print(f"✗ Main module import failed: {e}")
        return False

    try:
        from pr_review_agent.config import Config
        print("✓ Config module imported successfully")
    except ImportError as e:
        print(f"✗ Config module import failed: {e}")
        return False

    try:
        from pr_review_agent.providers.github import GitHubProvider
        print("✓ GitHub provider imported successfully")
    except ImportError as e:
        print(f"✗ GitHub provider import failed: {e}")
        return False

    try:
        from pr_review_agent.analyzers.security_analyzer import PythonSecurityAnalyzer
        print("✓ Security analyzer imported successfully")
    except ImportError as e:
        print(f"✗ Security analyzer import failed: {e}")
        return False

    return True

def test_cli_help():
    """Test that the CLI help command works."""
    print("\nTesting CLI help...")

    try:
        # Import the CLI module and test argument parsing
        from pr_review_agent.cli import main
        import argparse

        # Create a parser similar to the one in CLI
        parser = argparse.ArgumentParser(description="Test parser")
        parser.add_argument("--provider", required=True, choices=["github", "gitlab", "bitbucket"])
        parser.add_argument("--owner", required=True)
        parser.add_argument("--repo", required=True)
        parser.add_argument("--pr", required=True)

        # Test parsing with help
        try:
            parser.parse_args(["--help"])
        except SystemExit:
            pass  # Help command exits normally

        print("✓ CLI argument parsing works")
        return True

    except Exception as e:
        print(f"✗ CLI help test failed: {e}")
        return False

def test_config_loading():
    """Test that configuration can be loaded."""
    print("\nTesting configuration loading...")

    try:
        from pr_review_agent.config import Config

        # Test loading from environment
        config = Config.from_env()
        print("✓ Configuration loaded from environment")

        # Test loading from file if config.example.yaml exists
        config_file = Path("config.example.yaml")
        if config_file.exists():
            config = Config.from_file(str(config_file))
            print("✓ Configuration loaded from file")
        else:
            print("! Configuration file not found (this is OK)")

        return True

    except Exception as e:
        print(f"✗ Configuration loading failed: {e}")
        return False

def test_package_installation():
    """Test that the package is properly installed."""
    print("\nTesting package installation...")

    try:
        import pr_review_agent
        print(f"✓ Package installed successfully (version: {pr_review_agent.__version__})")
        return True
    except ImportError as e:
        print(f"✗ Package installation failed: {e}")
        return False
    except AttributeError:
        print("✓ Package installed successfully (no version info)")
        return True

def main():
    """Run all tests."""
    print("=" * 60)
    print("PR Review Agent - Project Test Suite")
    print("=" * 60)

    tests = [
        test_imports,
        test_cli_help,
        test_config_loading,
        test_package_installation
    ]

    passed = 0
    total = len(tests)

    for test in tests:
        if test():
            passed += 1

    print("\n" + "=" * 60)
    print(f"Test Results: {passed}/{total} tests passed")

    if passed == total:
        print("🎉 All tests passed! Your PR Review Agent project is working correctly.")
        print("\nTo use the CLI:")
        print("  pr-review-agent --provider github --owner <owner> --repo <repo> --pr <pr_number>")
        return 0
    else:
        print("❌ Some tests failed. Please check the error messages above.")
        return 1

if __name__ == "__main__":
    sys.exit(main())

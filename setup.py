"""
Setup script for PR Review Agent.

This script configures the package for installation and distribution.
"""

from setuptools import setup, find_packages
from pathlib import Path

# Read the README file
this_directory = Path(__file__).parent
long_description = (this_directory / "README.md").read_text()

# Read requirements
requirements = (this_directory / "requirements.txt").read_text().splitlines()

setup(
    name="pr-review-agent",
    version="0.1.0",
    author="PR Review Agent Team",
    author_email="team@pr-review-agent.dev",
    description="AI-powered pull request review agent for multiple git platforms",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/your-org/pr-review-agent",
    packages=find_packages(where="src"),
    package_dir={"": "src"},
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Topic :: Software Development :: Quality Assurance",
        "Topic :: Software Development :: Version Control :: Git",
    ],
    python_requires=">=3.8",
    install_requires=requirements,
    extras_require={
        "dev": [
            "pytest>=7.0.0",
            "pytest-asyncio>=0.21.0",
            "pytest-cov>=4.0.0",
            "black>=23.0.0",
            "flake8>=6.0.0",
            "mypy>=1.0.0",
            "pre-commit>=3.0.0",
        ],
        "cli": [
            "rich>=13.0.0",
        ],
    },
    entry_points={
        "console_scripts": [
            "pr-review-agent=pr_review_agent.cli:main",
        ],
    },
    include_package_data=True,
    zip_safe=False,
)

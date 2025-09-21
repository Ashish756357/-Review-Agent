"""
Configuration management for PR Review Agent.

This module handles loading and validating configuration from environment variables,
configuration files, and provides default values for all settings.
"""

import os
from pathlib import Path
from typing import Dict, List, Optional, Union

from pydantic import BaseModel, Field, validator
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()


class GitProviderConfig(BaseModel):
    """Configuration for a git provider."""

    name: str = Field(..., description="Provider name (github, gitlab, bitbucket)")
    base_url: str = Field(..., description="Base URL for the git provider API")
    api_token: Optional[str] = Field(None, description="API token for authentication")
    webhook_secret: Optional[str] = Field(None, description="Webhook secret for verification")
    enabled: bool = Field(True, description="Whether this provider is enabled")


class AIConfig(BaseModel):
    """Configuration for AI services."""

    provider: str = Field("openai", description="AI provider (openai, anthropic)")
    api_key: Optional[str] = Field(None, description="API key for AI service")
    model: str = Field("gpt-3.5-turbo", description="AI model to use")
    max_tokens: int = Field(2000, description="Maximum tokens for AI responses")
    temperature: float = Field(0.3, description="Temperature for AI responses")
    enabled: bool = Field(True, description="Whether AI features are enabled")


class AnalysisConfig(BaseModel):
    """Configuration for code analysis."""

    enable_security_scan: bool = Field(True, description="Enable security vulnerability scanning")
    enable_performance_analysis: bool = Field(True, description="Enable performance analysis")
    enable_style_check: bool = Field(True, description="Enable code style checking")
    enable_complexity_analysis: bool = Field(True, description="Enable code complexity analysis")
    max_file_size: int = Field(1024 * 1024, description="Maximum file size to analyze (bytes)")
    ignored_extensions: List[str] = Field(
        default_factory=lambda: [".lock", ".log", ".tmp", ".cache"],
        description="File extensions to ignore during analysis"
    )
    ignored_paths: List[str] = Field(
        default_factory=lambda: ["node_modules", ".git", "__pycache__", "build", "dist"],
        description="Paths to ignore during analysis"
    )


class ScoringConfig(BaseModel):
    """Configuration for quality scoring."""

    weights: Dict[str, float] = Field(
        default_factory=lambda: {
            "security": 0.3,
            "performance": 0.2,
            "style": 0.15,
            "complexity": 0.15,
            "maintainability": 0.2
        },
        description="Weights for different scoring aspects"
    )


class ReviewConfig(BaseModel):
    """Configuration for posting reviews back to git providers."""

    enable_summary_comment: bool = Field(True, description="Post a summary comment on the PR")
    enable_inline_comments: bool = Field(True, description="Post inline code comments on the PR")
    post_reviews: bool = Field(False, description="Actually POST reviews/comments to the provider")
    thresholds: Dict[str, float] = Field(
        default_factory=lambda: {
            "excellent": 0.9,
            "good": 0.7,
            "needs_improvement": 0.5,
            "poor": 0.0
        },
        description="Score thresholds for different quality levels"
    )


class Config(BaseModel):
    """Main configuration class for PR Review Agent."""

    # Application settings
    app_name: str = Field("PR Review Agent", description="Application name")
    debug: bool = Field(False, description="Enable debug mode")
    log_level: str = Field("INFO", description="Logging level")

    # Git providers
    git_providers: List[GitProviderConfig] = Field(
        default_factory=list,
        description="List of configured git providers"
    )

    # AI configuration
    ai: AIConfig = Field(default_factory=AIConfig, description="AI service configuration")

    # Analysis configuration
    analysis: AnalysisConfig = Field(
        default_factory=AnalysisConfig,
        description="Code analysis configuration"
    )

    # Scoring configuration
    scoring: ScoringConfig = Field(
        default_factory=ScoringConfig,
        description="Quality scoring configuration"
    )

    # Review posting configuration
    review: ReviewConfig = Field(default_factory=ReviewConfig, description="Review posting configuration")

    # Server configuration
    host: str = Field("0.0.0.0", description="Server host")
    port: int = Field(8000, description="Server port")
    webhook_timeout: int = Field(30, description="Webhook processing timeout (seconds)")

    @validator("git_providers", pre=True)
    def parse_git_providers(cls, v):
        """Parse git providers from environment or config."""
        if isinstance(v, list):
            return v

        # Parse from environment variables
        providers = []
        for provider_name in ["github", "gitlab", "bitbucket"]:
            enabled = os.getenv(f"{provider_name.upper()}_ENABLED", "true").lower() == "true"
            if enabled:
                api_token = os.getenv(f"{provider_name.upper()}_TOKEN")
                webhook_secret = os.getenv(f"{provider_name.upper()}_WEBHOOK_SECRET")

                if provider_name == "github":
                    base_url = os.getenv("GITHUB_BASE_URL", "https://api.github.com")
                elif provider_name == "gitlab":
                    base_url = os.getenv("GITLAB_BASE_URL", "https://gitlab.com/api/v4")
                else:  # bitbucket
                    base_url = os.getenv("BITBUCKET_BASE_URL", "https://api.bitbucket.org/2.0")

                providers.append(GitProviderConfig(
                    name=provider_name,
                    base_url=base_url,
                    api_token=api_token,
                    webhook_secret=webhook_secret,
                    enabled=enabled
                ))

        return providers

    @classmethod
    def from_env(cls) -> "Config":
        """Create configuration from environment variables."""
        return cls()

    @classmethod
    def from_file(cls, config_path: Union[str, Path]) -> "Config":
        """Create configuration from a YAML file."""
        import yaml

        config_path = Path(config_path)
        if not config_path.exists():
            raise FileNotFoundError(f"Configuration file not found: {config_path}")

        with open(config_path, "r") as f:
            config_data = yaml.safe_load(f)

        return cls(**config_data)

    def to_dict(self) -> Dict:
        """Convert configuration to dictionary."""
        return self.dict()

    def save_to_file(self, config_path: Union[str, Path]) -> None:
        """Save configuration to a YAML file."""
        import yaml

        config_path = Path(config_path)
        config_path.parent.mkdir(parents=True, exist_ok=True)

        with open(config_path, "w") as f:
            yaml.dump(self.dict(), f, default_flow_style=False, sort_keys=False)


# Global configuration instance
config = Config.from_env()

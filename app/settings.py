"""Typed, environment-driven service configuration."""

from __future__ import annotations

from functools import lru_cache

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime settings. All environment variables use the ``RELEASE_`` prefix."""

    model_config = SettingsConfigDict(
        env_prefix="RELEASE_",
        case_sensitive=False,
        extra="ignore",
    )

    service_name: str = Field(default="release-status-service", min_length=1, max_length=63)
    version: str = Field(default="dev", min_length=1, max_length=63)
    commit_sha: str = Field(default="unknown", min_length=1, max_length=64)
    environment: str = Field(default="local", min_length=1, max_length=32)
    force_not_ready: bool = False
    failure_reason: str = Field(default="controlled readiness drill", min_length=1, max_length=200)

    @field_validator("service_name", "version", "commit_sha", "environment", "failure_reason")
    @classmethod
    def reject_blank_values(cls, value: str) -> str:
        """Reject whitespace-only values while preserving meaningful release identifiers."""
        if not value.strip():
            raise ValueError("must not be blank")
        return value.strip()

    def release_metadata(self) -> dict[str, str]:
        """Return the immutable metadata exposed by the version endpoint."""
        return {
            "service": self.service_name,
            "version": self.version,
            "commit_sha": self.commit_sha,
            "environment": self.environment,
        }


@lru_cache
def get_settings() -> Settings:
    """Load settings once for a process; dependency injection keeps tests deterministic."""
    return Settings()


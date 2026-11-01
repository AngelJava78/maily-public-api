"""Configuration of the service, validated at start-up from environment variables or `.env`.

`load_settings()` is the only place that reads the environment: `create_app(settings)` receives what it
returns, so the tests build the application with any configuration (research R10). The messages about
a bad configuration name the variables, never their values: DATABASE_URL carries the only secret of
the service (Principle VIII).
"""

import re
from dataclasses import dataclass
from datetime import UTC, datetime
from urllib.parse import urlsplit

from pydantic import Field, ValidationError, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from src import VERSION

# The `service` of `/info` (health contract v1) and the value of what is not known.
SERVICE_NAME = "maily-public-api"
UNKNOWN = "unknown"

_DATABASE_SCHEME = "postgresql+asyncpg"
_ORIGIN_SCHEMES = ("http", "https")
_COMMIT = re.compile(r"[0-9A-Fa-f]{7,64}")
_ENVIRONMENT = re.compile(r"[A-Za-z0-9._-]{1,50}")


class InvalidSettingsError(Exception):
    """The configuration is incomplete or wrong. The message names variables, never values."""


class Settings(BaseSettings):
    """Every variable of contracts/environment.md (except the ones only the tests read)."""

    database_url: str
    cors_allowed_origins: str
    catalog_cache_max_age_seconds: int = Field(default=300, ge=0, le=86_400)
    database_query_timeout_seconds: float = Field(default=3.0, ge=1, le=30)
    docs_enabled: bool = True
    rate_limit_per_minute: int = Field(default=60, ge=0, le=10_000)
    trusted_proxy_hops: int = Field(default=0, ge=0, le=5)
    health_ready_timeout_seconds: float = Field(default=2.0, gt=0, le=10)
    # Build identification of `/info`: an invalid value is published as `unknown`, it does not stop
    # the start-up (contracts/health-v1.md).
    app_commit_sha: str | None = None
    app_build_date: str | None = None
    app_environment: str | None = None

    # An empty variable (docker-compose passes empty values when `.env` has none) counts as unset.
    model_config = SettingsConfigDict(env_file=".env", extra="ignore", env_ignore_empty=True)

    @field_validator("database_url")
    @classmethod
    def _asyncpg_url_with_host(cls, value: str) -> str:
        value = value.strip()
        try:
            parts = urlsplit(value)
            host = parts.hostname
        except ValueError:
            host = None
        # The message never includes the value: it carries the password.
        if not value.startswith(f"{_DATABASE_SCHEME}://") or not host:
            raise ValueError(f"It must start with {_DATABASE_SCHEME}:// and name a host")
        return value

    @field_validator("cors_allowed_origins")
    @classmethod
    def _explicit_origins(cls, value: str) -> str:
        origins = _split_origins(value)
        if not origins:
            raise ValueError("At least one origin is required")
        for origin in origins:
            if not _is_origin(origin):
                raise ValueError(
                    "Each origin is http:// or https:// plus a host and an optional port, "
                    "without a path, a query or *"
                )
        return value

    @property
    def cors_origins(self) -> list[str]:
        return _split_origins(self.cors_allowed_origins)


def _split_origins(text: str) -> list[str]:
    return [origin.strip() for origin in text.split(",") if origin.strip()]


def _is_origin(text: str) -> bool:
    if "*" in text:
        return False
    try:
        parts = urlsplit(text)
        parts.port  # noqa: B018 - raises ValueError on an invalid port
    except ValueError:
        return False
    return (
        parts.scheme in _ORIGIN_SCHEMES
        and bool(parts.hostname)
        and parts.path == ""
        and not parts.query
        and not parts.fragment
        and parts.username is None
        and parts.password is None
    )


def load_settings() -> Settings:
    """Read and validate the configuration, or name every wrong variable (never its value)."""
    try:
        return Settings()
    except ValidationError as error:
        # `msg` never carries the input value (that is `input`, which is never shown).
        problems = sorted(
            {f"{str(item['loc'][0]).upper()}: {item['msg']}" for item in error.errors() if item["loc"]}
        )
        raise InvalidSettingsError(
            "The configuration is not valid: " + "; ".join(problems)
        ) from None


@dataclass(frozen=True, slots=True)
class BuildInfo:
    """What `/info` publishes (health contract v1)."""

    service: str
    version: str
    commit: str
    build_date: str
    environment: str


def build_info(settings: Settings) -> BuildInfo:
    return BuildInfo(
        service=SERVICE_NAME,
        version=VERSION,
        commit=_commit(settings.app_commit_sha),
        build_date=_build_date(settings.app_build_date),
        environment=_environment(settings.app_environment),
    )


def _commit(value: str | None) -> str:
    if value is None or not _COMMIT.fullmatch(value.strip()):
        return UNKNOWN
    return value.strip().lower()


def _build_date(value: str | None) -> str:
    if value is None:
        return UNKNOWN
    try:
        moment = datetime.fromisoformat(value.strip())
    except ValueError:
        return UNKNOWN
    if moment.utcoffset() is None:
        return UNKNOWN
    return moment.astimezone(UTC).isoformat().replace("+00:00", "Z")


def _environment(value: str | None) -> str:
    if value is None or not _ENVIRONMENT.fullmatch(value):
        return UNKNOWN
    return value

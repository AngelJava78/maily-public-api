"""Configuration validated at start-up (FR-023, FR-024, contracts/environment.md)."""

import pytest

from src.config import UNKNOWN, InvalidSettingsError, build_info, load_settings

SECRET_URL = "postgresql+asyncpg://maily_public_api:s3cr3t-pass@db.internal:5432/maily"
VARIABLES = (
    "DATABASE_URL",
    "CORS_ALLOWED_ORIGINS",
    "CATALOG_CACHE_MAX_AGE_SECONDS",
    "DATABASE_QUERY_TIMEOUT_SECONDS",
    "DOCS_ENABLED",
    "RATE_LIMIT_PER_MINUTE",
    "TRUSTED_PROXY_HOPS",
    "HEALTH_READY_TIMEOUT_SECONDS",
    "APP_COMMIT_SHA",
    "APP_BUILD_DATE",
    "APP_ENVIRONMENT",
)


@pytest.fixture(autouse=True)
def clean_environment(monkeypatch: pytest.MonkeyPatch, tmp_path) -> pytest.MonkeyPatch:
    # A directory without `.env`, and none of the variables inherited from the shell.
    monkeypatch.chdir(tmp_path)
    for name in VARIABLES:
        monkeypatch.delenv(name, raising=False)
    return monkeypatch


def set_required(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DATABASE_URL", SECRET_URL)
    monkeypatch.setenv("CORS_ALLOWED_ORIGINS", "https://maily.example")


def invalid(monkeypatch: pytest.MonkeyPatch) -> str:
    with pytest.raises(InvalidSettingsError) as error:
        load_settings()
    return str(error.value)


def test_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    set_required(monkeypatch)

    settings = load_settings()

    assert settings.catalog_cache_max_age_seconds == 300
    assert settings.database_query_timeout_seconds == 3
    assert settings.docs_enabled is True
    assert settings.rate_limit_per_minute == 60
    assert settings.trusted_proxy_hops == 0
    assert settings.health_ready_timeout_seconds == 2
    assert settings.cors_origins == ["https://maily.example"]


def test_missing_required_variables_are_all_named(monkeypatch: pytest.MonkeyPatch) -> None:
    message = invalid(monkeypatch)

    assert "DATABASE_URL" in message
    assert "CORS_ALLOWED_ORIGINS" in message


def test_empty_variable_counts_as_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    set_required(monkeypatch)
    monkeypatch.setenv("CORS_ALLOWED_ORIGINS", "")

    assert "CORS_ALLOWED_ORIGINS" in invalid(monkeypatch)


def test_empty_optional_variable_takes_its_default(monkeypatch: pytest.MonkeyPatch) -> None:
    set_required(monkeypatch)
    monkeypatch.setenv("RATE_LIMIT_PER_MINUTE", "")

    assert load_settings().rate_limit_per_minute == 60


def test_several_origins(monkeypatch: pytest.MonkeyPatch) -> None:
    set_required(monkeypatch)
    monkeypatch.setenv(
        "CORS_ALLOWED_ORIGINS", " https://maily.example , http://localhost:4200,https://b.example:8443"
    )

    assert load_settings().cors_origins == [
        "https://maily.example",
        "http://localhost:4200",
        "https://b.example:8443",
    ]


@pytest.mark.parametrize(
    "origins",
    [
        "*",
        "https://maily.example,*",
        "https://maily.example/suscripciones",
        "https://maily.example/",
        "https://maily.example?x=1",
        "ftp://maily.example",
        "maily.example",
        "https://",
        "https://maily.example:99999",
        " , ",
    ],
)
def test_invalid_origins(monkeypatch: pytest.MonkeyPatch, origins: str) -> None:
    set_required(monkeypatch)
    monkeypatch.setenv("CORS_ALLOWED_ORIGINS", origins)

    assert "CORS_ALLOWED_ORIGINS" in invalid(monkeypatch)


@pytest.mark.parametrize(
    "url",
    [
        "postgresql://user:pass@host:5432/db",
        "postgresql+psycopg://user:pass@host:5432/db",
        "postgresql+asyncpg:///db",
        "not a url",
    ],
)
def test_invalid_database_url_is_named_without_its_value(
    monkeypatch: pytest.MonkeyPatch, url: str
) -> None:
    set_required(monkeypatch)
    monkeypatch.setenv("DATABASE_URL", url)

    message = invalid(monkeypatch)

    assert "DATABASE_URL" in message
    assert url not in message


def test_no_message_shows_the_secret(monkeypatch: pytest.MonkeyPatch) -> None:
    set_required(monkeypatch)
    monkeypatch.setenv("RATE_LIMIT_PER_MINUTE", "muchas")

    message = invalid(monkeypatch)

    assert "RATE_LIMIT_PER_MINUTE" in message
    assert "s3cr3t-pass" not in message
    assert "db.internal" not in message
    assert "muchas" not in message


@pytest.mark.parametrize(
    ("name", "value"),
    [
        ("CATALOG_CACHE_MAX_AGE_SECONDS", "-1"),
        ("CATALOG_CACHE_MAX_AGE_SECONDS", "86401"),
        ("DATABASE_QUERY_TIMEOUT_SECONDS", "0.5"),
        ("DATABASE_QUERY_TIMEOUT_SECONDS", "31"),
        ("DOCS_ENABLED", "quizás"),
        ("RATE_LIMIT_PER_MINUTE", "-1"),
        ("RATE_LIMIT_PER_MINUTE", "10001"),
        ("TRUSTED_PROXY_HOPS", "6"),
        ("TRUSTED_PROXY_HOPS", "-1"),
        ("HEALTH_READY_TIMEOUT_SECONDS", "0"),
        ("HEALTH_READY_TIMEOUT_SECONDS", "11"),
    ],
)
def test_out_of_range_values_are_named(
    monkeypatch: pytest.MonkeyPatch, name: str, value: str
) -> None:
    set_required(monkeypatch)
    monkeypatch.setenv(name, value)

    assert name in invalid(monkeypatch)


def test_limits_of_the_ranges_are_accepted(monkeypatch: pytest.MonkeyPatch) -> None:
    set_required(monkeypatch)
    monkeypatch.setenv("CATALOG_CACHE_MAX_AGE_SECONDS", "0")
    monkeypatch.setenv("DATABASE_QUERY_TIMEOUT_SECONDS", "30")
    monkeypatch.setenv("DOCS_ENABLED", "false")
    monkeypatch.setenv("RATE_LIMIT_PER_MINUTE", "0")
    monkeypatch.setenv("TRUSTED_PROXY_HOPS", "5")
    monkeypatch.setenv("HEALTH_READY_TIMEOUT_SECONDS", "10")

    settings = load_settings()

    assert settings.catalog_cache_max_age_seconds == 0
    assert settings.docs_enabled is False
    assert settings.rate_limit_per_minute == 0
    assert settings.trusted_proxy_hops == 5


def test_build_info_without_variables_is_unknown(monkeypatch: pytest.MonkeyPatch) -> None:
    set_required(monkeypatch)

    info = build_info(load_settings())

    assert info.service == "maily-public-api"
    assert info.version == "1.0.0"
    assert (info.commit, info.build_date, info.environment) == (UNKNOWN, UNKNOWN, UNKNOWN)


def test_build_info_valid_values(monkeypatch: pytest.MonkeyPatch) -> None:
    set_required(monkeypatch)
    monkeypatch.setenv("APP_COMMIT_SHA", "ABCDEF1234")
    monkeypatch.setenv("APP_BUILD_DATE", "2026-11-01T12:00:00-06:00")
    monkeypatch.setenv("APP_ENVIRONMENT", "dev")

    info = build_info(load_settings())

    assert info.commit == "abcdef1234"
    assert info.build_date == "2026-11-01T18:00:00Z"
    assert info.environment == "dev"


@pytest.mark.parametrize(
    ("name", "value"),
    [
        ("APP_COMMIT_SHA", "xyz"),
        ("APP_COMMIT_SHA", "abc12"),
        ("APP_BUILD_DATE", "ayer"),
        ("APP_BUILD_DATE", "2026-11-01T12:00:00"),
        ("APP_ENVIRONMENT", "dev con espacios"),
        ("APP_ENVIRONMENT", "x" * 51),
    ],
)
def test_invalid_build_values_become_unknown(
    monkeypatch: pytest.MonkeyPatch, name: str, value: str
) -> None:
    set_required(monkeypatch)
    monkeypatch.setenv(name, value)

    info = build_info(load_settings())

    assert UNKNOWN in (info.commit, info.build_date, info.environment)

"""`uvicorn src.main:app` reads the environment only when it asks for `app` (research R10)."""

from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi import FastAPI

import src.main

REQUIRED = ("DATABASE_URL", "CORS_ALLOWED_ORIGINS")


@pytest.fixture(autouse=True)
def isolated_environment(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Iterator[None]:
    # Without the repository's `.env` nor the variables of the shell running the tests.
    monkeypatch.chdir(tmp_path)
    for name in REQUIRED:
        monkeypatch.delenv(name, raising=False)
    vars(src.main).pop("app", None)
    yield
    vars(src.main).pop("app", None)


def test_importing_main_does_not_build_the_application() -> None:
    assert "app" not in vars(src.main)


def test_app_is_built_from_the_environment_once(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://reader:s3cret@127.0.0.1:1/catalog")
    monkeypatch.setenv("CORS_ALLOWED_ORIGINS", "https://app.example.com")

    application = src.main.app

    assert isinstance(application, FastAPI)
    assert application.state.settings.cors_origins == ["https://app.example.com"]
    assert src.main.app is application


def test_app_without_configuration_stops_naming_the_variables(
    caplog: pytest.LogCaptureFixture,
) -> None:
    with pytest.raises(SystemExit) as stopped:
        src.main.app

    assert stopped.value.code == 1
    for name in REQUIRED:
        assert name in caplog.text


def test_other_attributes_still_raise_attribute_error() -> None:
    with pytest.raises(AttributeError):
        src.main.application

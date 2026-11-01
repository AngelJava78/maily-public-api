"""Health contract v1 in the Service (FR-020, contracts/health-v1.md), with a Repository double."""

import pytest

from src.config import UNKNOWN, build_info
from src.repositories.errors import DatabaseUnavailableError
from src.services.health_service import HealthService
from tests.helpers import FakeHealthRepository, make_settings


def make_service(repository: FakeHealthRepository, timeout: float = 2) -> HealthService:
    return HealthService(repository, ready_timeout_seconds=timeout, build_info=build_info(make_settings()))


async def test_ready_when_the_database_answers() -> None:
    result = await make_service(FakeHealthRepository()).ready()

    assert result.status == "ok"
    [check] = result.checks
    assert (check.name, check.status, check.error) == ("database", "ok", None)
    assert check.latency_ms >= 0


@pytest.mark.parametrize("kind", ["connection_error", "timeout"])
async def test_unavailable_database(kind: str) -> None:
    repository = FakeHealthRepository(error=DatabaseUnavailableError(kind))  # type: ignore[arg-type]

    result = await make_service(repository).ready()

    assert result.status == "unavailable"
    assert (result.checks[0].status, result.checks[0].error) == ("error", kind)


async def test_slower_than_the_limit_is_a_timeout() -> None:
    result = await make_service(FakeHealthRepository(delay=1), timeout=0.05).ready()

    assert result.status == "unavailable"
    assert result.checks[0].error == "timeout"
    assert result.checks[0].latency_ms >= 50


async def test_anything_else_is_unexpected_and_never_raises() -> None:
    result = await make_service(FakeHealthRepository(error=RuntimeError("boom"))).ready()

    assert result.status == "unavailable"
    assert result.checks[0].error == "unexpected_error"


def test_info_without_build_variables() -> None:
    info = make_service(FakeHealthRepository()).info()

    assert info.service == "maily-public-api"
    assert info.version == "1.0.0"
    assert (info.commit, info.build_date, info.environment) == (UNKNOWN, UNKNOWN, UNKNOWN)

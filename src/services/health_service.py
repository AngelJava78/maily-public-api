"""Health contract v1: readiness of the database and identification of the build (FR-020)."""

import asyncio
import logging
import time

from src.config import BuildInfo
from src.dtos.health import CheckError, CheckResult, InfoResponse, ReadyResponse
from src.repositories.database_health_repository import DatabaseHealthRepository
from src.repositories.errors import DatabaseUnavailableError

logger = logging.getLogger(__name__)


class HealthService:
    def __init__(
        self,
        repository: DatabaseHealthRepository,
        ready_timeout_seconds: float,
        build_info: BuildInfo,
    ) -> None:
        self._repository = repository
        self._timeout = ready_timeout_seconds
        self._build_info = build_info

    async def ready(self) -> ReadyResponse:
        """Never raises: a failure is a 503 with its code, not a 500 (contracts/health-v1.md)."""
        started = time.perf_counter()
        error: CheckError | None = None
        try:
            async with asyncio.timeout(self._timeout):
                await self._repository.ping()
        except TimeoutError:
            error = "timeout"
        except DatabaseUnavailableError as failure:
            error = failure.kind
        except Exception:
            logger.exception("Unexpected failure of the database health check")
            error = "unexpected_error"
        latency_ms = int((time.perf_counter() - started) * 1000)

        check = CheckResult(
            name="database",
            status="ok" if error is None else "error",
            latency_ms=latency_ms,
            error=error,
        )
        return ReadyResponse(status="ok" if error is None else "unavailable", checks=[check])

    def info(self) -> InfoResponse:
        return InfoResponse.model_validate(self._build_info)

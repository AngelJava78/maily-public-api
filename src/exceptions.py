"""Errors of the service that become an HTTP response with the uniform body (src/error_handlers.py)."""

from src.messages import (
    RATE_LIMIT_EXCEEDED_MESSAGE,
    SERVICE_UNAVAILABLE_MESSAGE,
    ErrorCode,
)


class AppError(Exception):
    """An error with its HTTP status, its code, its Spanish message and any extra headers."""

    def __init__(
        self,
        status_code: int,
        code: ErrorCode,
        message: str,
        headers: dict[str, str] | None = None,
    ) -> None:
        super().__init__(code)
        self.status_code = status_code
        self.code = code
        self.message = message
        self.headers = headers or {}


class ServiceUnavailableError(AppError):
    """The shared database did not answer, refused the connection or ran out of time (FR-015)."""

    def __init__(self) -> None:
        super().__init__(503, ErrorCode.SERVICE_UNAVAILABLE, SERVICE_UNAVAILABLE_MESSAGE)


class RateLimitExceededError(AppError):
    """The client IP has no tokens left (FR-019); `Retry-After` says when the next one arrives."""

    def __init__(self, retry_after_seconds: int) -> None:
        super().__init__(
            429,
            ErrorCode.RATE_LIMIT_EXCEEDED,
            RATE_LIMIT_EXCEEDED_MESSAGE,
            headers={"Retry-After": str(retry_after_seconds)},
        )
        self.retry_after_seconds = retry_after_seconds

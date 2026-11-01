"""Translation of database failures (research R5).

A read runs in two phases so the kind of failure can be told: getting the connection (any failure
means the database is not available) and running the queries (only a lost connection or an SQLSTATE
of the classes 08, 53 or 57 means that; anything else, such as a missing grant, is left to rise and
ends as a 500). A cancellation (`asyncio.timeout`) is a `BaseException` and is never caught here.
"""

from collections.abc import Iterator
from contextlib import contextmanager
from typing import Literal

from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncSession

UnavailableKind = Literal["timeout", "connection_error", "unexpected_error"]

# 08 connection exception, 53 insufficient resources, 57 operator intervention.
_UNAVAILABLE_SQLSTATE_CLASSES = ("08", "53", "57")
_QUERY_CANCELED = "57014"  # statement_timeout


class DatabaseUnavailableError(Exception):
    """The shared database cannot be used right now."""

    def __init__(self, kind: UnavailableKind) -> None:
        super().__init__(kind)
        self.kind: UnavailableKind = kind


def _sqlstate(error: DBAPIError) -> str | None:
    state = getattr(error.orig, "sqlstate", None) or getattr(error.orig, "pgcode", None)
    return state if isinstance(state, str) else None


def unavailable_kind(error: DBAPIError) -> UnavailableKind | None:
    """`None` if the failure is not about availability (it must rise as an unexpected error)."""
    state = _sqlstate(error)
    if state == _QUERY_CANCELED:
        return "timeout"
    if error.connection_invalidated or (state is not None and state[:2] in _UNAVAILABLE_SQLSTATE_CLASSES):
        return "connection_error"
    return None


def is_unavailable(error: DBAPIError) -> bool:
    return unavailable_kind(error) is not None


@contextmanager
def unavailable_on_failure() -> Iterator[None]:
    """Second phase of every read: availability failures become `DatabaseUnavailableError`."""
    try:
        yield
    except DBAPIError as error:
        kind = unavailable_kind(error)
        if kind is None:
            raise
        raise DatabaseUnavailableError(kind) from None


async def open_connection(session: AsyncSession) -> None:
    """First phase of every read: any failure to get a connection means the database is not available."""
    try:
        await session.connection()
    except Exception:
        raise DatabaseUnavailableError("connection_error") from None

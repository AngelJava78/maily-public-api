"""Classification of the database failures (research R5)."""

import pytest
from sqlalchemy.exc import DBAPIError

from src.repositories.errors import (
    DatabaseUnavailableError,
    is_unavailable,
    open_connection,
    unavailable_kind,
)


class _DriverError(Exception):
    def __init__(self, sqlstate: str | None) -> None:
        super().__init__("driver error")
        self.sqlstate = sqlstate


def dbapi_error(sqlstate: str | None, *, invalidated: bool = False) -> DBAPIError:
    return DBAPIError("SELECT 1", None, _DriverError(sqlstate), connection_invalidated=invalidated)


@pytest.mark.parametrize("sqlstate", ["08006", "08001", "53300", "57P01"])
def test_connection_failures_are_unavailable(sqlstate: str) -> None:
    error = dbapi_error(sqlstate)

    assert is_unavailable(error)
    assert unavailable_kind(error) == "connection_error"


def test_statement_timeout_is_a_timeout() -> None:
    assert unavailable_kind(dbapi_error("57014")) == "timeout"


def test_invalidated_connection_is_unavailable() -> None:
    assert unavailable_kind(dbapi_error(None, invalidated=True)) == "connection_error"


@pytest.mark.parametrize("sqlstate", ["42501", "42P01", "22P02", None])
def test_other_failures_rise_as_unexpected(sqlstate: str | None) -> None:
    assert not is_unavailable(dbapi_error(sqlstate))


class _BrokenSession:
    async def connection(self) -> None:
        raise OSError("connection refused by db.internal:5432")


async def test_open_connection_translates_any_failure() -> None:
    with pytest.raises(DatabaseUnavailableError) as error:
        await open_connection(_BrokenSession())  # type: ignore[arg-type]

    assert error.value.kind == "connection_error"
    assert "db.internal" not in str(error.value)

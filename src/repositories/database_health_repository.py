from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncSession

from src.repositories.errors import DatabaseUnavailableError, open_connection, unavailable_kind


class DatabaseHealthRepository:
    """The trivial query of `/health/ready` (contracts/health-v1.md).

    Two phases, so the kind of failure can be told: getting the connection (any failure is
    `connection_error`) and running `SELECT 1` (a lost connection is `connection_error`, a cancelled
    statement `timeout`, anything else `unexpected_error`). The time limit is the caller's.
    """

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def ping(self) -> None:
        await open_connection(self._session)
        try:
            await self._session.execute(text("SELECT 1"))
        except DBAPIError as error:
            raise DatabaseUnavailableError(unavailable_kind(error) or "unexpected_error") from None
        except Exception:
            raise DatabaseUnavailableError("unexpected_error") from None

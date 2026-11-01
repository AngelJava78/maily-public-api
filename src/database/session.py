"""Read-only access to the shared database (research R4).

Three independent layers make a write impossible even if one fails: the grants of the database user
(docs/database/read-only-role.sql), the `READ ONLY` transactions this module asks for, and the
`default_transaction_read_only` of the session. `statement_timeout` stops a query on the server; the
Services add `asyncio.timeout` for what the server cannot see (a connection that never opens).
"""

from collections.abc import AsyncIterator

from fastapi import Request
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from src.config import SERVICE_NAME, Settings

# At most 10 connections per replica to the shared database (the role has CONNECTION LIMIT 12).
POOL_SIZE = 5
MAX_OVERFLOW = 5


def create_engine(settings: Settings) -> AsyncEngine:
    """Build the engine. It opens no connection until the first query."""
    timeout = settings.database_query_timeout_seconds
    return create_async_engine(
        settings.database_url,
        pool_pre_ping=True,
        pool_size=POOL_SIZE,
        max_overflow=MAX_OVERFLOW,
        # Every transaction is `BEGIN ISOLATION LEVEL REPEATABLE READ READ ONLY`: the queries of one
        # catalog read see the same snapshot, and a read-only transaction never fails to serialize.
        isolation_level="REPEATABLE READ",
        execution_options={"postgresql_readonly": True},
        connect_args={
            "timeout": timeout,
            "server_settings": {
                "application_name": SERVICE_NAME,
                "default_transaction_read_only": "on",
                "statement_timeout": str(int(timeout * 1000)),
            },
        },
    )


def create_session_factory(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(engine, expire_on_commit=False)


async def get_session(request: Request) -> AsyncIterator[AsyncSession]:
    """FastAPI dependency: one session per request, closed (and its transaction rolled back) at the end."""
    async with request.app.state.session_factory() as session:
        yield session

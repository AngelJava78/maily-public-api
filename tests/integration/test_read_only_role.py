"""The read-only role cannot write (SC-004) and only reads what it was granted (FR-025). Slow."""

from collections.abc import AsyncIterator

import asyncpg
import pytest
import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import AsyncEngine

ROLE = "maily_public_api"


@pytest_asyncio.fixture
async def as_reader(database_ready: str) -> AsyncIterator[asyncpg.Connection]:
    dsn = make_url(database_ready).set(drivername="postgresql").render_as_string(hide_password=False)
    connection = await asyncpg.connect(dsn)
    yield connection
    await connection.close()


@pytest.mark.parametrize(
    "statement",
    [
        "INSERT INTO subscriptions (name) VALUES ('x')",
        "UPDATE subscriptions SET name = name WHERE false",
        "DELETE FROM subscriptions WHERE false",
        "INSERT INTO modules (key, name, type_id) VALUES ('x', 'x', 2)",
        "TRUNCATE subscription_modules",
    ],
)
async def test_writes_are_rejected_even_in_a_read_write_transaction(
    as_reader: asyncpg.Connection, statement: str
) -> None:
    await as_reader.execute("BEGIN READ WRITE")
    try:
        with pytest.raises(asyncpg.InsufficientPrivilegeError):
            await as_reader.execute(statement)
    finally:
        await as_reader.execute("ROLLBACK")


@pytest.mark.parametrize(
    "query",
    ["SELECT updated_at FROM subscriptions", "SELECT 1 FROM subscription_statuses", "SELECT id FROM modules"],
)
async def test_what_was_not_granted_cannot_be_read(as_reader: asyncpg.Connection, query: str) -> None:
    with pytest.raises(asyncpg.InsufficientPrivilegeError):
        await as_reader.fetch(query)


async def test_transactions_are_read_only_by_default(as_reader: asyncpg.Connection) -> None:
    assert await as_reader.fetchval("SHOW default_transaction_read_only") == "on"


async def test_attributes_and_grants_of_the_role(admin_engine: AsyncEngine) -> None:
    async with admin_engine.connect() as connection:
        role = (
            await connection.execute(
                text(
                    "SELECT rolsuper, rolcreatedb, rolcreaterole, rolreplication, rolbypassrls,"
                    " rolconnlimit FROM pg_roles WHERE rolname = :role"
                ),
                {"role": ROLE},
            )
        ).one()
        memberships = (
            await connection.execute(
                text("SELECT count(*) FROM pg_auth_members WHERE member = CAST(:role AS regrole)"),
                {"role": ROLE},
            )
        ).scalar_one()
        grants = (
            await connection.execute(
                text(
                    "SELECT table_name, column_name, privilege_type"
                    " FROM information_schema.column_privileges WHERE grantee = :role"
                ),
                {"role": ROLE},
            )
        ).all()
        table_grants = (
            await connection.execute(
                text(
                    "SELECT count(*) FROM information_schema.table_privileges"
                    " WHERE grantee = :role AND privilege_type <> 'SELECT'"
                ),
                {"role": ROLE},
            )
        ).scalar_one()

    assert tuple(role) == (False, False, False, False, False, 12)
    assert memberships == 0
    assert len(grants) == 25
    assert {privilege for _, _, privilege in grants} == {"SELECT"}
    assert {table for table, _, _ in grants} == {
        "subscriptions",
        "subscription_types",
        "subscription_modules",
        "modules",
    }
    assert table_grants == 0

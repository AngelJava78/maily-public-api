"""`ModuleRepository` against PostgreSQL 18, reading as the read-only role (slow)."""

from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from src.repositories.module_repository import ModuleRepository
from tests.integration.seed import insert_module

ACTIVE, BLOCKED, DELETED = 1, 2, 3
SYSTEM, CLINIC = 1, 2


async def keys_found(session: AsyncSession, keys: list[str]) -> list[str]:
    modules = await ModuleRepository(session).list_by_keys(keys, status_id=ACTIVE, type_id=CLINIC)
    return sorted(module.key for module in modules)


async def test_only_active_clinic_modules(admin_engine: AsyncEngine, reader_session: AsyncSession) -> None:
    async with admin_engine.begin() as connection:
        await insert_module(connection, "patients", "Pacientes", sort_order=1)
        await insert_module(connection, "blocked_one", "Bloqueado", status_id=BLOCKED)
        await insert_module(connection, "deleted_one", "Eliminado", status_id=DELETED)
        await insert_module(connection, "users_admin", "Usuarios", type_id=SYSTEM)

    keys = ["patients", "blocked_one", "deleted_one", "users_admin", "missing"]

    assert await keys_found(reader_session, keys) == ["patients"]


async def test_name_and_sort_order_are_read(
    admin_engine: AsyncEngine, reader_session: AsyncSession
) -> None:
    async with admin_engine.begin() as connection:
        await insert_module(connection, "scheduling", "Agenda", sort_order=7)

    [module] = await ModuleRepository(reader_session).list_by_keys(["scheduling"], ACTIVE, CLINIC)

    assert (module.key, module.name, module.sort_order) == ("scheduling", "Agenda", 7)


async def test_a_deleted_duplicate_key_is_ignored(
    admin_engine: AsyncEngine, reader_session: AsyncSession
) -> None:
    async with admin_engine.begin() as connection:
        await insert_module(connection, "reminders", "Recordatorios viejos", status_id=DELETED)
        await insert_module(connection, "reminders", "Recordatorios")

    [module] = await ModuleRepository(reader_session).list_by_keys(["reminders"], ACTIVE, CLINIC)

    assert module.name == "Recordatorios"


async def test_no_keys_no_query(reader_session: AsyncSession) -> None:
    assert await ModuleRepository(reader_session).list_by_keys([], ACTIVE, CLINIC) == []

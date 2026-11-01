from collections.abc import Collection

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models import Module
from src.repositories.errors import open_connection, unavailable_on_failure


class ModuleRepository:
    """Reads the module catalog. Which modules may be published comes from the Service."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def list_by_keys(self, keys: Collection[str], status_id: int, type_id: int) -> list[Module]:
        """The modules with one of `keys` and that status and type (unordered)."""
        if not keys:
            return []
        await open_connection(self._session)
        statement = select(Module).where(
            Module.key.in_(list(keys)), Module.status_id == status_id, Module.type_id == type_id
        )
        with unavailable_on_failure():
            return list(await self._session.scalars(statement))

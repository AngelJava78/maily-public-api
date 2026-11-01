from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload, selectinload

from src.models import Subscription
from src.repositories.errors import open_connection, unavailable_on_failure


class SubscriptionRepository:
    """Reads the subscriptions. The publication criterion comes from the Service (Principle I)."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def list_by_publication(self, status_id: int, self_service: bool) -> list[Subscription]:
        """The subscriptions with that status and self-service, oldest first (FR-006).

        The filter runs in the query: the rows that are not public are never loaded (FR-005).
        """
        await open_connection(self._session)
        statement = (
            select(Subscription)
            .where(Subscription.status_id == status_id, Subscription.self_service == self_service)
            .order_by(Subscription.created_at, Subscription.id)
            .options(
                joinedload(Subscription.subscription_type),
                selectinload(Subscription.modules),
            )
        )
        with unavailable_on_failure():
            result = await self._session.scalars(statement)
            return list(result.unique())

"""The public catalog of subscriptions: which ones are published and how (FR-004 to FR-012)."""

import asyncio
import logging
from collections.abc import Hashable

from src.dtos.subscription import ModuleRead, PublicSubscriptionRead, SubscriptionTypeRead
from src.exceptions import ServiceUnavailableError
from src.models import Module, Subscription
from src.repositories.errors import DatabaseUnavailableError
from src.repositories.module_repository import ModuleRepository
from src.repositories.subscription_repository import SubscriptionRepository

logger = logging.getLogger(__name__)

# Publication criterion (FR-004): Active (status 1, by identifier) and self-service.
ACTIVE_STATUS_ID = 1
PUBLIC_SELF_SERVICE = True
# Modules that may be shown by name (FR-011): Active (status 1) and of type Clinic (type 2).
ACTIVE_MODULE_STATUS_ID = 1
CLINIC_MODULE_TYPE_ID = 2
# Above this size the catalog must be paginated in a new version of the contract (FR-007).
CATALOG_MAX_EXPECTED = 500


class OncePerProcess:
    """Remembers what was already logged, so a warning is not repeated on every request (research R7).

    Bounded: beyond `capacity` keys it stops remembering (it may repeat a warning, it never grows).
    """

    def __init__(self, capacity: int = 1000) -> None:
        self._capacity = capacity
        self._seen: set[Hashable] = set()

    def first_time(self, key: Hashable) -> bool:
        if key in self._seen:
            return False
        if len(self._seen) < self._capacity:
            self._seen.add(key)
        return True


_once = OncePerProcess()


class SubscriptionCatalogService:
    def __init__(
        self,
        subscriptions: SubscriptionRepository,
        modules: ModuleRepository,
        query_timeout_seconds: float,
    ) -> None:
        self._subscriptions = subscriptions
        self._modules = modules
        self._timeout = query_timeout_seconds

    async def list_catalog(self) -> list[PublicSubscriptionRead]:
        """The whole public catalog, or `ServiceUnavailableError` within the time limit (FR-015)."""
        try:
            async with asyncio.timeout(self._timeout):
                subscriptions = await self._subscriptions.list_by_publication(
                    status_id=ACTIVE_STATUS_ID, self_service=PUBLIC_SELF_SERVICE
                )
                keys = sorted({key for subscription in subscriptions for key in subscription.module_keys})
                modules = await self._modules.list_by_keys(
                    keys, status_id=ACTIVE_MODULE_STATUS_ID, type_id=CLINIC_MODULE_TYPE_ID
                )
        except (TimeoutError, DatabaseUnavailableError):
            raise ServiceUnavailableError() from None

        if len(subscriptions) > CATALOG_MAX_EXPECTED and _once.first_time("catalog_size"):
            logger.warning(
                "The public catalog has %d subscriptions, more than the %d the contract returns "
                "without pagination; all are returned, but a paginated version is due (FR-007)",
                len(subscriptions),
                CATALOG_MAX_EXPECTED,
            )
        by_key = {module.key: module for module in modules}
        return [self._to_public(subscription, by_key) for subscription in subscriptions]

    def _to_public(
        self, subscription: Subscription, modules_by_key: dict[str, Module]
    ) -> PublicSubscriptionRead:
        published = []
        for key in subscription.module_keys:
            module = modules_by_key.get(key)
            if module is not None:
                published.append(module)
            elif _once.first_time(("module", subscription.id, key)):
                # FR-012: the plan is still published; someone must fix the module catalog.
                logger.warning(
                    "Subscription %s includes the module key %r, which is not an Active module of "
                    "type Clinic: it is left out of `modules`",
                    subscription.id,
                    key,
                )
        published.sort(key=lambda module: (module.sort_order, module.key))

        return PublicSubscriptionRead(
            id=subscription.id,
            name=subscription.name,
            description=subscription.description,
            subscription_type=SubscriptionTypeRead.model_validate(subscription.subscription_type),
            monthly_price=subscription.monthly_price,
            annual_price=subscription.annual_price,
            trial_days=subscription.trial_days,
            module_keys=subscription.module_keys,
            modules=[ModuleRead(key=module.key, name=module.name) for module in published],
            other_features=subscription.other_features,
            consulting_rooms_limit=subscription.consulting_rooms_limit,
            doctors_limit=subscription.doctors_limit,
            assistants_limit=subscription.assistants_limit,
            new_patients_per_year_limit=subscription.new_patients_per_year_limit,
            clinics_limit=subscription.clinics_limit,
        )

from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.models.base import Base

if TYPE_CHECKING:
    from src.models.subscription_module import SubscriptionModule
    from src.models.subscription_type import SubscriptionType


class Subscription(Base):
    """A subscription (plan) as maily-system-api stores it.

    Only the 16 columns the read-only role may read (docs/database/read-only-role.sql) are mapped:
    selecting any other one would fail with a permission error. `status_id`, `self_service` and
    `created_at` are read for the filter and the order and never published (FR-010).
    """

    __tablename__ = "subscriptions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(100))
    description: Mapped[str | None] = mapped_column(String(500))
    subscription_type_id: Mapped[int] = mapped_column(Integer, ForeignKey("subscription_types.id"))
    # Mexican pesos, never float (Principle VI).
    monthly_price: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    annual_price: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    trial_days: Mapped[int] = mapped_column(Integer)
    other_features: Mapped[list[str]] = mapped_column(ARRAY(Text))
    consulting_rooms_limit: Mapped[int] = mapped_column(Integer)
    doctors_limit: Mapped[int] = mapped_column(Integer)
    assistants_limit: Mapped[int] = mapped_column(Integer)
    new_patients_per_year_limit: Mapped[int] = mapped_column(Integer)
    clinics_limit: Mapped[int] = mapped_column(Integer)
    # 1 = Active (recognised by its identifier, never by its name).
    status_id: Mapped[int] = mapped_column(Integer)
    self_service: Mapped[bool] = mapped_column(Boolean)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))

    # lazy="raise": an AsyncSession has no implicit loads; the Repository loads both explicitly.
    subscription_type: Mapped["SubscriptionType"] = relationship(lazy="raise")
    # Ordered by the database with the same expression as maily-system-api, so `module_keys` comes in
    # the same order under the same collation (research R6).
    modules: Mapped[list["SubscriptionModule"]] = relationship(
        lazy="raise", order_by="SubscriptionModule.module_key"
    )

    @property
    def module_keys(self) -> list[str]:
        return [module.module_key for module in self.modules]

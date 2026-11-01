from sqlalchemy import ForeignKey, Integer, Text
from sqlalchemy.orm import Mapped, mapped_column

from src.models.base import Base


class SubscriptionModule(Base):
    """One module key included in a subscription (written by maily-system-api)."""

    __tablename__ = "subscription_modules"

    subscription_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("subscriptions.id"), primary_key=True
    )
    module_key: Mapped[str] = mapped_column(Text, primary_key=True)

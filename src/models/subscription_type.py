from sqlalchemy import Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from src.models.base import Base


class SubscriptionType(Base):
    """Who a subscription is for (today 1 Individual, 2 Empresarial). Only the granted columns."""

    __tablename__ = "subscription_types"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(50))

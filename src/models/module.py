from sqlalchemy import Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from src.models.base import Base


class Module(Base):
    """A module of the catalog the users service manages. Only the granted columns: no `id`.

    `key` is the primary key of the mapping only (research R6): it is unique among the modules that
    are not Deleted (index `modules_key_not_deleted_key`) and only Active modules are ever read.
    """

    __tablename__ = "modules"

    key: Mapped[str] = mapped_column(String(50), primary_key=True)
    name: Mapped[str] = mapped_column(String(100))
    sort_order: Mapped[int] = mapped_column(Integer)
    # 1 = Active, 2 = Blocked, 3 = Deleted; type 1 = System, 2 = Clinic (by identifier).
    status_id: Mapped[int] = mapped_column(Integer)
    type_id: Mapped[int] = mapped_column(Integer)

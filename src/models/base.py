from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """Base of the ORM models. They map tables of the shared database (schema owned by mailySoft-DB)
    and are only read: this service never creates, alters or writes a table (Principle VI)."""

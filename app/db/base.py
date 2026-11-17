from typing import ClassVar

from sqlalchemy import MetaData, event
from sqlalchemy.orm import DeclarativeBase

NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=NAMING_CONVENTION)

    # Si no se configura, usamos el nombre de la tabla.
    __permission_resource__: ClassVar[str | None] = None

    # Acciones predeterminadas para todos los modelos.
    __permission_actions__: ClassVar[tuple[str, ...]] = (
        "read",
        "create",
        "update",
        "delete",
    )


@event.listens_for(Base, "before_insert", propagate=True)
@event.listens_for(Base, "before_update", propagate=True)
def uppercase_display_fields(mapper, connection, target) -> None:
    """Normalizar texto visible y username sin modificar contraseñas ni códigos."""
    for field in ("username", "name", "last_name", "description"):
        if field in mapper.column_attrs:
            value = getattr(target, field)
            if isinstance(value, str):
                setattr(target, field, value.strip().upper())

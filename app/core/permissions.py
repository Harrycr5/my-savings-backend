import logging
import re
from uuid import uuid4

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.engine import Connection

from app.db.base import Base

logger = logging.getLogger("alembic.permissions")

VALID_IDENTIFIER = re.compile(r"^[a-z][a-z0-9_]*$")

ACTION_LABELS = {
    "read": "Consultar",
    "create": "Crear",
    "update": "Actualizar",
    "delete": "Eliminar",
}


def get_permission_definitions() -> list[dict[str, str]]:
    definitions: dict[str, dict[str, str]] = {}

    for mapper in Base.registry.mappers:
        model = mapper.class_

        resource = getattr(model, "__permission_resource__", None) or mapper.local_table.name

        actions = getattr(model, "__permission_actions__", ())

        # Permite excluir un modelo con una tupla vacía.
        if not actions:
            continue

        if not VALID_IDENTIFIER.fullmatch(resource):
            raise ValueError(f"Recurso de permisos inválido en {model.__name__}: {resource!r}")

        for action in actions:
            if not VALID_IDENTIFIER.fullmatch(action):
                raise ValueError(f"Acción de permisos inválida en {model.__name__}: {action!r}")

            code = f"{resource}.{action}"

            if len(code) > 100:
                raise ValueError(f"El código de permiso supera 100 caracteres: {code}")

            label = ACTION_LABELS.get(
                action,
                action.replace("_", " ").capitalize(),
            )

            definitions[code] = {
                "code": code,
                "name": f"{label} {resource}".upper()[:100],
                "description": f"Permite ejecutar la acción '{action}' sobre '{resource}'.".upper(),
            }

    return [definitions[code] for code in sorted(definitions)]


def sync_model_permissions(connection: Connection) -> None:
    definitions = get_permission_definitions()

    if not definitions:
        return

    permissions = sa.Table(
        "permissions",
        sa.MetaData(),
        sa.Column("id", sa.Uuid(as_uuid=True)),
        sa.Column("code", sa.String(100)),
        sa.Column("name", sa.String(100)),
        sa.Column("description", sa.String(255)),
    )

    inserted_count = 0

    # Insertar por bloques para admitir catálogos grandes.
    for start in range(0, len(definitions), 500):
        batch = definitions[start : start + 500]

        rows = [
            {
                "id": uuid4(),
                **definition,
            }
            for definition in batch
        ]

        statement = (
            insert(permissions)
            .values(rows)
            .on_conflict_do_nothing(index_elements=["code"])
            .returning(permissions.c.code)
        )

        result = connection.execute(statement)
        inserted_count += len(result.scalars().all())

    logger.info(
        "Catálogo de permisos sincronizado: %s nuevos.",
        inserted_count,
    )

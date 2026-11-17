"""Grant the basic profile access to personal modules."""

from uuid import uuid4

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import insert

revision = "c6e7d9b812f0"
down_revision = "a7d92c5e1048"
branch_labels = None
depends_on = None

PERSONAL_ACTIONS = {
    "tills": ("read", "create", "update"),
    "till_concepts": ("read", "create"),
    "till_movements": ("read", "create"),
    "debts": ("read", "create", "update"),
    "debt_payments": ("read", "create"),
    "inheritance_assets": ("read", "create", "update", "delete"),
    "users": ("me",),
}
ACTION_LABELS = {
    "read": "Consultar",
    "create": "Crear",
    "update": "Actualizar",
    "delete": "Eliminar",
    "me": "Consultar y actualizar la cuenta propia",
}


def upgrade() -> None:
    permissions = sa.table(
        "permissions",
        sa.column("id", sa.Uuid()),
        sa.column("code", sa.String()),
        sa.column("name", sa.String()),
        sa.column("description", sa.String()),
    )
    profiles = sa.table("profiles", sa.column("id", sa.Uuid()), sa.column("code", sa.String()))
    grants = sa.table(
        "profile_permissions",
        sa.column("profile_id", sa.Uuid()),
        sa.column("permission_id", sa.Uuid()),
    )

    rows = [
        {
            "id": uuid4(),
            "code": f"{resource}.{action}",
            "name": f"{ACTION_LABELS[action]} {resource}".upper(),
            "description": f"Permite ejecutar la accion '{action}' sobre '{resource}'.".upper(),
        }
        for resource, actions in PERSONAL_ACTIONS.items()
        for action in actions
    ]
    op.execute(insert(permissions).values(rows).on_conflict_do_nothing(index_elements=["code"]))
    basic_permissions = (
        sa.select(profiles.c.id, permissions.c.id)
        .select_from(profiles.join(permissions, sa.true()))
        .where(profiles.c.code == "user", permissions.c.code.in_([row["code"] for row in rows]))
    )
    op.execute(
        insert(grants)
        .from_select(["profile_id", "permission_id"], basic_permissions)
        .on_conflict_do_nothing(index_elements=["profile_id", "permission_id"])
    )


def downgrade() -> None:
    # Preserve grants that could have been assigned before this migration.
    pass

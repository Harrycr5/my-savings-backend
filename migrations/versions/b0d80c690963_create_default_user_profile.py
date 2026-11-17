"""create default user profile

Revision ID: b0d80c690963
Revises: 911b7d3f0603
"""

from uuid import UUID

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import insert

revision = "b0d80c690963"
down_revision = "911b7d3f0603"
branch_labels = None
depends_on = None


DEFAULT_PROFILE_ID = UUID("58e28fc8-5397-4b15-93ac-5347b7b68d05")

profiles = sa.table(
    "profiles",
    sa.column("id", sa.Uuid(as_uuid=True)),
    sa.column("code", sa.String(50)),
    sa.column("name", sa.String(100)),
    sa.column("description", sa.String(255)),
    sa.column("is_active", sa.Boolean()),
)


def upgrade() -> None:
    statement = (
        insert(profiles)
        .values(
            id=DEFAULT_PROFILE_ID,
            code="user",
            name="Básico",
            description="Perfil Predeterminado para usuarios registrados.",
            is_active=True,
        )
        .on_conflict_do_nothing(index_elements=["code"])
    )

    op.execute(statement)


def downgrade() -> None:
    op.execute(
        profiles.delete().where(
            profiles.c.id == DEFAULT_PROFILE_ID,
            profiles.c.code == "user",
        )
    )

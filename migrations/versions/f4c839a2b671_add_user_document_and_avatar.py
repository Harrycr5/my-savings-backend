"""Add document number and profile picture URL to users.

Revision ID: f4c839a2b671
Revises: e3b426c8ad51
"""

import sqlalchemy as sa
from alembic import op

revision = "f4c839a2b671"
down_revision = "e3b426c8ad51"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("doc_number", sa.String(8), nullable=True))
    op.add_column("users", sa.Column("avatar_url", sa.String(255), nullable=True))
    op.create_unique_constraint(op.f("uq_users_doc_number"), "users", ["doc_number"])


def downgrade() -> None:
    op.drop_constraint(op.f("uq_users_doc_number"), "users", type_="unique")
    op.drop_column("users", "avatar_url")
    op.drop_column("users", "doc_number")

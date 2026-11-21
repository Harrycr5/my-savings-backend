"""Create the idempotency table for till movements."""

import sqlalchemy as sa
from alembic import op

revision = "6d3ce54ce4a8"
down_revision = "c6e7d9b812f0"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "till_movement_requests",
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("key", sa.String(128), nullable=False),
        sa.Column("request_fingerprint", sa.String(64), nullable=False),
        sa.Column("status", sa.String(10), nullable=False),
        sa.Column("movement_id", sa.Uuid(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.PrimaryKeyConstraint("user_id", "key"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["movement_id"], ["till_movements.id"], ondelete="RESTRICT"),
        sa.CheckConstraint(
            "(status = 'processing' AND movement_id IS NULL) OR "
            "(status = 'completed' AND movement_id IS NOT NULL)",
            name="valid_status",
        ),
    )


def downgrade() -> None:
    op.drop_table("till_movement_requests")

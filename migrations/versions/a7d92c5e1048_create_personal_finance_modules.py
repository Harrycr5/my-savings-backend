"""Create permanent tills, concepts, movements, recurring debts and assets.

Revision ID: a7d92c5e1048
Revises: f4c839a2b671
"""

import sqlalchemy as sa
from alembic import op

revision = "a7d92c5e1048"
down_revision = "f4c839a2b671"
branch_labels = None
depends_on = None


def base_columns():
    return [
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    ]


def upgrade() -> None:
    op.create_table(
        "tills",
        *base_columns(),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("description", sa.String(500), nullable=True),
        sa.Column("currency", sa.String(3), nullable=False),
        sa.Column("opening_balance", sa.Numeric(18, 2), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_tills")),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], ondelete="RESTRICT", name=op.f("fk_tills_user_id_users")
        ),
        sa.CheckConstraint(
            "opening_balance >= 0", name=op.f("ck_tills_opening_balance_nonnegative")
        ),
    )
    op.create_index("ix_tills_user_id", "tills", ["user_id"])
    op.create_table(
        "till_concepts",
        *base_columns(),
        sa.Column("till_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("direction", sa.String(7), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_till_concepts")),
        sa.ForeignKeyConstraint(
            ["till_id"],
            ["tills.id"],
            ondelete="RESTRICT",
            name=op.f("fk_till_concepts_till_id_tills"),
        ),
        sa.CheckConstraint(
            "direction IN ('income', 'expense')", name=op.f("ck_till_concepts_valid_direction")
        ),
        sa.UniqueConstraint("till_id", "direction", "name", name=op.f("uq_till_concepts_till_id")),
        sa.UniqueConstraint("id", "till_id", "direction", name=op.f("uq_till_concepts_id")),
    )
    op.create_index("ix_till_concepts_till_id", "till_concepts", ["till_id"])
    op.create_table(
        "till_movements",
        *base_columns(),
        sa.Column("till_id", sa.Uuid(), nullable=False),
        sa.Column("concept_id", sa.Uuid(), nullable=False),
        sa.Column("direction", sa.String(7), nullable=False),
        sa.Column("amount", sa.Numeric(18, 2), nullable=False),
        sa.Column("occurred_on", sa.Date(), nullable=False),
        sa.Column("description", sa.String(500), nullable=True),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_till_movements")),
        sa.ForeignKeyConstraint(
            ["till_id"],
            ["tills.id"],
            ondelete="RESTRICT",
            name=op.f("fk_till_movements_till_id_tills"),
        ),
        sa.ForeignKeyConstraint(
            ["concept_id", "till_id", "direction"],
            ["till_concepts.id", "till_concepts.till_id", "till_concepts.direction"],
            ondelete="RESTRICT",
            name=op.f("fk_till_movements_concept_id_till_concepts"),
        ),
        sa.CheckConstraint("amount > 0", name=op.f("ck_till_movements_positive_amount")),
        sa.CheckConstraint(
            "direction IN ('income', 'expense')", name=op.f("ck_till_movements_valid_direction")
        ),
    )
    op.create_index("ix_till_movements_till_id", "till_movements", ["till_id"])
    op.create_index("ix_till_movements_occurred_on", "till_movements", ["occurred_on"])
    op.create_table(
        "debts",
        *base_columns(),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("description", sa.String(500), nullable=True),
        sa.Column("amount", sa.Numeric(18, 2), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False),
        sa.Column("frequency", sa.String(7), nullable=False),
        sa.Column("interval", sa.Integer(), nullable=False),
        sa.Column("first_due_date", sa.Date(), nullable=False),
        sa.Column("next_due_date", sa.Date(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_debts")),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], ondelete="RESTRICT", name=op.f("fk_debts_user_id_users")
        ),
        sa.CheckConstraint("amount > 0", name=op.f("ck_debts_positive_amount")),
        sa.CheckConstraint("interval >= 1", name=op.f("ck_debts_positive_interval")),
        sa.CheckConstraint(
            "frequency IN ('once', 'daily', 'weekly', 'monthly', 'yearly')",
            name=op.f("ck_debts_valid_frequency"),
        ),
    )
    op.create_index("ix_debts_user_id", "debts", ["user_id"])
    op.create_index("ix_debts_next_due_date", "debts", ["next_due_date"])
    op.create_table(
        "debt_payments",
        *base_columns(),
        sa.Column("debt_id", sa.Uuid(), nullable=False),
        sa.Column("movement_id", sa.Uuid(), nullable=False),
        sa.Column("due_date", sa.Date(), nullable=False),
        sa.Column("paid_on", sa.Date(), nullable=False),
        sa.Column("amount", sa.Numeric(18, 2), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_debt_payments")),
        sa.ForeignKeyConstraint(
            ["debt_id"],
            ["debts.id"],
            ondelete="RESTRICT",
            name=op.f("fk_debt_payments_debt_id_debts"),
        ),
        sa.ForeignKeyConstraint(
            ["movement_id"],
            ["till_movements.id"],
            ondelete="RESTRICT",
            name=op.f("fk_debt_payments_movement_id_till_movements"),
        ),
        sa.UniqueConstraint("debt_id", "due_date", name=op.f("uq_debt_payments_debt_id")),
        sa.UniqueConstraint("movement_id", name=op.f("uq_debt_payments_movement_id")),
    )
    op.create_index("ix_debt_payments_debt_id", "debt_payments", ["debt_id"])
    op.create_table(
        "inheritance_assets",
        *base_columns(),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("description", sa.String(500), nullable=True),
        sa.Column("asset_type", sa.String(8), nullable=False),
        sa.Column("other_type", sa.String(100), nullable=True),
        sa.Column("currency", sa.String(3), nullable=False),
        sa.Column("current_value", sa.Numeric(18, 2), nullable=False),
        sa.Column("market_value", sa.Numeric(18, 2), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_inheritance_assets")),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            ondelete="RESTRICT",
            name=op.f("fk_inheritance_assets_user_id_users"),
        ),
        sa.CheckConstraint(
            "asset_type IN ('property', 'vehicle', 'other')",
            name=op.f("ck_inheritance_assets_valid_asset_type"),
        ),
        sa.CheckConstraint(
            "current_value >= 0 AND market_value >= 0",
            name=op.f("ck_inheritance_assets_nonnegative_values"),
        ),
        sa.CheckConstraint(
            "asset_type != 'other' OR (other_type IS NOT NULL AND length(trim(other_type)) > 0)",
            name=op.f("ck_inheritance_assets_other_type_required"),
        ),
    )
    op.create_index("ix_inheritance_assets_user_id", "inheritance_assets", ["user_id"])


def downgrade() -> None:
    for table in (
        "inheritance_assets",
        "debt_payments",
        "debts",
        "till_movements",
        "till_concepts",
        "tills",
    ):
        op.drop_table(table)

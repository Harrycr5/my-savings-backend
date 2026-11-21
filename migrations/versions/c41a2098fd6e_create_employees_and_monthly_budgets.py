"""Create employee and monthly budget records."""

import sqlalchemy as sa
from alembic import op

revision = "c41a2098fd6e"
down_revision = "6d3ce54ce4a8"
branch_labels = None
depends_on = None


def record_columns():
    return (
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "user_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
        ),
        sa.Column("currency", sa.String(3), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )


def upgrade() -> None:
    op.create_table(
        "employees",
        *record_columns(),
        sa.Column("full_name", sa.String(100), nullable=False),
        sa.Column("salary", sa.Numeric(18, 2), nullable=False),
        sa.Column("first_pay_date", sa.Date(), nullable=False),
        sa.CheckConstraint("salary > 0", name="positive_salary"),
    )
    op.create_index("ix_employees_user_id", "employees", ["user_id"])
    op.create_table(
        "monthly_budgets",
        *record_columns(),
        sa.Column("year", sa.Integer(), nullable=False),
        sa.Column("month", sa.Integer(), nullable=False),
        sa.Column("leisure", sa.Numeric(18, 2), nullable=False),
        sa.Column("fixed_expenses", sa.Numeric(18, 2), nullable=False),
        sa.Column("food", sa.Numeric(18, 2), nullable=False),
        sa.Column("subscriptions", sa.Numeric(18, 2), nullable=False),
        sa.UniqueConstraint("user_id", "year", "month", name="uq_monthly_budgets_user_period"),
        sa.CheckConstraint(
            "year BETWEEN 1 AND 9999 AND month BETWEEN 1 AND 12", name="valid_period"
        ),
        sa.CheckConstraint(
            "leisure >= 0 AND fixed_expenses >= 0 AND food >= 0 AND subscriptions >= 0",
            name="nonnegative_amounts",
        ),
    )


def downgrade() -> None:
    op.drop_table("monthly_budgets")
    op.drop_index("ix_employees_user_id", table_name="employees")
    op.drop_table("employees")

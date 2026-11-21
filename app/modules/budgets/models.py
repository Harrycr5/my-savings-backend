from decimal import Decimal
from uuid import UUID

from sqlalchemy import CheckConstraint, ForeignKey, Numeric, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.mixins import TimestampMixin, UUIDMixin


class MonthlyBudget(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "monthly_budgets"
    __table_args__ = (
        UniqueConstraint("user_id", "year", "month", name="uq_monthly_budgets_user_period"),
        CheckConstraint("year BETWEEN 1 AND 9999 AND month BETWEEN 1 AND 12", name="valid_period"),
        CheckConstraint(
            "leisure >= 0 AND fixed_expenses >= 0 AND food >= 0 AND subscriptions >= 0",
            name="nonnegative_amounts",
        ),
    )

    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    year: Mapped[int]
    month: Mapped[int]
    currency: Mapped[str] = mapped_column(ForeignKey("currencies.code", ondelete="RESTRICT"))
    leisure: Mapped[Decimal] = mapped_column(Numeric(18, 2))
    fixed_expenses: Mapped[Decimal] = mapped_column(Numeric(18, 2))
    food: Mapped[Decimal] = mapped_column(Numeric(18, 2))
    subscriptions: Mapped[Decimal] = mapped_column(Numeric(18, 2))

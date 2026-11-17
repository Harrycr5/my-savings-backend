from datetime import date
from decimal import Decimal
from uuid import UUID

from sqlalchemy import Boolean, CheckConstraint, Date, ForeignKey, Numeric, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.mixins import TimestampMixin, UUIDMixin


class Debt(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "debts"
    __table_args__ = (
        CheckConstraint("amount > 0", name="positive_amount"),
        CheckConstraint("interval >= 1", name="positive_interval"),
        CheckConstraint(
            "frequency IN ('once', 'daily', 'weekly', 'monthly', 'yearly')",
            name="valid_frequency",
        ),
    )

    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), index=True)
    name: Mapped[str] = mapped_column(String(100))
    description: Mapped[str | None] = mapped_column(String(500))
    amount: Mapped[Decimal] = mapped_column(Numeric(18, 2))
    currency: Mapped[str] = mapped_column(String(3))
    frequency: Mapped[str] = mapped_column(String(7))
    interval: Mapped[int] = mapped_column(default=1)
    first_due_date: Mapped[date] = mapped_column(Date)
    next_due_date: Mapped[date | None] = mapped_column(Date, index=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class DebtPayment(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "debt_payments"
    __table_args__ = (
        UniqueConstraint("debt_id", "due_date"),
        UniqueConstraint("movement_id"),
    )

    debt_id: Mapped[UUID] = mapped_column(ForeignKey("debts.id", ondelete="RESTRICT"), index=True)
    movement_id: Mapped[UUID] = mapped_column(ForeignKey("till_movements.id", ondelete="RESTRICT"))
    due_date: Mapped[date] = mapped_column(Date)
    paid_on: Mapped[date] = mapped_column(Date)
    amount: Mapped[Decimal] = mapped_column(Numeric(18, 2))
    currency: Mapped[str] = mapped_column(String(3))

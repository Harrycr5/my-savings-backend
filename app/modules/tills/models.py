from datetime import date
from decimal import Decimal
from typing import ClassVar
from uuid import UUID

from sqlalchemy import (
    CheckConstraint,
    Date,
    ForeignKey,
    ForeignKeyConstraint,
    Numeric,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.mixins import TimestampMixin, UUIDMixin


class Till(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "tills"
    __table_args__ = (CheckConstraint("opening_balance >= 0", name="opening_balance_nonnegative"),)

    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), index=True)
    name: Mapped[str] = mapped_column(String(100))
    description: Mapped[str | None] = mapped_column(String(500))
    currency: Mapped[str] = mapped_column(ForeignKey("currencies.code", ondelete="RESTRICT"))
    opening_balance: Mapped[Decimal] = mapped_column(Numeric(18, 2), default=Decimal("0"))


class TillConcept(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "till_concepts"
    __table_args__ = (
        CheckConstraint("direction IN ('income', 'expense')", name="valid_direction"),
        UniqueConstraint("till_id", "direction", "name"),
        UniqueConstraint("id", "till_id", "direction"),
    )

    till_id: Mapped[UUID] = mapped_column(ForeignKey("tills.id", ondelete="RESTRICT"), index=True)
    name: Mapped[str] = mapped_column(String(100))
    direction: Mapped[str] = mapped_column(String(7))


class TillMovement(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "till_movements"
    __table_args__ = (
        CheckConstraint("amount > 0", name="positive_amount"),
        CheckConstraint("direction IN ('income', 'expense')", name="valid_direction"),
        ForeignKeyConstraint(
            ["concept_id", "till_id", "direction"],
            ["till_concepts.id", "till_concepts.till_id", "till_concepts.direction"],
            ondelete="RESTRICT",
        ),
    )

    till_id: Mapped[UUID] = mapped_column(ForeignKey("tills.id", ondelete="RESTRICT"), index=True)
    concept_id: Mapped[UUID]
    direction: Mapped[str] = mapped_column(String(7))
    amount: Mapped[Decimal] = mapped_column(Numeric(18, 2))
    occurred_on: Mapped[date] = mapped_column(Date, index=True)
    description: Mapped[str | None] = mapped_column(String(500))


class TillMovementRequest(TimestampMixin, Base):
    __tablename__ = "till_movement_requests"
    __permission_actions__: ClassVar[tuple[str, ...]] = ()
    __table_args__ = (
        CheckConstraint(
            "(status = 'processing' AND movement_id IS NULL) OR "
            "(status = 'completed' AND movement_id IS NOT NULL)",
            name="valid_status",
        ),
    )

    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), primary_key=True
    )
    key: Mapped[str] = mapped_column(String(128), primary_key=True)
    request_fingerprint: Mapped[str] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(10))
    movement_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("till_movements.id", ondelete="RESTRICT")
    )

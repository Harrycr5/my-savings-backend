from __future__ import annotations

from decimal import Decimal
from uuid import UUID

from sqlalchemy import CheckConstraint, ForeignKey, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.mixins import TimestampMixin, UUIDMixin


class Asset(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "inheritance_assets"
    __table_args__ = (
        CheckConstraint("asset_type IN ('property', 'vehicle', 'other')", name="valid_asset_type"),
        CheckConstraint("current_value >= 0 AND market_value >= 0", name="nonnegative_values"),
        CheckConstraint(
            "asset_type != 'other' OR (other_type IS NOT NULL AND length(trim(other_type)) > 0)",
            name="other_type_required",
        ),
    )

    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), index=True)
    name: Mapped[str] = mapped_column(String(100))
    description: Mapped[str | None] = mapped_column(String(500))
    asset_type: Mapped[str] = mapped_column(String(8))
    other_type: Mapped[str | None] = mapped_column(String(100))
    currency: Mapped[str] = mapped_column(String(3))
    current_value: Mapped[Decimal] = mapped_column(Numeric(18, 2))
    market_value: Mapped[Decimal] = mapped_column(Numeric(18, 2))

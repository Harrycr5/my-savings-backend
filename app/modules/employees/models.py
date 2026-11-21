from datetime import date
from decimal import Decimal
from uuid import UUID

from sqlalchemy import CheckConstraint, ForeignKey, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.mixins import TimestampMixin, UUIDMixin


class Employee(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "employees"
    __table_args__ = (CheckConstraint("salary > 0", name="positive_salary"),)

    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), index=True)
    full_name: Mapped[str] = mapped_column(String(100))
    salary: Mapped[Decimal] = mapped_column(Numeric(18, 2))
    currency: Mapped[str] = mapped_column(ForeignKey("currencies.code", ondelete="RESTRICT"))
    first_pay_date: Mapped[date]

from datetime import date
from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import Field

from app.core.finance import (
    Currency,
    Description,
    FinancialInput,
    FinancialPatch,
    FinancialRead,
    Name,
    PositiveMoney,
)
from app.core.pagination import PaginationParams

Frequency = Literal["once", "daily", "weekly", "monthly", "yearly"]


class DebtCreate(FinancialInput):
    name: Name
    description: Description | None = None
    amount: PositiveMoney
    currency: Currency = "PEN"
    frequency: Frequency = "monthly"
    interval: int = Field(default=1, ge=1, le=120)
    first_due_date: date


class DebtUpdate(FinancialPatch):
    name: Name | None = None
    description: Description | None = None
    amount: PositiveMoney | None = None
    is_active: bool | None = None


class DebtRead(FinancialRead):
    name: str
    description: str | None
    amount: Decimal
    currency: str
    frequency: Frequency
    interval: int
    first_due_date: date
    next_due_date: date | None
    is_active: bool


class DebtFilters(PaginationParams):
    is_active: bool | None = None
    due_before: date | None = None


class DebtPay(FinancialInput):
    till_id: UUID
    concept_id: UUID
    due_date: date = Field(
        description="Vencimiento que se paga; evita pagar la misma cuota dos veces."
    )
    paid_on: date = Field(default_factory=date.today)


class DebtPaymentRead(FinancialRead):
    debt_id: UUID
    movement_id: UUID
    due_date: date
    paid_on: date
    amount: Decimal
    currency: str

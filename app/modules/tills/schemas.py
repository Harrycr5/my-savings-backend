from datetime import date
from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import Field, model_validator

from app.core.finance import (
    Currency,
    Description,
    FinancialInput,
    FinancialPatch,
    FinancialRead,
    Money,
    Name,
    PositiveMoney,
)
from app.core.pagination import PaginationParams

Direction = Literal["income", "expense"]


class TillCreate(FinancialInput):
    name: Name
    description: Description | None = None
    currency: Currency = "PEN"
    opening_balance: Money = Decimal("0")


class TillUpdate(FinancialPatch):
    name: Name | None = None
    description: Description | None = None


class TillRead(FinancialRead):
    name: str
    description: str | None
    currency: str
    opening_balance: Decimal


class TillBalance(FinancialInput):
    till_id: UUID
    currency: str
    opening_balance: Decimal
    total_income: Decimal
    total_expense: Decimal
    balance: Decimal


class ConceptCreate(FinancialInput):
    name: Name
    direction: Direction


class TillSummary(FinancialInput):
    currency: str
    total_tills: int
    opening_balance: Decimal
    total_income: Decimal
    total_expense: Decimal
    net_savings: Decimal
    balance: Decimal


class ConceptRead(FinancialRead):
    till_id: UUID
    name: str
    direction: Direction


class MovementCreate(FinancialInput):
    concept_id: UUID
    amount: PositiveMoney
    occurred_on: date = Field(default_factory=date.today)
    description: Description | None = None


class MovementRead(FinancialRead):
    till_id: UUID
    concept_id: UUID
    direction: Direction
    amount: Decimal
    occurred_on: date
    description: str | None


class MovementFilters(PaginationParams):
    direction: Direction | None = None
    concept_id: UUID | None = None
    date_from: date | None = None
    date_to: date | None = None

    @model_validator(mode="after")
    def validate_dates(self):
        if self.date_from and self.date_to and self.date_from > self.date_to:
            raise ValueError("La fecha inicial no puede ser posterior a la final.")
        return self

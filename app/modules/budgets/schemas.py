from decimal import Decimal
from typing import Annotated

from pydantic import Field

from app.core.finance import Currency, FinancialInput, FinancialRead, Money


class MonthlyBudgetCreate(FinancialInput):
    year: Annotated[int, Field(strict=True, ge=1, le=9999)]
    month: Annotated[int, Field(strict=True, ge=1, le=12)]
    currency: Currency = "PEN"
    leisure: Money
    fixed_expenses: Money
    food: Money
    subscriptions: Money


class MonthlyBudgetRead(FinancialRead):
    year: int
    month: int
    currency: str
    leisure: Decimal
    fixed_expenses: Decimal
    food: Decimal
    subscriptions: Decimal

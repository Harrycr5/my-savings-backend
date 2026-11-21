from datetime import date
from decimal import Decimal

from app.core.finance import (
    Currency,
    FinancialInput,
    FinancialPatch,
    FinancialRead,
    Name,
    PositiveMoney,
)


class EmployeeCreate(FinancialInput):
    full_name: Name
    salary: PositiveMoney
    currency: Currency = "PEN"
    first_pay_date: date


class EmployeeUpdate(FinancialPatch):
    full_name: Name | None = None
    salary: PositiveMoney | None = None
    currency: Currency | None = None
    first_pay_date: date | None = None


class EmployeeRead(FinancialRead):
    full_name: str
    salary: Decimal
    currency: str
    first_pay_date: date

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Query

from app.api.dependencies import DbSession
from app.core.pagination import Page, Pagination
from app.core.responses import ApiResponse
from app.modules.auth.dependencies import CurrentUser
from app.modules.debts.models import Debt
from app.modules.debts.repository import DebtRepository
from app.modules.debts.schemas import (
    DebtCreate,
    DebtFilters,
    DebtPay,
    DebtPaymentRead,
    DebtRead,
    DebtUpdate,
)
from app.modules.debts.service import DebtService

router = APIRouter(prefix="/debts", tags=["Debts"])


@router.post("", response_model=ApiResponse[DebtRead], status_code=201)
async def create_debt(data: DebtCreate, user: CurrentUser, session: DbSession):
    return ApiResponse(data=await DebtService(session).create(user.id, data))


@router.get("", response_model=ApiResponse[Page[DebtRead]])
async def list_debts(
    user: CurrentUser, session: DbSession, filters: Annotated[DebtFilters, Query()]
):
    conditions = []
    if filters.is_active is not None:
        conditions.append(Debt.is_active == filters.is_active)
    if filters.due_before is not None:
        conditions.append(Debt.next_due_date <= filters.due_before)
    return ApiResponse(
        data=await DebtRepository(session).list(user.id, filters, DebtRead, *conditions)
    )


@router.get("/{debt_id}", response_model=ApiResponse[DebtRead])
async def get_debt(debt_id: UUID, user: CurrentUser, session: DbSession):
    return ApiResponse(data=await DebtRepository(session).get(debt_id, user.id))


@router.patch("/{debt_id}", response_model=ApiResponse[DebtRead])
async def update_debt(debt_id: UUID, data: DebtUpdate, user: CurrentUser, session: DbSession):
    return ApiResponse(data=await DebtService(session).update(user.id, debt_id, data))


@router.post("/{debt_id}/payments", response_model=ApiResponse[DebtPaymentRead], status_code=201)
async def pay_debt(debt_id: UUID, data: DebtPay, user: CurrentUser, session: DbSession):
    return ApiResponse(data=await DebtService(session).pay(user.id, debt_id, data))


@router.get("/{debt_id}/payments", response_model=ApiResponse[Page[DebtPaymentRead]])
async def list_payments(debt_id: UUID, user: CurrentUser, session: DbSession, params: Pagination):
    repository = DebtRepository(session)
    await repository.get(debt_id, user.id)
    return ApiResponse(data=await repository.payments(debt_id, params))

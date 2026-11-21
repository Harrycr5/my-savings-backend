from fastapi import APIRouter
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.api.dependencies import DbSession
from app.core.exceptions import ConflictError
from app.core.finance import OwnedRepository
from app.core.responses import ApiResponse
from app.modules.auth.dependencies import CurrentUser
from app.modules.budgets.models import MonthlyBudget
from app.modules.budgets.schemas import MonthlyBudgetCreate, MonthlyBudgetRead
from app.modules.currencies.service import require_selectable_currency

router = APIRouter(prefix="/budgets", tags=["Budgets"])


@router.post("", response_model=ApiResponse[MonthlyBudgetRead], status_code=201)
async def create_monthly_budget(data: MonthlyBudgetCreate, user: CurrentUser, session: DbSession):
    await require_selectable_currency(session, data.currency)
    user_id = user.id
    try:
        budget = await OwnedRepository(session, MonthlyBudget).save(
            MonthlyBudget(user_id=user_id, **data.model_dump())
        )
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        existing_id = await session.scalar(
            select(MonthlyBudget.id).where(
                MonthlyBudget.user_id == user_id,
                MonthlyBudget.year == data.year,
                MonthlyBudget.month == data.month,
            )
        )
        if existing_id is not None:
            raise ConflictError("Ya existe un presupuesto para ese mes.") from exc
        raise
    return ApiResponse(data=budget)

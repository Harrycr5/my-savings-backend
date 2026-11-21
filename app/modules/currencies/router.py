from fastapi import APIRouter
from sqlalchemy import select

from app.api.dependencies import DbSession
from app.core.responses import ApiResponse
from app.modules.auth.dependencies import CurrentUser
from app.modules.currencies.models import Currency
from app.modules.currencies.schemas import CurrencyRead

router = APIRouter(prefix="/currencies", tags=["Currencies"])


@router.get("", response_model=ApiResponse[list[CurrencyRead]])
async def list_currencies(user: CurrentUser, session: DbSession):
    currencies = await session.scalars(
        select(Currency).where(Currency.is_selectable.is_(True)).order_by(Currency.code)
    )
    return ApiResponse(data=currencies.all())

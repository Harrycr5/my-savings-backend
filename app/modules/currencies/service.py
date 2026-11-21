from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AppError
from app.modules.currencies.models import Currency


class UnsupportedCurrencyError(AppError):
    status_code = 422


async def require_selectable_currency(session: AsyncSession, code: str) -> None:
    currency = await session.get(Currency, code)
    if currency is None or not currency.is_selectable:
        raise UnsupportedCurrencyError(f"La moneda {code} no está disponible para seleccionar.")

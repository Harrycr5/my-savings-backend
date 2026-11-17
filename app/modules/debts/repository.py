from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.finance import OwnedRepository
from app.core.pagination import Page, PaginationParams
from app.modules.debts.models import Debt, DebtPayment
from app.modules.debts.schemas import DebtPaymentRead


class DebtRepository(OwnedRepository[Debt]):
    def __init__(self, session: AsyncSession):
        super().__init__(session, Debt)

    async def payments(self, debt_id: UUID, params: PaginationParams):
        total = (
            await self.session.scalar(
                select(func.count()).select_from(DebtPayment).where(DebtPayment.debt_id == debt_id)
            )
            or 0
        )
        records = await self.session.scalars(
            select(DebtPayment)
            .where(DebtPayment.debt_id == debt_id)
            .order_by(DebtPayment.due_date.desc(), DebtPayment.id)
            .offset(params.offset)
            .limit(params.page_size)
        )
        return Page.build([DebtPaymentRead.model_validate(item) for item in records], total, params)

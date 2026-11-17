from decimal import Decimal
from uuid import UUID

from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError
from app.core.finance import OwnedRepository
from app.core.pagination import Page, PaginationParams
from app.modules.tills.models import Till, TillConcept, TillMovement
from app.modules.tills.schemas import (
    ConceptRead,
    MovementFilters,
    MovementRead,
    TillBalance,
    TillSummary,
)


class TillRepository(OwnedRepository[Till]):
    def __init__(self, session: AsyncSession):
        super().__init__(session, Till)

    async def summary(self, user_id: UUID):
        movements = (
            select(
                TillMovement.till_id,
                func.sum(
                    case((TillMovement.direction == "income", TillMovement.amount), else_=0)
                ).label("income"),
                func.sum(
                    case((TillMovement.direction == "expense", TillMovement.amount), else_=0)
                ).label("expense"),
            )
            .group_by(TillMovement.till_id)
            .subquery()
        )
        rows = await self.session.execute(
            select(
                Till.currency,
                func.count(Till.id),
                func.sum(Till.opening_balance),
                func.coalesce(func.sum(movements.c.income), 0),
                func.coalesce(func.sum(movements.c.expense), 0),
            )
            .outerjoin(movements, movements.c.till_id == Till.id)
            .where(Till.user_id == user_id)
            .group_by(Till.currency)
            .order_by(Till.currency)
        )
        return [
            TillSummary(
                currency=currency,
                total_tills=count,
                opening_balance=opening,
                total_income=income,
                total_expense=expense,
                net_savings=income - expense,
                balance=opening + income - expense,
            )
            for currency, count, opening, income, expense in rows
        ]

    async def get_concept(self, till_id: UUID, concept_id: UUID) -> TillConcept:
        concept = await self.session.scalar(
            select(TillConcept).where(TillConcept.id == concept_id, TillConcept.till_id == till_id)
        )
        if concept is None:
            raise NotFoundError("El concepto no existe en esta caja.")
        return concept

    async def concepts(self, till_id: UUID, params: PaginationParams):
        total = (
            await self.session.scalar(
                select(func.count()).select_from(TillConcept).where(TillConcept.till_id == till_id)
            )
            or 0
        )
        records = await self.session.scalars(
            select(TillConcept)
            .where(TillConcept.till_id == till_id)
            .order_by(TillConcept.name, TillConcept.id)
            .offset(params.offset)
            .limit(params.page_size)
        )
        return Page.build([ConceptRead.model_validate(item) for item in records], total, params)

    async def movements(self, till_id: UUID, filters: MovementFilters):
        query = select(TillMovement).where(TillMovement.till_id == till_id)
        return await self._movement_page(query, filters)

    async def all_movements(self, user_id: UUID, filters: MovementFilters):
        query = (
            select(TillMovement)
            .join(Till, Till.id == TillMovement.till_id)
            .where(Till.user_id == user_id)
        )
        return await self._movement_page(query, filters)

    async def _movement_page(self, query, filters: MovementFilters):
        conditions = []
        for field in ("direction", "concept_id"):
            if (value := getattr(filters, field)) is not None:
                conditions.append(getattr(TillMovement, field) == value)
        if filters.date_from:
            conditions.append(TillMovement.occurred_on >= filters.date_from)
        if filters.date_to:
            conditions.append(TillMovement.occurred_on <= filters.date_to)
        query = query.where(*conditions)
        total = await self.session.scalar(select(func.count()).select_from(query.subquery())) or 0
        records = await self.session.scalars(
            query.order_by(
                TillMovement.occurred_on.desc(), TillMovement.created_at.desc(), TillMovement.id
            )
            .offset(filters.offset)
            .limit(filters.page_size)
        )
        return Page.build([MovementRead.model_validate(item) for item in records], total, filters)

    async def balance(self, till: Till) -> TillBalance:
        income, expense = (
            await self.session.execute(
                select(
                    func.coalesce(
                        func.sum(
                            case((TillMovement.direction == "income", TillMovement.amount), else_=0)
                        ),
                        0,
                    ),
                    func.coalesce(
                        func.sum(
                            case(
                                (TillMovement.direction == "expense", TillMovement.amount), else_=0
                            )
                        ),
                        0,
                    ),
                ).where(TillMovement.till_id == till.id)
            )
        ).one()
        income, expense = Decimal(income), Decimal(expense)
        return TillBalance(
            till_id=till.id,
            currency=till.currency,
            opening_balance=till.opening_balance,
            total_income=income,
            total_expense=expense,
            balance=till.opening_balance + income - expense,
        )

from calendar import monthrange
from datetime import date, timedelta
from uuid import UUID

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AppError, ConflictError
from app.modules.currencies.service import require_selectable_currency
from app.modules.debts.models import Debt, DebtPayment
from app.modules.debts.repository import DebtRepository
from app.modules.debts.schemas import DebtCreate, DebtPay, DebtUpdate
from app.modules.tills.repository import TillRepository
from app.modules.tills.schemas import MovementCreate
from app.modules.tills.service import TillService


def next_due_date(debt: Debt) -> date | None:
    """Preserve the original day across short months and leap years."""
    current = debt.next_due_date
    if debt.frequency == "once":
        return None
    if debt.frequency in {"daily", "weekly"}:
        days = debt.interval * (7 if debt.frequency == "weekly" else 1)
        return current + timedelta(days=days)
    months = debt.interval * (12 if debt.frequency == "yearly" else 1)
    month_index = current.year * 12 + current.month - 1 + months
    year, month = divmod(month_index, 12)
    month += 1
    return date(year, month, min(debt.first_due_date.day, monthrange(year, month)[1]))


class DebtService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.repository = DebtRepository(session)

    async def create(self, user_id: UUID, data: DebtCreate):
        await require_selectable_currency(self.session, data.currency)
        debt = Debt(user_id=user_id, next_due_date=data.first_due_date, **data.model_dump())
        await self.repository.save(debt)
        await self.session.commit()
        return debt

    async def update(self, user_id: UUID, debt_id: UUID, data: DebtUpdate):
        debt = await self.repository.get(debt_id, user_id, lock=True)
        if data.is_active and debt.next_due_date is None:
            raise ConflictError("Esta deuda ya fue completada.")
        for field, value in data.model_dump(exclude_unset=True).items():
            setattr(debt, field, value)
        await self.repository.save(debt)
        await self.session.commit()
        return debt

    async def pay(self, user_id: UUID, debt_id: UUID, data: DebtPay):
        try:
            debt = await self.repository.get(debt_id, user_id, lock=True)
            if not debt.is_active or debt.next_due_date is None:
                raise ConflictError("La deuda está desactivada o completada.")
            if data.due_date != debt.next_due_date:
                raise ConflictError("El vencimiento ya fue pagado o no es el siguiente pendiente.")
            tills = TillRepository(self.session)
            till = await tills.get(data.till_id, user_id)
            if till.currency != debt.currency:
                raise AppError("La caja y la deuda deben tener la misma moneda.")
            concept = await tills.get_concept(till.id, data.concept_id)
            if concept.direction != "expense":
                raise AppError("El pago requiere un concepto de salida.")
            try:
                following_date = next_due_date(debt)
            except (ValueError, OverflowError) as exc:
                raise AppError(
                    "El próximo vencimiento excede el rango de fechas permitido."
                ) from exc
            movement = await TillService(self.session).add_movement(
                user_id,
                till.id,
                MovementCreate(
                    concept_id=concept.id,
                    amount=debt.amount,
                    occurred_on=data.paid_on,
                    description=f"Pago: {debt.name}",
                ),
            )
            payment = DebtPayment(
                debt_id=debt.id,
                movement_id=movement.id,
                due_date=data.due_date,
                paid_on=data.paid_on,
                amount=debt.amount,
                currency=debt.currency,
            )
            self.session.add(payment)
            debt.next_due_date = following_date
            if following_date is None:
                debt.is_active = False
            await self.session.flush()
            await self.session.refresh(payment)
            await self.session.commit()
            return payment
        except IntegrityError as exc:
            await self.session.rollback()
            raise ConflictError("Este vencimiento ya fue pagado.") from exc
        except Exception:
            await self.session.rollback()
            raise

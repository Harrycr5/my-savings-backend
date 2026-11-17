from uuid import UUID

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError
from app.modules.tills.models import Till, TillConcept, TillMovement
from app.modules.tills.repository import TillRepository
from app.modules.tills.schemas import ConceptCreate, MovementCreate, TillCreate, TillUpdate


class TillService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.repository = TillRepository(session)

    async def create(self, user_id: UUID, data: TillCreate) -> Till:
        till = await self.repository.save(Till(user_id=user_id, **data.model_dump()))
        await self.session.commit()
        return till

    async def update(self, user_id: UUID, till_id: UUID, data: TillUpdate) -> Till:
        till = await self.repository.get(till_id, user_id, lock=True)
        for field, value in data.model_dump(exclude_unset=True).items():
            setattr(till, field, value)
        await self.repository.save(till)
        await self.session.commit()
        return till

    async def create_concept(self, user_id: UUID, till_id: UUID, data: ConceptCreate):
        await self.repository.get(till_id, user_id)
        concept = TillConcept(till_id=till_id, **data.model_dump())
        try:
            self.session.add(concept)
            await self.session.flush()
            await self.session.refresh(concept)
            await self.session.commit()
        except IntegrityError as exc:
            await self.session.rollback()
            raise ConflictError("Ya existe un concepto con ese nombre y tipo en la caja.") from exc
        return concept

    async def add_movement(self, user_id: UUID, till_id: UUID, data: MovementCreate):
        # También se usa desde debts: el pago y la salida se confirman juntos.
        await self.repository.get(till_id, user_id)
        concept = await self.repository.get_concept(till_id, data.concept_id)
        movement = TillMovement(till_id=till_id, direction=concept.direction, **data.model_dump())
        self.session.add(movement)
        await self.session.flush()
        await self.session.refresh(movement)
        return movement

    async def create_movement(self, user_id: UUID, till_id: UUID, data: MovementCreate):
        movement = await self.add_movement(user_id, till_id, data)
        await self.session.commit()
        return movement

import json
from hashlib import sha256
from uuid import UUID

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError
from app.modules.currencies.service import require_selectable_currency
from app.modules.tills.models import Till, TillConcept, TillMovement, TillMovementRequest
from app.modules.tills.repository import TillRepository
from app.modules.tills.schemas import ConceptCreate, MovementCreate, TillCreate, TillUpdate


class TillService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.repository = TillRepository(session)

    async def create(self, user_id: UUID, data: TillCreate) -> Till:
        await require_selectable_currency(self.session, data.currency)
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

    async def add_movement(
        self, user_id: UUID, till_id: UUID, data: MovementCreate
    ) -> TillMovement:
        # También se usa desde debts: el pago y la salida se confirman juntos.
        await self.repository.get(till_id, user_id)
        concept = await self.repository.get_concept(till_id, data.concept_id)
        movement = TillMovement(till_id=till_id, direction=concept.direction, **data.model_dump())
        self.session.add(movement)
        await self.session.flush()
        await self.session.refresh(movement)
        return movement

    async def create_movement(
        self,
        user_id: UUID,
        till_id: UUID,
        data: MovementCreate,
        *,
        idempotency_key: str | None = None,
    ) -> TillMovement:
        if idempotency_key is None:
            movement = await self.add_movement(user_id, till_id, data)
            await self.session.commit()
            return movement

        await self.repository.get(till_id, user_id)
        fingerprint = self._movement_fingerprint(till_id, data)
        try:
            request = await self.repository.reserve_movement_request(
                user_id, idempotency_key, fingerprint
            )
            if request is None:
                request = await self.session.get_one(
                    TillMovementRequest, (user_id, idempotency_key)
                )
                if request.request_fingerprint != fingerprint:
                    raise ConflictError("La clave de idempotencia ya se usó con otros datos.")
                if request.movement_id is None:
                    raise ConflictError("La solicitud con esta clave sigue en proceso.")
                return await self.session.get_one(TillMovement, request.movement_id)

            movement = await self.add_movement(user_id, till_id, data)
            request.movement_id = movement.id
            request.status = "completed"
            await self.session.commit()
            return movement
        except Exception:
            await self.session.rollback()
            raise

    @staticmethod
    def _movement_fingerprint(till_id: UUID, data: MovementCreate) -> str:
        payload = data.model_dump(mode="json")
        payload["till_id"] = str(till_id)
        payload["amount"] = format(data.amount, ".2f")
        # Una fecha implícita puede cambiar entre el primer envío y el reintento.
        if "occurred_on" not in data.model_fields_set:
            payload.pop("occurred_on")
        encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
        return sha256(encoded).hexdigest()

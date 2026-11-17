"""Shared validation and persistence for user-owned financial records."""

from datetime import datetime
from decimal import Decimal
from typing import Annotated, Generic, TypeVar
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError
from app.core.pagination import Page, PaginationParams

Money = Annotated[Decimal, Field(ge=0, max_digits=18, decimal_places=2)]
PositiveMoney = Annotated[Decimal, Field(gt=0, max_digits=18, decimal_places=2)]
Currency = Annotated[str, StringConstraints(pattern=r"^[A-Z]{3}$")]
Name = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=100)]
Description = Annotated[str, StringConstraints(strip_whitespace=True, max_length=500)]


class FinancialInput(BaseModel):
    model_config = ConfigDict(extra="forbid")


class FinancialPatch(FinancialInput):
    @model_validator(mode="after")
    def validate_changes(self):
        if not self.model_fields_set:
            raise ValueError("Envía al menos un campo para actualizar.")
        for field in self.model_fields_set:
            if getattr(self, field) is None and field not in {"description", "other_type"}:
                raise ValueError(f"El campo {field} no acepta null.")
        return self


class FinancialRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    created_at: datetime
    updated_at: datetime


T = TypeVar("T")


class OwnedRepository(Generic[T]):
    def __init__(self, session: AsyncSession, model: type[T]):
        self.session = session
        self.model = model

    async def get(self, record_id: UUID, user_id: UUID, *, lock: bool = False) -> T:
        statement = select(self.model).where(
            self.model.id == record_id, self.model.user_id == user_id
        )
        if lock:
            statement = statement.with_for_update().execution_options(populate_existing=True)
        record = await self.session.scalar(statement)
        if record is None:
            raise NotFoundError("El registro no existe.")
        return record

    async def list(self, user_id: UUID, params: PaginationParams, schema, *conditions):
        conditions = (self.model.user_id == user_id, *conditions)
        total = (
            await self.session.scalar(
                select(func.count()).select_from(self.model).where(*conditions)
            )
            or 0
        )
        records = await self.session.scalars(
            select(self.model)
            .where(*conditions)
            .order_by(self.model.created_at.desc(), self.model.id)
            .offset(params.offset)
            .limit(params.page_size)
        )
        return Page.build([schema.model_validate(item) for item in records], total, params)

    async def save(self, record: T) -> T:
        self.session.add(record)
        await self.session.flush()
        await self.session.refresh(record)
        return record

from uuid import UUID

from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AppError
from app.modules.currencies.service import require_selectable_currency
from app.modules.inheritance.models import Asset
from app.modules.inheritance.repository import AssetRepository
from app.modules.inheritance.schemas import AssetCreate, AssetUpdate


class AssetService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.repository = AssetRepository(session)

    async def create(self, user_id: UUID, data: AssetCreate):
        await require_selectable_currency(self.session, data.currency)
        asset = await self.repository.save(Asset(user_id=user_id, **data.model_dump()))
        await self.session.commit()
        return asset

    async def update(self, user_id: UUID, asset_id: UUID, data: AssetUpdate):
        asset = await self.repository.get(asset_id, user_id, lock=True)
        values = {field: getattr(asset, field) for field in AssetCreate.model_fields}
        changes = data.model_dump(exclude_unset=True)
        values.update(changes)
        if (
            "asset_type" in changes
            and changes["asset_type"] != "other"
            and "other_type" not in changes
        ):
            values["other_type"] = None
        try:
            validated = AssetCreate.model_validate(values)
        except ValidationError as exc:
            raise AppError(
                "Para el tipo other debes especificar other_type; revisa el tipo de bien."
            ) from exc
        for field, value in validated.model_dump().items():
            setattr(asset, field, value)
        await self.repository.save(asset)
        await self.session.commit()
        return asset

    async def delete(self, user_id: UUID, asset_id: UUID):
        asset = await self.repository.get(asset_id, user_id, lock=True)
        await self.session.delete(asset)
        await self.session.commit()

from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.finance import OwnedRepository
from app.modules.inheritance.models import Asset
from app.modules.inheritance.schemas import AssetSummary


class AssetRepository(OwnedRepository[Asset]):
    def __init__(self, session: AsyncSession):
        super().__init__(session, Asset)

    async def summary(self, user_id: UUID):
        rows = await self.session.execute(
            select(
                Asset.currency,
                func.count(Asset.id),
                func.sum(Asset.current_value),
                func.sum(Asset.market_value),
            )
            .where(Asset.user_id == user_id)
            .group_by(Asset.currency)
            .order_by(Asset.currency)
        )
        return [
            AssetSummary(
                currency=currency, total_assets=count, current_value=current, market_value=market
            )
            for currency, count, current, market in rows
        ]

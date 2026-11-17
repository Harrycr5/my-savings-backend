from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.auth.models import PasswordResetCode


class PasswordResetRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_for_user(self, user_id: UUID) -> PasswordResetCode | None:
        return await self.session.scalar(
            select(PasswordResetCode)
            .where(PasswordResetCode.user_id == user_id)
            .with_for_update()
            .execution_options(populate_existing=True)
        )

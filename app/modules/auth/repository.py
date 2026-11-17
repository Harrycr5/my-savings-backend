from datetime import datetime
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.auth.models import AuthSession


class AuthSessionRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_by_id(self, session_id: UUID, *, lock: bool = False) -> AuthSession | None:
        statement = select(AuthSession).where(AuthSession.id == session_id)
        if lock:
            statement = statement.with_for_update().execution_options(populate_existing=True)
        return await self.session.scalar(statement)

    async def create(
        self, *, session_id: UUID, user_id: UUID, token_hash: str, expires_at: datetime
    ) -> AuthSession:
        auth_session = AuthSession(
            id=session_id,
            user_id=user_id,
            refresh_token_hash=token_hash,
            expires_at=expires_at,
        )
        self.session.add(auth_session)
        await self.session.flush()
        return auth_session

    async def revoke(self, session_id: UUID, revoked_at: datetime) -> None:
        await self.session.execute(
            update(AuthSession)
            .where(AuthSession.id == session_id, AuthSession.revoked_at.is_(None))
            .values(revoked_at=revoked_at)
        )

    async def revoke_for_user(self, user_id: UUID, revoked_at: datetime) -> None:
        await self.session.execute(
            update(AuthSession)
            .where(AuthSession.user_id == user_id, AuthSession.revoked_at.is_(None))
            .values(revoked_at=revoked_at)
        )

from datetime import datetime, timedelta, timezone
from hmac import compare_digest
from uuid import UUID, uuid4

from jwt.exceptions import InvalidTokenError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.security import (
    DUMMY_PASSWORD_HASH,
    create_access_token,
    create_refresh_token,
    hash_refresh_token,
    refresh_session_id,
    verify_password,
)
from app.modules.auth.exceptions import InvalidCredentialsError
from app.modules.auth.models import AuthSession
from app.modules.auth.repository import AuthSessionRepository
from app.modules.auth.schemas import TokenRead
from app.modules.users.models import User
from app.modules.users.repository import UserRepository
from app.modules.users.schemas import UserSessionRead


class AuthService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.users = UserRepository(session)
        self.sessions = AuthSessionRepository(session)
        self.settings = get_settings()

    @staticmethod
    def ensure_active(user: User | None) -> User:
        if user is None or not user.is_active or (not user.is_admin and not user.profile.is_active):
            raise InvalidCredentialsError()
        return user

    def tokens(self, user: User, session_id: UUID, refresh_token: str) -> TokenRead:
        return TokenRead(
            access_token=create_access_token(user.id, session_id),
            refresh_token=refresh_token,
            expires_in=self.settings.access_token_expire_minutes * 60,
            user=UserSessionRead.from_user(user),
        )

    async def login(self, identifier: str, password: str) -> TokenRead:
        identifier = identifier.strip().lower()
        if "@" in identifier:
            user = await self.users.get_email_for_update(identifier)
        else:
            user = await self.users.get_username_for_update(identifier)
        password_hash = user.password_hash if user is not None else DUMMY_PASSWORD_HASH
        valid_password = await verify_password(password, password_hash)
        if user is None or not valid_password:
            raise InvalidCredentialsError()
        user = self.ensure_active(await self.users.get_with_permissions(user.id))
        session_id = uuid4()
        refresh_token = create_refresh_token(session_id)
        expires_at = datetime.now(timezone.utc) + timedelta(
            days=self.settings.refresh_token_expire_days
        )
        try:
            await self.sessions.create(
                session_id=session_id,
                user_id=user.id,
                token_hash=hash_refresh_token(refresh_token),
                expires_at=expires_at,
            )
            response = self.tokens(user, session_id, refresh_token)
            await self.session.commit()
        except Exception:
            await self.session.rollback()
            raise
        return response

    async def refresh(self, token: str) -> TokenRead:
        try:
            session_id = refresh_session_id(token)
        except InvalidTokenError as exc:
            raise InvalidCredentialsError("Refresh token inválido.") from exc
        try:
            # Bloqueo de fila: dos renovaciones no pueden aceptar el mismo token.
            auth_session = await self.sessions.get_by_id(session_id, lock=True)
            now = datetime.now(timezone.utc)
            if (
                auth_session is None
                or auth_session.revoked_at is not None
                or auth_session.expires_at <= now
                or not compare_digest(auth_session.refresh_token_hash, hash_refresh_token(token))
            ):
                raise InvalidCredentialsError("Refresh token inválido o vencido.")
            user = self.ensure_active(await self.users.get_with_permissions(auth_session.user_id))
            refresh_token = create_refresh_token(session_id)
            auth_session.refresh_token_hash = hash_refresh_token(refresh_token)
            # La sesión conserva su vencimiento absoluto; no se extiende indefinidamente.
            response = self.tokens(user, session_id, refresh_token)
            await self.session.commit()
        except Exception:
            await self.session.rollback()
            raise
        return response

    async def logout(self, auth_session: AuthSession) -> None:
        try:
            await self.sessions.revoke(auth_session.id, datetime.now(timezone.utc))
            await self.session.commit()
        except Exception:
            await self.session.rollback()
            raise

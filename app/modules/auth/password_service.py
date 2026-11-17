from datetime import datetime, timedelta, timezone
from hashlib import sha256
from hmac import compare_digest
from hmac import new as hmac_new
from secrets import randbelow
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.exceptions import AppError
from app.core.security import hash_password, verify_password
from app.infrastructure.mail import ensure_mail_configured
from app.modules.auth.models import PasswordResetCode
from app.modules.auth.password_repository import PasswordResetRepository
from app.modules.auth.repository import AuthSessionRepository
from app.modules.auth.schemas import PasswordChange, PasswordReset
from app.modules.users.models import User
from app.modules.users.repository import UserRepository


class PasswordService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.users = UserRepository(session)
        self.codes = PasswordResetRepository(session)
        self.sessions = AuthSessionRepository(session)
        self.settings = get_settings()

    def code_hash(self, user_id: UUID, code: str) -> str:
        value = f"password-reset:{user_id}:{code}".encode()
        return hmac_new(self.settings.jwt_secret_key.encode(), value, sha256).hexdigest()

    async def replace_password(self, user: User, password: str, now: datetime) -> None:
        if await verify_password(password, user.password_hash):
            raise AppError("La nueva contraseña debe ser distinta de la anterior.")
        user.password_hash = await hash_password(password)
        challenge = await self.codes.get_for_user(user.id)
        if challenge is not None:
            challenge.consumed_at = now
        await self.sessions.revoke_for_user(user.id, now)
        await self.session.commit()

    async def change(self, user_id: UUID, data: PasswordChange) -> None:
        try:
            user = await self.users.get_for_update(user_id)
            if user is None or not user.is_active:
                raise AppError("La cuenta no está disponible.")
            if not await verify_password(
                data.current_password.get_secret_value(), user.password_hash
            ):
                raise AppError("La contraseña actual no es correcta.")
            await self.replace_password(
                user, data.new_password.get_secret_value(), datetime.now(timezone.utc)
            )
        except Exception:
            await self.session.rollback()
            raise

    async def request_reset(self, email: str) -> tuple[str, str] | None:
        # Fallar igual para cualquier dirección si aún no se configuró SMTP.
        ensure_mail_configured()
        try:
            user = await self.users.get_email_for_update(email.lower())
            if user is None or not user.is_active:
                return None
            now = datetime.now(timezone.utc)
            challenge = await self.codes.get_for_user(user.id)
            if (
                challenge is not None
                and (now - challenge.requested_at).total_seconds()
                < self.settings.password_reset_cooldown_seconds
            ):
                return None
            code = f"{randbelow(1_000_000):06d}"
            while challenge is not None and compare_digest(
                challenge.code_hash, self.code_hash(user.id, code)
            ):
                code = f"{randbelow(1_000_000):06d}"
            if challenge is None:
                challenge = PasswordResetCode(user_id=user.id)
                self.session.add(challenge)
            challenge.code_hash = self.code_hash(user.id, code)
            challenge.expires_at = now + timedelta(
                minutes=self.settings.password_reset_expire_minutes
            )
            challenge.requested_at = now
            challenge.attempts = 0
            challenge.consumed_at = None
            await self.session.commit()
            return user.email, code
        except Exception:
            await self.session.rollback()
            raise

    async def reset(self, data: PasswordReset) -> None:
        invalid = "El código es inválido o venció. Solicita uno nuevo."
        try:
            user = await self.users.get_email_for_update(str(data.email).lower())
            if user is None or not user.is_active:
                raise AppError(invalid)
            now = datetime.now(timezone.utc)
            challenge = await self.codes.get_for_user(user.id)
            if (
                challenge is None
                or challenge.consumed_at is not None
                or challenge.expires_at <= now
                or challenge.attempts >= self.settings.password_reset_max_attempts
            ):
                raise AppError(invalid)
            if not compare_digest(challenge.code_hash, self.code_hash(user.id, data.code)):
                challenge.attempts += 1
                await self.session.commit()
                raise AppError(invalid)
            await self.replace_password(user, data.new_password.get_secret_value(), now)
        except Exception:
            await self.session.rollback()
            raise

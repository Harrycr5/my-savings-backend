from datetime import datetime, timedelta, timezone
from hashlib import sha256
from secrets import token_urlsafe
from uuid import UUID, uuid4

import jwt
from jwt.exceptions import InvalidTokenError
from pwdlib import PasswordHash
from starlette.concurrency import run_in_threadpool

from app.core.config import get_settings

settings = get_settings()
password_hasher = PasswordHash.recommended()

# Se utiliza para verificar una contraseña incluso cuando
# el usuario no existe, reduciendo diferencias de tiempo.
DUMMY_PASSWORD_HASH = password_hasher.hash("dummy-password-not-used-for-login")


async def hash_password(password: str) -> str:
    return await run_in_threadpool(
        password_hasher.hash,
        password,
    )


async def verify_password(password: str, password_hash: str) -> bool:
    return await run_in_threadpool(
        password_hasher.verify,
        password,
        password_hash,
    )


def create_access_token(user_id: UUID, session_id: UUID) -> str:
    now = datetime.now(timezone.utc)

    payload = {
        "sub": str(user_id),
        "sid": str(session_id),
        "jti": str(uuid4()),
        "iat": now,
        "exp": now + timedelta(minutes=settings.access_token_expire_minutes),
        "type": "access",
    }

    return jwt.encode(
        payload,
        settings.jwt_secret_key,
        algorithm=settings.jwt_algorithm,
    )


def decode_access_token(token: str) -> tuple[UUID, UUID]:
    payload = jwt.decode(
        token,
        settings.jwt_secret_key,
        algorithms=[settings.jwt_algorithm],
        options={
            "require": ["sub", "sid", "iat", "exp", "type"],
        },
    )

    if payload["type"] != "access":
        raise InvalidTokenError("Tipo de token inválido.")

    subject = payload["sub"]

    if not isinstance(subject, str):
        raise InvalidTokenError("Identificador inválido.")

    try:
        return UUID(subject), UUID(payload["sid"])
    except (ValueError, TypeError, AttributeError) as exc:
        raise InvalidTokenError("Identificador inválido.") from exc


def create_refresh_token(session_id: UUID) -> str:
    return f"{session_id}.{token_urlsafe(48)}"


def hash_refresh_token(token: str) -> str:
    return sha256(token.encode("utf-8")).hexdigest()


def refresh_session_id(token: str) -> UUID:
    try:
        session_id, secret = token.split(".", 1)
        if not secret:
            raise ValueError("Refresh token incompleto.")
        return UUID(session_id)
    except (ValueError, TypeError, AttributeError) as exc:
        raise InvalidTokenError("Refresh token inválido.") from exc

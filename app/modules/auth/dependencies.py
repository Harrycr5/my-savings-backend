from datetime import datetime, timezone
from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jwt.exceptions import InvalidTokenError

from app.api.dependencies import DbSession
from app.core.security import decode_access_token
from app.modules.auth.models import AuthSession
from app.modules.auth.repository import AuthSessionRepository
from app.modules.users.models import User
from app.modules.users.repository import UserRepository

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")


def unauthorized(message: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=message,
        headers={"WWW-Authenticate": "Bearer"},
    )


async def get_current_session(
    token: Annotated[str, Depends(oauth2_scheme)], session: DbSession
) -> AuthSession:
    try:
        user_id, session_id = decode_access_token(token)
    except InvalidTokenError as exc:
        raise unauthorized("Token inválido o vencido.") from exc
    auth_session = await AuthSessionRepository(session).get_by_id(session_id)
    if (
        auth_session is None
        or auth_session.user_id != user_id
        or auth_session.revoked_at is not None
        or auth_session.expires_at <= datetime.now(timezone.utc)
    ):
        raise unauthorized("La sesión venció o fue cerrada.")
    return auth_session


CurrentSession = Annotated[AuthSession, Depends(get_current_session)]


async def get_current_user(auth_session: CurrentSession, session: DbSession) -> User:
    user = await UserRepository(session).get_with_permissions(auth_session.user_id)
    if user is None:
        raise unauthorized("Usuario no encontrado.")
    if not user.is_active or (not user.is_admin and not user.profile.is_active):
        raise HTTPException(status_code=403, detail="Usuario o perfil desactivado.")
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


def require_permissions(*required_codes: str):
    async def check_permissions(user: CurrentUser) -> User:
        if user.is_admin:
            return user
        available_codes = {permission.code for permission in user.profile.permissions}
        if not set(required_codes).issubset(available_codes):
            raise HTTPException(status_code=403, detail="No tienes permisos para esta operación.")
        return user

    return check_permissions


async def require_superadmin(user: CurrentUser) -> User:
    if not user.is_admin:
        raise HTTPException(status_code=403, detail="Esta operación requiere ser superadmin.")
    return user


SuperAdmin = Annotated[User, Depends(require_superadmin)]

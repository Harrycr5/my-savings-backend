from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ForbiddenError, NotFoundError
from app.core.security import hash_password
from app.modules.auth.repository import AuthSessionRepository

from ..profiles.repository import ProfileRepository
from ..users.exceptions import (
    RegistrationUnavailableError,
    UserAlreadyExistsError,
)
from ..users.models import User
from ..users.repository import UserRepository
from ..users.schemas import UserAdminUpdate, UserCreate, UserFilters, UserUpdate


class UserService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.users = UserRepository(session)
        self.profiles = ProfileRepository(session)

    async def register(self, data: UserCreate) -> User:
        email = str(data.email).lower()
        username = data.username.upper()

        if await self.users.get_by_email(email):
            raise UserAlreadyExistsError("El correo ya está registrado.")

        if await self.users.get_by_username(username):
            raise UserAlreadyExistsError("El nombre de usuario ya está registrado.")

        profile = await self.profiles.get_by_code("user")

        if profile is None or not profile.is_active:
            raise RegistrationUnavailableError("El registro de usuarios no está disponible.")

        password_hash = await hash_password(data.password.get_secret_value())

        try:
            user = await self.users.create(
                email=email,
                username=username,
                name=data.name,
                last_name=data.last_name,
                password_hash=password_hash,
                profile_id=profile.id,
            )

            await self.session.commit()

        except IntegrityError as exc:
            await self.session.rollback()

            if getattr(exc.orig, "sqlstate", None) == "23505":
                raise UserAlreadyExistsError(
                    "El correo o el nombre de usuario ya está registrado."
                ) from exc

            raise

        return user

    async def update_me(
        self,
        user: User,
        data: UserUpdate,
    ) -> User:
        changes = data.model_dump(exclude_unset=True)

        try:
            user = await self.users.update_personal_data(
                user,
                changes,
            )
            await self.session.commit()

        except Exception:
            await self.session.rollback()
            raise

        return user

    async def list_users(self, filters: UserFilters) -> tuple[list[User], int]:
        users = await self.users.list_users(filters)
        total = await self.users.count_users(filters)
        return users, total

    async def get_user(self, user_id: UUID) -> User:
        user = await self.users.get_with_permissions(user_id)
        if user is None:
            raise NotFoundError("El usuario no existe.")
        return user

    async def update_user(self, user_id: UUID, data: UserAdminUpdate) -> User:
        user = await self.get_user(user_id)
        if user.is_admin:
            raise ForbiddenError("Las cuentas superadmin se administran desde consola.")
        changes = data.model_dump(exclude_unset=True)
        if data.profile_id is not None:
            profile = await self.profiles.get_by_id(data.profile_id)
            if profile is None:
                raise NotFoundError("El perfil no existe.")
            if profile.code == "superadmin":
                raise ForbiddenError("El perfil superadmin se asigna desde consola.")
            if not profile.is_active:
                raise ForbiddenError("No se puede asignar un perfil desactivado.")
        try:
            # Un cambio de perfil o estado cierra las sesiones anteriores.
            await self.users.update_admin_data(user, changes)
            await AuthSessionRepository(self.session).revoke_for_user(
                user.id, datetime.now(timezone.utc)
            )
            await self.session.commit()
        except Exception:
            await self.session.rollback()
            raise
        return user

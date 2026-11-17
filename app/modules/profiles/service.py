from uuid import UUID

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import (
    ConflictError,
    ForbiddenError,
    NotFoundError,
)

from .models import Permission, Profile
from .repository import ProfileRepository
from .schemas import (
    PermissionFilters,
    ProfileCreate,
    ProfileFilters,
    ProfilePermissionsAdd,
    ProfilePermissionsRemove,
)


class ProfileService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repository = ProfileRepository(session)

    async def list_profiles(self, filters: ProfileFilters) -> tuple[list[Profile], int]:
        profiles = await self.repository.list_profiles(filters)
        total = await self.repository.count_profiles(filters)
        return profiles, total

    async def get_profile(self, profile_id: UUID) -> Profile:
        profile = await self.repository.get_by_id(profile_id)

        if profile is None:
            raise NotFoundError("El perfil no existe.")

        return profile

    async def list_permissions(self, filters: PermissionFilters) -> tuple[list[Permission], int]:
        permissions = await self.repository.list_permissions(filters)
        total = await self.repository.count_permissions(filters)
        return permissions, total

    async def create_profile(self, data: ProfileCreate) -> Profile:
        if data.code == "superadmin":
            raise ForbiddenError("El perfil superadmin se administra desde consola.")

        try:
            profile = await self.repository.create_profile(**data.model_dump())
            await self.session.commit()

        except IntegrityError as exc:
            await self.session.rollback()

            if getattr(exc.orig, "sqlstate", None) == "23505":
                raise ConflictError("Ya existe un perfil con ese código.") from exc

            raise

        return profile

    async def add_permissions(
        self,
        profile_id: UUID,
        data: ProfilePermissionsAdd,
    ) -> Profile:
        profile = await self.get_profile(profile_id)

        if profile.code == "superadmin":
            raise ForbiddenError("El superadmin ya tiene acceso completo.")

        requested_ids = set(data.permission_ids)

        permissions = await self.repository.get_permissions_by_ids(requested_ids)

        found_ids = {permission.id for permission in permissions}

        if requested_ids != found_ids:
            raise NotFoundError("Uno o más permisos enviados no existen.")

        try:
            await self.repository.add_permissions(
                profile_id,
                requested_ids,
            )
            await self.session.commit()

        except Exception:
            await self.session.rollback()
            raise

        self.session.expire(profile, ["permissions"])

        return await self.get_profile(profile_id)

    async def remove_permissions(self, profile_id: UUID, data: ProfilePermissionsRemove) -> Profile:
        profile = await self.get_profile(profile_id)
        if profile.code == "superadmin":
            raise ForbiddenError("El superadmin tiene acceso completo por definición.")
        try:
            # Quitar un ID no asignado es una operación idempotente.
            await self.repository.remove_permissions(profile_id, set(data.permission_ids))
            await self.session.commit()
        except Exception:
            await self.session.rollback()
            raise
        self.session.expire(profile, ["permissions"])
        return await self.get_profile(profile_id)

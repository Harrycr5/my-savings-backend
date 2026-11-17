from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query

from app.api.dependencies import DbSession
from app.core.pagination import Page
from app.core.responses import ApiResponse
from app.modules.auth.dependencies import CurrentUser, SuperAdmin, require_permissions
from app.modules.users.schemas import (
    UserAdminUpdate,
    UserFilters,
    UserRead,
    UserSessionRead,
    UserUpdate,
)
from app.modules.users.service import UserService

router = APIRouter(prefix="/users", tags=["Users"])


@router.get("/me", response_model=ApiResponse[UserSessionRead])
async def get_me(user: CurrentUser):
    return ApiResponse[UserSessionRead](
        message="Usuario obtenido correctamente.", data=UserSessionRead.from_user(user)
    )


@router.patch("/me", response_model=ApiResponse[UserRead])
async def update_me(data: UserUpdate, user: CurrentUser, session: DbSession):
    updated_user = await UserService(session).update_me(user, data)
    return ApiResponse[UserRead](
        message="Usuario actualizado correctamente.", data=UserRead.model_validate(updated_user)
    )


@router.get(
    "",
    response_model=ApiResponse[Page[UserRead]],
    dependencies=[Depends(require_permissions("users.read"))],
)
async def list_users(session: DbSession, filters: Annotated[UserFilters, Query()]):
    users, total = await UserService(session).list_users(filters)
    return ApiResponse[Page[UserRead]](
        message="Usuarios obtenidos correctamente.",
        data=Page[UserRead].build(
            [UserRead.model_validate(user) for user in users], total, filters
        ),
    )


@router.get(
    "/{user_id}",
    response_model=ApiResponse[UserRead],
    dependencies=[Depends(require_permissions("users.read"))],
)
async def get_user(user_id: UUID, session: DbSession):
    user = await UserService(session).get_user(user_id)
    return ApiResponse[UserRead](
        message="Usuario obtenido correctamente.", data=UserRead.model_validate(user)
    )


@router.patch("/{user_id}", response_model=ApiResponse[UserRead])
async def update_user(user_id: UUID, data: UserAdminUpdate, session: DbSession, admin: SuperAdmin):
    user = await UserService(session).update_user(user_id, data)
    return ApiResponse[UserRead](
        message="Usuario actualizado correctamente.", data=UserRead.model_validate(user)
    )

from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends, status
from fastapi.security import OAuth2PasswordRequestForm

from app.api.dependencies import DbSession
from app.core.responses import ApiResponse
from app.infrastructure.mail import send_password_code
from app.modules.auth.dependencies import CurrentSession, CurrentUser
from app.modules.auth.password_service import PasswordService
from app.modules.auth.schemas import (
    PasswordChange,
    PasswordForgot,
    PasswordReset,
    RefreshRequest,
    TokenRead,
)
from app.modules.auth.service import AuthService
from app.modules.users.schemas import UserCreate, UserRead
from app.modules.users.service import UserService

router = APIRouter(prefix="/auth", tags=["Auth"])


@router.post("/register", response_model=ApiResponse[UserRead], status_code=status.HTTP_201_CREATED)
async def register(data: UserCreate, session: DbSession):
    user = await UserService(session).register(data)
    return ApiResponse[UserRead](
        message="Usuario registrado correctamente.", data=UserRead.model_validate(user)
    )


@router.post("/login", response_model=TokenRead)
async def login(form: Annotated[OAuth2PasswordRequestForm, Depends()], session: DbSession):
    return await AuthService(session).login(form.username, form.password)


@router.post("/refresh", response_model=TokenRead)
async def refresh(data: RefreshRequest, session: DbSession):
    return await AuthService(session).refresh(data.refresh_token.get_secret_value())


@router.post("/logout", response_model=ApiResponse[None])
async def logout(auth_session: CurrentSession, session: DbSession):
    await AuthService(session).logout(auth_session)
    return ApiResponse[None](message="Sesión cerrada correctamente.", data=None)


@router.post("/change-password", response_model=ApiResponse[None])
async def change_password(data: PasswordChange, user: CurrentUser, session: DbSession):
    await PasswordService(session).change(user.id, data)
    return ApiResponse[None](message="Contraseña actualizada. Inicia sesión nuevamente.", data=None)


@router.post("/forgot-password", response_model=ApiResponse[None], status_code=202)
async def forgot_password(data: PasswordForgot, session: DbSession, background: BackgroundTasks):
    delivery = await PasswordService(session).request_reset(str(data.email))
    if delivery is not None:
        background.add_task(send_password_code, *delivery)
    return ApiResponse[None](
        message="Si la cuenta está disponible, recibirás un código por correo.", data=None
    )


@router.post("/reset-password", response_model=ApiResponse[None])
async def reset_password(data: PasswordReset, session: DbSession):
    await PasswordService(session).reset(data)
    return ApiResponse[None](
        message="Contraseña restablecida. Inicia sesión nuevamente.", data=None
    )

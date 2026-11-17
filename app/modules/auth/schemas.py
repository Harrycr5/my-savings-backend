from typing import Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field, SecretStr

from ..users.schemas import UserSessionRead


class TokenRead(BaseModel):
    access_token: str
    refresh_token: str
    expires_in: int
    token_type: Literal["bearer"] = "bearer"
    user: UserSessionRead


class RefreshRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    refresh_token: SecretStr = Field(min_length=1, max_length=512)


class PasswordChange(BaseModel):
    model_config = ConfigDict(extra="forbid")

    current_password: SecretStr = Field(min_length=1, max_length=128)
    new_password: SecretStr = Field(min_length=12, max_length=128)


class PasswordForgot(BaseModel):
    model_config = ConfigDict(extra="forbid")

    email: EmailStr


class PasswordReset(PasswordForgot):
    code: str = Field(pattern=r"^[0-9]{6}$")
    new_password: SecretStr = Field(min_length=12, max_length=128)

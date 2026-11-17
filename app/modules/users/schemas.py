from datetime import datetime
from typing import TYPE_CHECKING, Annotated
from uuid import UUID

from pydantic import (
    BaseModel,
    ConfigDict,
    EmailStr,
    Field,
    SecretStr,
    StringConstraints,
    model_validator,
)

from app.core.filters import SearchFilters

from ..profiles.schemas import ProfileSimpleRead

if TYPE_CHECKING:
    from app.modules.users.models import User


class UserCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    email: EmailStr

    username: str = Field(
        min_length=3,
        max_length=50,
        pattern=r"^[a-zA-Z0-9_]+$",
    )

    name: str = Field(min_length=1, max_length=100)
    last_name: str = Field(min_length=1, max_length=100)

    password: SecretStr = Field(
        min_length=12,
        max_length=128,
    )


PersonalName = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True,
        min_length=1,
        max_length=100,
    ),
]


class UserUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: PersonalName | None = None
    last_name: PersonalName | None = None

    @model_validator(mode="after")
    def validate_changes(self):
        if not self.model_fields_set:
            raise ValueError("Envía al menos un campo para actualizar.")

        for field in self.model_fields_set:
            if getattr(self, field) is None:
                raise ValueError(f"El campo {field} no acepta null.")

        return self


class UserAdminUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    profile_id: UUID | None = None
    is_active: bool | None = None

    @model_validator(mode="after")
    def validate_changes(self):
        if not self.model_fields_set:
            raise ValueError("Envía al menos un campo para actualizar.")
        for field in self.model_fields_set:
            if getattr(self, field) is None:
                raise ValueError(f"El campo {field} no acepta null.")
        return self


class UserRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    email: EmailStr
    username: str
    name: str
    last_name: str
    is_active: bool
    is_admin: bool
    profile_id: UUID
    created_at: datetime
    updated_at: datetime


class UserSimpleRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    username: str
    name: str
    last_name: str
    is_active: bool
    is_admin: bool


class UserSessionRead(UserSimpleRead):
    profile: ProfileSimpleRead
    permissions: list[str]

    @classmethod
    def from_user(cls, user: "User") -> "UserSessionRead":
        return cls(
            **UserSimpleRead.model_validate(user).model_dump(),
            profile=ProfileSimpleRead.model_validate(user.profile),
            permissions=sorted({permission.code for permission in user.profile.permissions}),
        )


class UserFilters(SearchFilters):
    name: str | None = Field(default=None, max_length=100)
    last_name: str | None = Field(default=None, max_length=100)
    username: str | None = Field(default=None, max_length=50)
    email: str | None = Field(default=None, max_length=254)
    profile_id: UUID | None = None
    is_active: bool | None = None
    is_admin: bool | None = None

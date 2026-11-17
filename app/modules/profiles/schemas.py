from datetime import datetime
from typing import Annotated
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

from app.core.filters import SearchFilters

DisplayName = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True,
        min_length=1,
        max_length=100,
    ),
]


class ProfileCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: str = Field(
        min_length=1,
        max_length=50,
        pattern=r"^[a-z][a-z0-9_]*$",
    )
    name: DisplayName
    description: str | None = Field(default=None, max_length=255)


class ProfilePermissionsAdd(BaseModel):
    model_config = ConfigDict(extra="forbid")

    permission_ids: list[UUID] = Field(max_length=500)


class ProfilePermissionsRemove(ProfilePermissionsAdd):
    pass


class PermissionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    code: str
    name: str
    description: str | None


class ProfileRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    code: str
    name: str
    description: str | None
    is_active: bool
    created_at: datetime
    updated_at: datetime


class ProfileSimpleRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    code: str
    name: str
    description: str | None
    is_active: bool


class ProfileDetailRead(ProfileSimpleRead):
    permissions: list[PermissionRead]


class PermissionFilters(SearchFilters):
    name: str | None = Field(default=None, max_length=100)
    code: str | None = Field(default=None, max_length=100)
    description: str | None = Field(default=None, max_length=255)


class ProfileFilters(PermissionFilters):
    is_active: bool | None = None

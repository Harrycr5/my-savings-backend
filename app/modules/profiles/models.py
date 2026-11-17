from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar

from sqlalchemy import (
    Boolean,
    Column,
    ForeignKey,
    String,
    Table,
    Uuid,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.db.mixins import TimestampMixin, UUIDMixin

if TYPE_CHECKING:
    from ..users.models import User


profile_permissions = Table(
    "profile_permissions",
    Base.metadata,
    Column(
        "profile_id",
        Uuid(as_uuid=True),
        ForeignKey("profiles.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column(
        "permission_id",
        Uuid(as_uuid=True),
        ForeignKey("permissions.id", ondelete="CASCADE"),
        primary_key=True,
    ),
)


class Profile(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "profiles"

    code: Mapped[str] = mapped_column(
        String(50),
        unique=True,
        nullable=False,
    )

    name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )

    description: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )

    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        server_default=text("true"),
    )

    users: Mapped[list[User]] = relationship(
        back_populates="profile",
        passive_deletes="all",
        lazy="raise",
    )

    permissions: Mapped[list[Permission]] = relationship(
        secondary=profile_permissions,
        back_populates="profiles",
        passive_deletes=True,
        lazy="raise",
    )


class Permission(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "permissions"

    __permission_actions__: ClassVar[tuple[str, ...]] = ("read",)

    code: Mapped[str] = mapped_column(
        String(100),
        unique=True,
        nullable=False,
    )

    name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )

    description: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )

    profiles: Mapped[list[Profile]] = relationship(
        secondary=profile_permissions,
        back_populates="permissions",
        passive_deletes=True,
        lazy="raise",
    )

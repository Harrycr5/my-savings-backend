from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import Boolean, ForeignKey, String, Uuid, text
from sqlalchemy.orm import Mapped, mapped_column, relationship, validates

from app.db.base import Base
from app.db.mixins import TimestampMixin, UUIDMixin

if TYPE_CHECKING:
    from ..profiles.models import Profile


class User(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "users"

    email: Mapped[str] = mapped_column(
        String(254),
        unique=True,
        nullable=False,
    )

    doc_number: Mapped[str | None] = mapped_column(
        String(8),
        unique=True,
        nullable=True,
    )

    avatar_url: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )

    username: Mapped[str] = mapped_column(
        String(50),
        unique=True,
        nullable=False,
    )

    name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )

    last_name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )

    password_hash: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        server_default=text("true"),
    )

    profile_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("profiles.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )

    is_admin: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=text("false")
    )

    profile: Mapped[Profile] = relationship(
        back_populates="users",
        lazy="raise",
    )

    @validates("doc_number")
    def validate_doc_number(self, key: str, value: str | None) -> str | None:
        if value is not None and (
            not isinstance(value, str) or not value.isdigit() or len(value) != 8
        ):
            raise ValueError("doc_number debe contener exactamente 8 dígitos.")
        return value

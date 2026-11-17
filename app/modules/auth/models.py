from datetime import datetime
from typing import ClassVar
from uuid import UUID

from sqlalchemy import DateTime, ForeignKey, Integer, String, Uuid, text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.mixins import TimestampMixin, UUIDMixin


class AuthSession(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "auth_sessions"
    __permission_actions__: ClassVar[tuple[str, ...]] = ()

    user_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    refresh_token_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class PasswordResetCode(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "password_reset_codes"
    __permission_actions__: ClassVar[tuple[str, ...]] = ()

    user_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), unique=True
    )
    code_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    requested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    attempts: Mapped[int] = mapped_column(Integer, default=0, server_default=text("0"))
    consumed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

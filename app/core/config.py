from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import EmailStr, Field, PostgresDsn, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

# Raíz del proyecto: contiene el archivo .env
BASE_DIR = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=BASE_DIR / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # Aplicación
    app_name: str = "FastAPI Starter"
    app_version: str = "0.1.0"
    environment: Literal["development", "testing", "production"] = "development"
    debug: bool = False

    # Base de datos
    database_url: PostgresDsn

    # Orígenes exactos del frontend. Sin cookies: autenticación Bearer.
    cors_origins: list[str] = Field(default_factory=list)

    # Autenticación
    jwt_secret_key: str = Field(min_length=32, repr=False)
    jwt_algorithm: Literal["HS256"] = "HS256"
    access_token_expire_minutes: int = Field(default=15, gt=0)
    refresh_token_expire_days: int = Field(default=7, gt=0)

    # Correo para códigos de recuperación; desactivado hasta configurarlo.
    smtp_host: str | None = None
    smtp_port: int = Field(default=587, ge=1, le=65535)
    smtp_username: str | None = None
    smtp_password: SecretStr | None = None
    smtp_from_email: EmailStr | None = None
    smtp_use_tls: bool = False
    smtp_start_tls: bool = True
    password_reset_expire_minutes: int = Field(default=10, ge=1, le=30)
    password_reset_max_attempts: int = Field(default=5, ge=1, le=10)
    password_reset_cooldown_seconds: int = Field(default=60, ge=30)


@lru_cache
def get_settings() -> Settings:
    return Settings()

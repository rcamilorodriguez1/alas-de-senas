"""Configuración de la aplicación desde variables de entorno y `.env` (§19.4, B49)."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal, Self
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

REPO_ROOT = Path(__file__).resolve().parents[4]

DEV_JWT_SECRET = "secreto-solo-para-desarrollo-local-no-usar-en-produccion"  # noqa: S105 — valor público solo para desarrollo; producción lo rechaza
MIN_JWT_SECRET_LENGTH = 32
MIN_PASSWORD_BYTES = 8
MAX_PASSWORD_BYTES = 72  # límite de bcrypt (§11, B27)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=REPO_ROOT / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_env: Literal["development", "test", "production"] = "development"
    database_url: str = "postgresql+psycopg://alas:alas@localhost:5433/alas_de_senas"
    database_url_test: str = "postgresql+psycopg://alas:alas@localhost:5433/alas_test"
    jwt_secret: str = DEV_JWT_SECRET
    access_token_minutes: int = Field(default=15, gt=0)
    refresh_token_days: int = Field(default=7, gt=0)
    app_timezone: str = "America/Bogota"
    admin_email: str | None = None
    admin_password: str | None = None
    hearts_enabled: bool = True
    demo_email: str = "demo@alasdesenas.co"
    demo_password: str | None = None
    content_dir: Path = Path("content")
    media_dir: Path = Path("apps/web/public/media")
    web_dist_dir: Path = Path("apps/web/dist")
    # IP real del cliente detrás de proxies (D-035). 0 = no se confía en X-Forwarded-For.
    trusted_proxy_hops: int = Field(default=0, ge=0, le=5)
    client_ip_header: str | None = None  # p. ej. True-Client-IP, solo si se verificó

    @field_validator(
        "admin_email", "admin_password", "demo_password", "client_ip_header", mode="before"
    )
    @classmethod
    def _empty_as_none(cls, value: object) -> object:
        # `.env.example` deja estas variables vacías («ADMIN_EMAIL=»): significan «no configurado».
        if isinstance(value, str) and not value.strip():
            return None
        return value

    @field_validator("app_timezone")
    @classmethod
    def _valid_timezone(cls, value: str) -> str:
        # Falla al arrancar y no en la primera fecha (B45: en Windows requiere tzdata).
        try:
            ZoneInfo(value)
        except (ZoneInfoNotFoundError, ValueError) as exc:
            raise ValueError(f"APP_TIMEZONE no es una zona horaria válida: {value}") from exc
        return value

    @field_validator("content_dir", "media_dir", "web_dist_dir", mode="after")
    @classmethod
    def _absolute_from_repo_root(cls, value: Path) -> Path:
        return value if value.is_absolute() else (REPO_ROOT / value).resolve()

    @model_validator(mode="after")
    def _check_admin(self) -> Self:
        if (self.admin_email is None) != (self.admin_password is None):
            raise ValueError("ADMIN_EMAIL y ADMIN_PASSWORD van juntos: define ambos o ninguno.")
        if self.admin_password is not None:
            size = len(self.admin_password.encode("utf-8"))
            if not MIN_PASSWORD_BYTES <= size <= MAX_PASSWORD_BYTES:
                raise ValueError(
                    f"ADMIN_PASSWORD debe tener entre {MIN_PASSWORD_BYTES} y "
                    f"{MAX_PASSWORD_BYTES} bytes (la ñ y las tildes ocupan 2)."
                )
        return self

    @model_validator(mode="after")
    def _check_production(self) -> Self:
        if len(self.jwt_secret) < MIN_JWT_SECRET_LENGTH:
            raise ValueError(f"JWT_SECRET debe tener al menos {MIN_JWT_SECRET_LENGTH} caracteres.")
        if self.is_production:
            missing = [
                name.upper()
                for name in ("database_url", "jwt_secret")
                if name not in self.model_fields_set
            ]
            if missing:
                raise ValueError(f"En producción son obligatorias: {', '.join(missing)}.")
            if self.jwt_secret == DEV_JWT_SECRET:
                raise ValueError("En producción JWT_SECRET no puede ser el secreto de desarrollo.")
        return self

    @property
    def is_production(self) -> bool:
        return self.app_env == "production"


@lru_cache
def get_settings() -> Settings:
    return Settings()

"""Tarea 0.3 — configuración con pydantic-settings (§19.4, §11)."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from pydantic import ValidationError

from app.core.config import DEV_JWT_SECRET, Settings, get_settings

REPO_ROOT = Path(__file__).resolve().parents[4]

ENV_VARS = (
    "APP_ENV",
    "DATABASE_URL",
    "DATABASE_URL_TEST",
    "JWT_SECRET",
    "ACCESS_TOKEN_MINUTES",
    "REFRESH_TOKEN_DAYS",
    "APP_TIMEZONE",
    "ADMIN_EMAIL",
    "ADMIN_PASSWORD",
    "HEARTS_ENABLED",
    "DEMO_EMAIL",
    "DEMO_PASSWORD",
    "CONTENT_DIR",
    "MEDIA_DIR",
    "WEB_DIST_DIR",
)

VALID_PROD_SECRET = "secreto-de-produccion-con-mas-de-32-caracteres-xyz"
PROD_DB_URL = "postgresql+psycopg://alas:clave@db.example.com:5432/alas"


@pytest.fixture(autouse=True)
def clean_env(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """CI define DATABASE_URL, JWT_SECRET, etc.: cada prueba parte de un entorno limpio."""
    for name in ENV_VARS:
        monkeypatch.delenv(name, raising=False)
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


# --- Desarrollo: arranca sin .env -------------------------------------------------------------


def test_dev_secret_es_largo() -> None:
    assert len(DEV_JWT_SECRET) >= 32


def test_desarrollo_arranca_sin_env_con_valores_por_defecto() -> None:
    settings = Settings(_env_file=None)

    assert settings.app_env == "development"
    assert settings.is_production is False
    assert "localhost:5433/alas_de_senas" in settings.database_url
    assert settings.database_url.startswith("postgresql+psycopg://")
    assert "localhost:5433/alas_test" in settings.database_url_test
    assert settings.jwt_secret == DEV_JWT_SECRET
    assert settings.access_token_minutes == 15
    assert settings.refresh_token_days == 7
    assert settings.app_timezone == "America/Bogota"
    assert settings.admin_email is None
    assert settings.admin_password is None
    assert settings.hearts_enabled is True
    assert settings.demo_email == "demo@alasdesenas.co"
    assert settings.demo_password is None


def test_rutas_por_defecto_son_absolutas_desde_la_raiz_del_repositorio() -> None:
    settings = Settings(_env_file=None)

    assert settings.content_dir.is_absolute()
    assert settings.media_dir.is_absolute()
    assert settings.web_dist_dir.is_absolute()
    assert settings.content_dir.resolve() == REPO_ROOT / "content"
    assert settings.media_dir.resolve() == REPO_ROOT / "apps" / "web" / "public" / "media"
    assert settings.web_dist_dir.resolve() == REPO_ROOT / "apps" / "web" / "dist"


def test_variables_de_entorno_sobrescriben_los_valores(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://otro:otro@localhost:5433/otra")
    monkeypatch.setenv("ACCESS_TOKEN_MINUTES", "30")
    monkeypatch.setenv("HEARTS_ENABLED", "false")
    monkeypatch.setenv("APP_TIMEZONE", "America/Bogota")
    monkeypatch.setenv("ADMIN_EMAIL", "admin@alasdesenas.co")
    monkeypatch.setenv("ADMIN_PASSWORD", "Clave-Segura-1")  # van juntos (revisión Grupo 2)

    settings = Settings(_env_file=None)

    assert settings.database_url == "postgresql+psycopg://otro:otro@localhost:5433/otra"
    assert settings.access_token_minutes == 30
    assert settings.hearts_enabled is False
    assert settings.admin_email == "admin@alasdesenas.co"


def test_app_env_invalido_es_rechazado(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_ENV", "staging")
    with pytest.raises(ValidationError):
        Settings(_env_file=None)


def test_get_settings_usa_cache() -> None:
    assert get_settings() is get_settings()


def test_get_settings_cache_clear_relee_el_entorno(monkeypatch: pytest.MonkeyPatch) -> None:
    first = get_settings()
    monkeypatch.setenv("ACCESS_TOKEN_MINUTES", "42")
    get_settings.cache_clear()
    second = get_settings()

    assert second is not first
    assert second.access_token_minutes == 42


# --- Producción: falla rápido si falta configuración crítica ----------------------------------


def _set_production(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_ENV", "production")


def test_produccion_falla_sin_database_url(monkeypatch: pytest.MonkeyPatch) -> None:
    _set_production(monkeypatch)
    monkeypatch.setenv("JWT_SECRET", VALID_PROD_SECRET)

    with pytest.raises(ValidationError):
        Settings(_env_file=None)


def test_produccion_falla_sin_jwt_secret(monkeypatch: pytest.MonkeyPatch) -> None:
    _set_production(monkeypatch)
    monkeypatch.setenv("DATABASE_URL", PROD_DB_URL)

    with pytest.raises(ValidationError):
        Settings(_env_file=None)


def test_produccion_falla_sin_ninguna_de_las_dos(monkeypatch: pytest.MonkeyPatch) -> None:
    _set_production(monkeypatch)

    with pytest.raises(ValidationError):
        Settings(_env_file=None)


def test_produccion_falla_con_el_secreto_de_desarrollo(monkeypatch: pytest.MonkeyPatch) -> None:
    _set_production(monkeypatch)
    monkeypatch.setenv("DATABASE_URL", PROD_DB_URL)
    monkeypatch.setenv("JWT_SECRET", DEV_JWT_SECRET)

    with pytest.raises(ValidationError):
        Settings(_env_file=None)


@pytest.mark.parametrize("secret", ["corto", "a" * 31])
def test_produccion_falla_con_secreto_de_menos_de_32_caracteres(
    monkeypatch: pytest.MonkeyPatch, secret: str
) -> None:
    _set_production(monkeypatch)
    monkeypatch.setenv("DATABASE_URL", PROD_DB_URL)
    monkeypatch.setenv("JWT_SECRET", secret)

    with pytest.raises(ValidationError):
        Settings(_env_file=None)


def test_produccion_con_secreto_de_exactamente_32_caracteres_arranca(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _set_production(monkeypatch)
    monkeypatch.setenv("DATABASE_URL", PROD_DB_URL)
    monkeypatch.setenv("JWT_SECRET", "b" * 32)

    settings = Settings(_env_file=None)

    assert settings.jwt_secret == "b" * 32


def test_produccion_con_configuracion_valida_arranca(monkeypatch: pytest.MonkeyPatch) -> None:
    _set_production(monkeypatch)
    monkeypatch.setenv("DATABASE_URL", PROD_DB_URL)
    monkeypatch.setenv("JWT_SECRET", VALID_PROD_SECRET)

    settings = Settings(_env_file=None)

    assert settings.app_env == "production"
    assert settings.is_production is True
    assert settings.database_url == PROD_DB_URL
    assert settings.jwt_secret == VALID_PROD_SECRET


def test_zona_horaria_invalida_falla_al_arrancar(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_TIMEZONE", "America/NoExiste")
    with pytest.raises(ValidationError):
        Settings(_env_file=None)


@pytest.mark.parametrize("name", ["ACCESS_TOKEN_MINUTES", "REFRESH_TOKEN_DAYS"])
def test_plazos_de_tokens_deben_ser_positivos(monkeypatch: pytest.MonkeyPatch, name: str) -> None:
    monkeypatch.setenv(name, "0")
    with pytest.raises(ValidationError):
        Settings(_env_file=None)

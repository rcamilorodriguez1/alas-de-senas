"""Tarea 11.5 — bloqueo del usuario de demostración en producción (§17.4, B84, R10.9).

En producción `seed_demo` se niega salvo que se pase `allow_production=True` **y** exista
`DEMO_PASSWORD`. La negativa ocurre antes de tocar la base de datos: estas pruebas sustituyen
`get_engine` por una función que falla si alguien la llama.

El módulo se importa en tiempo de ejecución (pruebas primero): mientras no exista, cada prueba
falla con `ModuleNotFoundError: app.content.demo`.
"""

from __future__ import annotations

import dataclasses
import importlib
from datetime import UTC, datetime
from types import ModuleType

import pytest
from sqlalchemy.engine import Engine
from typer.testing import CliRunner

from app.cli import app
from app.core.config import Settings, get_settings
from tests.fakes import FakeClock

runner = CliRunner()
WIDE = {"COLUMNS": "200", "NO_COLOR": "1", "TERM": "dumb"}
REMOTE_URL = "postgresql+psycopg://u:p@db.example.com:5432/alas"
PROD_SECRET = "s" * 48
NOW = datetime(2026, 11, 4, 15, 0, tzinfo=UTC)


def demo_module() -> ModuleType:
    # Se importa en tiempo de ejecución: el módulo aún no existe (pruebas primero).
    return importlib.import_module("app.content.demo")


def production(*, demo_password: str | None) -> Settings:
    return Settings(
        _env_file=None,
        app_env="production",
        database_url=REMOTE_URL,
        jwt_secret=PROD_SECRET,
        demo_password=demo_password,
    )


def _no_database() -> Engine:
    raise AssertionError("seed_demo no debe abrir la base de datos en producción sin permiso")


def guarded_demo(monkeypatch: pytest.MonkeyPatch) -> ModuleType:
    """El módulo de la demo con `get_engine` sustituido: cualquier acceso a la BD falla."""
    module = demo_module()
    import app.infra.db as db

    monkeypatch.setattr(db, "get_engine", _no_database)
    # Por si el módulo hizo `from app.infra.db import get_engine`.
    monkeypatch.setattr(module, "get_engine", _no_database, raising=False)
    return module


# ---------------------------------------------------------------- interfaz pública


def test_contrasena_de_desarrollo_por_defecto() -> None:
    assert demo_module().DEMO_DEV_PASSWORD == "demo-alas-2026"


def test_demo_result_es_un_dataclass_inmutable() -> None:
    result_cls = demo_module().DemoResult
    result = result_cls(created=True, email="demo@alasdesenas.co")

    assert dataclasses.is_dataclass(result_cls)
    assert result.created is True
    assert result.email == "demo@alasdesenas.co"
    with pytest.raises(dataclasses.FrozenInstanceError):
        result.created = False


def test_demo_error_es_una_excepcion() -> None:
    assert issubclass(demo_module().DemoError, Exception)


# ---------------------------------------------------------------- bloqueo en producción (B84)


def test_produccion_sin_allow_production_se_niega(monkeypatch: pytest.MonkeyPatch) -> None:
    demo = guarded_demo(monkeypatch)
    settings = production(demo_password="Clave-Demo-Segura-1")

    with pytest.raises(demo.DemoError) as excinfo:
        demo.seed_demo(settings, FakeClock(NOW))

    assert "producción" in str(excinfo.value)
    assert "--allow-production" in str(excinfo.value)


def test_produccion_con_allow_production_pero_sin_demo_password_se_niega(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    demo = guarded_demo(monkeypatch)
    settings = production(demo_password=None)

    with pytest.raises(demo.DemoError) as excinfo:
        demo.seed_demo(settings, FakeClock(NOW), allow_production=True)

    assert "DEMO_PASSWORD" in str(excinfo.value)


def test_produccion_con_reset_tampoco_pasa_sin_permiso(monkeypatch: pytest.MonkeyPatch) -> None:
    demo = guarded_demo(monkeypatch)
    settings = production(demo_password="Clave-Demo-Segura-1")

    with pytest.raises(demo.DemoError):
        demo.seed_demo(settings, FakeClock(NOW), reset=True)


def test_produccion_nunca_usa_la_contrasena_de_desarrollo(monkeypatch: pytest.MonkeyPatch) -> None:
    """Sin DEMO_PASSWORD en producción no hay respaldo con `demo-alas-2026` (B84)."""
    demo = guarded_demo(monkeypatch)
    settings = production(demo_password=None)

    with pytest.raises(demo.DemoError):
        demo.seed_demo(settings, FakeClock(NOW), reset=True, allow_production=True)


# ---------------------------------------------------------------- CLI


def _production_env(monkeypatch: pytest.MonkeyPatch, *, demo_password: str) -> None:
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("DATABASE_URL", REMOTE_URL)
    monkeypatch.setenv("JWT_SECRET", PROD_SECRET)
    monkeypatch.setenv("DEMO_PASSWORD", demo_password)
    get_settings.cache_clear()


def test_cli_seed_demo_en_produccion_sin_bandera_sale_con_1(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    guarded_demo(monkeypatch)
    _production_env(monkeypatch, demo_password="Clave-Demo-Segura-1")
    try:
        result = runner.invoke(app, ["db", "seed-demo"], env=WIDE)
    finally:
        get_settings.cache_clear()

    assert result.exit_code == 1, result.output
    assert "producción" in result.output
    assert "--allow-production" in result.output
    assert "Pendiente" not in result.output


def test_cli_seed_demo_reset_en_produccion_sin_bandera_sale_con_1(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    guarded_demo(monkeypatch)
    _production_env(monkeypatch, demo_password="Clave-Demo-Segura-1")
    try:
        result = runner.invoke(app, ["db", "seed-demo", "--reset"], env=WIDE)
    finally:
        get_settings.cache_clear()

    assert result.exit_code == 1, result.output
    assert "producción" in result.output


def test_cli_seed_demo_en_produccion_sin_demo_password_sale_con_1(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    guarded_demo(monkeypatch)
    _production_env(monkeypatch, demo_password="")  # vacío ⇒ no configurado
    try:
        result = runner.invoke(app, ["db", "seed-demo", "--allow-production"], env=WIDE)
    finally:
        get_settings.cache_clear()

    assert result.exit_code == 1, result.output
    assert "DEMO_PASSWORD" in result.output

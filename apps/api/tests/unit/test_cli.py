"""Tarea 0.7 — CLI `alas` (Typer, §19.3). Solo se prueban comandos que no lanzan procesos."""

from __future__ import annotations

from pathlib import Path

import pytest
from typer.testing import CliRunner

from app.cli import app
from app.core.config import Settings

runner = CliRunner()
WIDE = {"COLUMNS": "200", "NO_COLOR": "1", "TERM": "dumb"}


def _help(*args: str) -> str:
    result = runner.invoke(app, [*args, "--help"], env=WIDE)
    assert result.exit_code == 0, result.output
    return result.output


@pytest.mark.parametrize(
    "command",
    ["dev", "check", "gen-api", "db", "content", "camera-assets", "e2e", "start-prod"],
)
def test_help_lista_los_comandos_principales(command: str) -> None:
    assert command in _help()


@pytest.mark.parametrize("command", ["up", "migrate", "seed", "seed-demo", "reset"])
def test_db_help_lista_sus_subcomandos(command: str) -> None:
    assert command in _help("db")


@pytest.mark.parametrize("command", ["placeholders", "videos", "check", "all"])
def test_content_help_lista_sus_subcomandos(command: str) -> None:
    assert command in _help("content")


@pytest.mark.parametrize(
    "url",
    [
        "postgresql+psycopg://alas:alas@localhost:5433/alas_de_senas",
        "postgresql+psycopg://alas:alas@localhost:5433/alas_test_respaldo",
    ],
)
def test_e2e_se_niega_si_la_base_de_prueba_no_termina_en_test(
    monkeypatch: pytest.MonkeyPatch, url: str
) -> None:
    """`alas e2e` migra, siembra y crea usuarios: nunca en la base de desarrollo (D-034.4).
    Se niega antes de compilar o de tocar cualquier base."""
    import app.cli as cli

    def no_build() -> None:
        raise AssertionError("no debía compilar la SPA")

    monkeypatch.setattr(cli, "_build_web", no_build)
    monkeypatch.setattr(
        cli,
        "get_settings",
        lambda: Settings(_env_file=None, app_env="development", database_url_test=url),
    )
    result = runner.invoke(app, ["e2e"], env=WIDE)

    assert result.exit_code == 1
    assert "_test" in result.output


def test_comando_desconocido_falla() -> None:
    result = runner.invoke(app, ["no-existe"], env=WIDE)
    assert result.exit_code != 0


def test_db_reset_se_niega_a_borrar_una_base_remota(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.core.config import get_settings

    monkeypatch.setenv("APP_ENV", "development")
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://u:p@db.example.com:5432/alas")
    get_settings.cache_clear()
    try:
        result = runner.invoke(app, ["db", "reset", "--yes"], env=WIDE)
    finally:
        get_settings.cache_clear()
    assert result.exit_code == 1
    assert "solo borra bases locales" in result.output


def test_content_check_con_errores_sale_con_codigo_1(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Contenido real con un `media_dir` vacío: faltan todos los videos (Grupo 2)."""
    from app.core.config import get_settings

    monkeypatch.setenv("MEDIA_DIR", str(tmp_path / "media"))
    get_settings.cache_clear()
    try:
        result = runner.invoke(app, ["content", "check", "--skip-raw"], env=WIDE)
    finally:
        get_settings.cache_clear()
    assert result.exit_code == 1
    assert "Falta el video de «hola». Ejecuta alas content all." in result.output

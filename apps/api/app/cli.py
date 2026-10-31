"""CLI `alas` (Typer, §19.3). Se ejecuta desde la raíz del repositorio con `uv run alas …`."""

from __future__ import annotations

import difflib
import json
import os
import shutil
import signal
import subprocess
import sys
import tempfile
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Annotated

import typer
from sqlalchemy import create_engine, make_url, text

from app.core.config import REPO_ROOT, Settings, get_settings

API_DIR = REPO_ROOT / "apps" / "api"
WEB_DIR = REPO_ROOT / "apps" / "web"
ALEMBIC_INI = API_DIR / "alembic.ini"
API_TYPES = WEB_DIR / "src" / "lib" / "api-types.ts"
OPENAPI_JSON = REPO_ROOT / "openapi.json"
LOCAL_HOSTS = {"localhost", "127.0.0.1", "::1"}

app = typer.Typer(help="Herramientas de Alas de Señas.", no_args_is_help=True)
db_app = typer.Typer(help="Base de datos de desarrollo.", no_args_is_help=True)
content_app = typer.Typer(help="Pipeline de contenido (§6.4).", no_args_is_help=True)
app.add_typer(db_app, name="db")
app.add_typer(content_app, name="content")


@app.callback()
def _utf8_output() -> None:
    # La consola de Windows usa cp1252 al redirigir la salida y no puede escribir «→ ✓ ✗».
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if callable(reconfigure):
            reconfigure(encoding="utf-8", errors="replace")


@contextmanager
def _content_errors() -> Iterator[None]:
    """Convierte los errores de contenido o de un manifiesto dañado en un mensaje en español."""
    from pydantic import ValidationError

    from app.content.errors import ContentError

    try:
        yield
    except ContentError as exc:
        typer.secho(str(exc), fg="red")
        raise typer.Exit(code=1) from exc
    except ValidationError as exc:
        typer.secho(
            "media/manifest.json está dañado. Restáuralo desde git o bórralo y ejecuta "
            "alas content all.",
            fg="red",
        )
        raise typer.Exit(code=1) from exc


def _pending(group: int) -> None:
    typer.echo(f"Pendiente de la fase {group} (docs/specs/tasks.md, Grupo {group}).")


def _executable(name: str) -> str:
    """Ruta completa del ejecutable (resuelve `npm.cmd` en Windows)."""
    found = shutil.which(name)
    if found is None:
        typer.secho(f"No se encontró «{name}». Revisa los requisitos previos (§19.6).", fg="red")
        raise typer.Exit(code=1)
    return found


def _run(cmd: list[str], cwd: Path = REPO_ROOT) -> int:
    return subprocess.run(cmd, cwd=cwd, check=False).returncode


def _python(*args: str) -> list[str]:
    return [sys.executable, "-m", *args]


@app.command()
def dev() -> None:
    """Inicia la API (puerto 8000, con recarga) y Vite (puerto 5173). Ctrl+C detiene ambos."""
    # En Mac/Linux cada servidor va en su propio grupo de procesos para detenerlo completo.
    new_session = sys.platform != "win32"
    api = subprocess.Popen(
        _python(
            "uvicorn",
            "app.main:app",
            "--reload",
            "--reload-dir",
            str(API_DIR / "app"),
            "--port",
            "8000",
            "--app-dir",
            str(API_DIR),
        ),
        cwd=REPO_ROOT,
        start_new_session=new_session,
    )
    web = subprocess.Popen(
        [_executable("npm"), "run", "dev"], cwd=WEB_DIR, start_new_session=new_session
    )
    typer.echo("API en http://localhost:8000 · web en http://localhost:5173 (Ctrl+C para salir)")
    try:
        while api.poll() is None and web.poll() is None:
            try:
                api.wait(timeout=0.5)
            except subprocess.TimeoutExpired:
                continue
    except KeyboardInterrupt:
        typer.echo("Deteniendo…")
    finally:
        for process in (api, web):
            _stop_tree(process)


def _stop_tree(process: subprocess.Popen[bytes]) -> None:
    """Detiene el proceso y sus hijos (el recargador de uvicorn, Vite bajo npm)."""
    if process.poll() is not None:
        return
    if sys.platform == "win32":
        # En Windows terminate() solo cierra el proceso directo y deja vivos a los hijos con el
        # puerto ocupado; taskkill /T termina el árbol completo.
        subprocess.run(
            ["taskkill", "/T", "/F", "/PID", str(process.pid)], capture_output=True, check=False
        )
    else:
        os.killpg(process.pid, signal.SIGTERM)
    try:
        process.wait(timeout=10)
    except subprocess.TimeoutExpired:
        process.kill()


@app.command()
def check() -> None:
    """Verificación completa: ruff, mypy, pytest, ESLint, tsc, Vitest y tipos de la API."""
    npm = _executable("npm")
    steps: list[tuple[str, list[str], Path]] = [
        ("ruff check", _python("ruff", "check", "apps/api"), REPO_ROOT),
        ("ruff format --check", _python("ruff", "format", "--check", "apps/api"), REPO_ROOT),
        ("mypy --strict", _python("mypy", "apps/api/app"), REPO_ROOT),
        (
            "pytest",
            _python(
                "pytest",
                "-m",
                "not e2e",
                "--cov=app.domain",
                "--cov-report=term-missing:skip-covered",
                "--cov-fail-under=95",
            ),
            REPO_ROOT,
        ),
        ("ESLint", [npm, "run", "lint"], WEB_DIR),
        ("tsc", [npm, "run", "typecheck"], WEB_DIR),
        ("Vitest", [npm, "run", "test", "--", "--run"], WEB_DIR),
        ("tipos de la API", _python("app.cli", "gen-api", "--check"), REPO_ROOT),
    ]
    for name, cmd, cwd in steps:
        typer.secho(f"→ {name}", fg="cyan", bold=True)
        if _run(cmd, cwd) != 0:
            typer.secho(f"✗ Falló: {name}", fg="red", bold=True)
            raise typer.Exit(code=1)
    typer.secho("✓ alas check en verde", fg="green", bold=True)


def _openapi_schema() -> str:
    from app.main import create_app

    # Siempre con la configuración de desarrollo: el contrato no depende del entorno.
    schema = create_app(Settings(_env_file=None, app_env="development")).openapi()
    return json.dumps(schema, ensure_ascii=False, indent=2) + "\n"


def _generate_types(openapi_path: Path, output: Path) -> None:
    code = _run(
        [_executable("npx"), "openapi-typescript", str(openapi_path), "-o", str(output)],
        WEB_DIR,
    )
    if code != 0:
        typer.secho("openapi-typescript falló.", fg="red")
        raise typer.Exit(code=1)


@app.command("gen-api")
def gen_api(
    check_only: Annotated[
        bool, typer.Option("--check", help="No escribe nada; falla si los tipos están viejos.")
    ] = False,
) -> None:
    """Exporta openapi.json y genera apps/web/src/lib/api-types.ts (§8.4)."""
    schema = _openapi_schema()
    if not check_only:
        OPENAPI_JSON.write_text(schema, encoding="utf-8", newline="\n")
        _generate_types(OPENAPI_JSON, API_TYPES)
        typer.echo(f"Tipos generados en {API_TYPES.relative_to(REPO_ROOT).as_posix()}")
        return

    with tempfile.TemporaryDirectory() as tmp:
        tmp_dir = Path(tmp)
        openapi_path = tmp_dir / "openapi.json"
        openapi_path.write_text(schema, encoding="utf-8", newline="\n")
        generated = tmp_dir / "api-types.ts"
        _generate_types(openapi_path, generated)
        expected = generated.read_text(encoding="utf-8").replace("\r\n", "\n")
    current = (
        API_TYPES.read_text(encoding="utf-8").replace("\r\n", "\n") if API_TYPES.exists() else ""
    )
    if current != expected:
        diff = difflib.unified_diff(
            current.splitlines(), expected.splitlines(), "api-types.ts", "generado", lineterm=""
        )
        typer.echo("\n".join(list(diff)[:40]))
        typer.secho(
            "Los tipos de la API están desactualizados: ejecuta `uv run alas gen-api`.", fg="red"
        )
        raise typer.Exit(code=1)
    typer.secho("Tipos de la API al día.", fg="green")


@db_app.command("up")
def db_up() -> None:
    """Levanta PostgreSQL 16 (Docker Compose, puerto 5433)."""
    raise typer.Exit(code=_run([_executable("docker"), "compose", "up", "-d", "--wait"]))


@db_app.command("migrate")
def db_migrate() -> None:
    """Aplica las migraciones (`alembic upgrade head`)."""
    raise typer.Exit(code=_run(_python("alembic", "-c", str(ALEMBIC_INI), "upgrade", "head")))


@db_app.command("seed")
def db_seed() -> None:
    """Valida el contenido (sin raw/) y lo carga de forma idempotente (§6.4)."""
    _run_check(skip_raw=True)
    _seed()


def _seed() -> None:
    from sqlalchemy.exc import IntegrityError
    from sqlalchemy.orm import Session

    from app.content.errors import ContentError
    from app.content.seed import seed_content
    from app.infra.db import get_engine

    settings = get_settings()
    try:
        with Session(get_engine()) as session:
            counts = seed_content(
                session,
                settings.content_dir,
                settings.media_dir,
                admin_email=settings.admin_email,
                admin_password=settings.admin_password,
            )
            session.commit()
    except ContentError as exc:
        typer.secho(str(exc), fg="red")
        raise typer.Exit(code=1) from exc
    except IntegrityError as exc:
        typer.secho(
            "La carga del contenido chocó con datos existentes en la base de datos "
            f"({type(exc.orig).__name__}). Nada se guardó.",
            fg="red",
        )
        raise typer.Exit(code=1) from exc
    typer.secho(
        f"Contenido cargado: {counts.modules} módulos, {counts.nodes} nodos, "
        f"{counts.lessons} lecciones, {counts.signs} señas, {counts.exercises} ejercicios, "
        f"{counts.achievements} logros.",
        fg="green",
    )


@db_app.command("seed-demo")
def db_seed_demo(
    reset: Annotated[bool, typer.Option("--reset", help="Borra y recrea la demo.")] = False,
    allow_production: Annotated[
        bool, typer.Option("--allow-production", help="Permite ejecutarlo en producción.")
    ] = False,
) -> None:
    """Crea el usuario de demostración (§17.4)."""
    _pending(11)


@db_app.command("reset")
def db_reset(
    yes: Annotated[bool, typer.Option("--yes", "-y", help="No pide confirmación.")] = False,
) -> None:
    """Borra y recrea la base de datos de desarrollo y aplica las migraciones."""
    settings = get_settings()
    if settings.is_production:
        typer.secho("`alas db reset` no se puede ejecutar en producción.", fg="red")
        raise typer.Exit(code=1)
    url = make_url(settings.database_url)
    name = url.database
    if not name:
        typer.secho("DATABASE_URL no indica el nombre de la base de datos.", fg="red")
        raise typer.Exit(code=1)
    if url.host not in LOCAL_HOSTS:
        typer.secho(
            f"`alas db reset` solo borra bases locales; DATABASE_URL apunta a «{url.host}».",
            fg="red",
        )
        raise typer.Exit(code=1)
    if not yes:
        typer.confirm(f"Se borrarán TODOS los datos de «{name}». ¿Continuar?", abort=True)

    engine = create_engine(url.set(database="postgres"), isolation_level="AUTOCOMMIT")
    quoted = engine.dialect.identifier_preparer.quote(name)
    with engine.connect() as conn:
        conn.execute(text("DROP DATABASE IF EXISTS " + quoted + " WITH (FORCE)"))
        conn.execute(text("CREATE DATABASE " + quoted))
    engine.dispose()
    typer.echo(f"Base de datos «{name}» recreada.")
    db_migrate()


@content_app.command("placeholders")
def content_placeholders() -> None:
    """Genera los videos de relleno y el manifiesto (D6, D19)."""
    with _content_errors():
        _placeholders()


def _placeholders() -> None:
    from app.content.csv_reader import read_signs_csv
    from app.content.placeholders import generate_placeholders
    from app.content.raw_files import scan_raw

    settings = get_settings()
    slugs = [row.slug for row in read_signs_csv(settings.content_dir / "signs.csv")]
    raw = scan_raw(settings.content_dir / "videos" / "raw", slugs)
    result = generate_placeholders(settings.content_dir, settings.media_dir, set(raw.assets))
    typer.echo(
        f"Videos de relleno: {len(result.created)} generados, {len(result.kept)} sin cambios."
    )


@content_app.command("videos")
def content_videos() -> None:
    """Normaliza los videos e imágenes de content/videos/raw (§6.4, D25)."""
    from app.content.videos import process_videos

    settings = get_settings()
    with _content_errors():
        result = process_videos(settings.content_dir, settings.media_dir)
    typer.echo(
        f"Videos: {len(result.processed)} procesados, {len(result.unchanged)} sin cambios, "
        f"{len(result.removed)} archivos viejos borrados."
    )
    for warning in result.warnings:
        typer.secho(f"  ⚠ {warning}", fg="yellow")
    for error in result.errors:
        typer.secho(f"  ✗ {error}", fg="red")
    if result.errors:
        raise typer.Exit(code=1)


@content_app.command("check")
def content_check(
    skip_raw: Annotated[
        bool, typer.Option("--skip-raw", help="No revisa content/videos/raw (CI).")
    ] = False,
) -> None:
    """Valida el contenido (§6.6) e imprime el reporte; código 1 si hay errores."""
    _run_check(skip_raw=skip_raw)


def _run_check(*, skip_raw: bool) -> None:
    from app.content.validation import check_content

    settings = get_settings()
    report = check_content(settings.content_dir, settings.media_dir, skip_raw=skip_raw)
    typer.echo(report.render())
    if not report.ok:
        raise typer.Exit(code=1)


@content_app.command("all")
def content_all() -> None:
    """placeholders → videos → check → seed (§6.4)."""
    content_placeholders()
    content_videos()
    _run_check(skip_raw=False)
    _seed()


@app.command("camera-assets")
def camera_assets() -> None:
    """Copia el WASM de MediaPipe y descarga los modelos `.task`."""
    _pending(10)


@app.command()
def e2e() -> None:
    """Pruebas de extremo a extremo con Playwright para Python."""
    _pending(11)


@app.command("start-prod")
def start_prod() -> None:
    """Compila la SPA y la sirve con uvicorn sin recarga."""
    _pending(11)


if __name__ == "__main__":
    app()

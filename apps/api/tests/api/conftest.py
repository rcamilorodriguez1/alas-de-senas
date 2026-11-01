"""Pruebas de API contra PostgreSQL real (`alas_test`), §15.

- Al inicio de la ejecución se aplican las migraciones (`alembic upgrade head`) a `alas_test`.
- Después de cada prueba se truncan las tablas de usuario (`TRUNCATE … RESTART IDENTITY CASCADE`).
  No se usa «transacción que se revierte» porque el cierre de lección abre su propia sesión (D21).
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import make_url, select, text
from sqlalchemy.orm import Session

from app.content.seed import seed_content
from app.core.config import Settings, get_settings
from app.infra.db import get_engine
from app.infra.models import Lesson, Module
from app.main import create_app
from tests.unit.content.real_content import CONTENT_DIR, make_media

API_DIR = Path(__file__).resolve().parents[2]
ALEMBIC_INI = API_DIR / "alembic.ini"

# Tablas con datos de usuario que se vacían después de cada prueba. El contenido (módulos,
# lecciones, señas…) se carga una vez y no se trunca.
USER_TABLES: tuple[str, ...] = (
    "favorites",
    "user_achievements",
    "sign_reviews",
    "streaks",
    "daily_activity",
    "review_answers",
    "review_sessions",
    "session_answers",
    "lesson_sessions",
    "refresh_tokens",
    "users",
)


def alembic_config() -> Config:
    return Config(str(ALEMBIC_INI))


@pytest.fixture(scope="session", autouse=True)
def test_database() -> Iterator[str]:
    url = Settings().database_url_test
    if not (make_url(url).database or "").endswith("_test"):
        pytest.exit(f"DATABASE_URL_TEST debe apuntar a una base «*_test»: {url}", returncode=2)
    with pytest.MonkeyPatch.context() as mp:
        mp.setenv("DATABASE_URL", url)
        mp.setenv("DATABASE_URL_TEST", url)
        get_settings.cache_clear()
        get_engine.cache_clear()

        command.upgrade(alembic_config(), "head")
        yield url

        get_engine().dispose()
        get_engine.cache_clear()
        get_settings.cache_clear()


@pytest.fixture(autouse=True)
def truncate_user_tables() -> Iterator[None]:
    yield
    if not USER_TABLES:
        return
    preparer = get_engine().dialect.identifier_preparer
    quoted = ", ".join(preparer.quote(name) for name in USER_TABLES)
    with get_engine().begin() as conn:
        # Todas las tablas de usuario dependen de `users` (FK): si está vacía no hay nada que
        # limpiar y se evita un TRUNCATE lento por prueba (Docker en Windows).
        if conn.execute(text("SELECT EXISTS (SELECT 1 FROM users)")).scalar_one():
            conn.execute(text("TRUNCATE TABLE " + quoted + " RESTART IDENTITY CASCADE"))


@pytest.fixture
def client() -> Iterator[TestClient]:
    with TestClient(create_app()) as test_client:
        yield test_client


@pytest.fixture
def seeded_content(tmp_path_factory: pytest.TempPathFactory) -> None:
    """Garantiza que el contenido REAL de `content/` está sembrado en `alas_test`.

    `tests/api/test_seed.py` trunca las tablas de contenido, así que se comprueba en cada prueba
    y, si `modules` está vacía, se vuelve a sembrar con un `media_dir` temporal.
    """
    with Session(get_engine()) as session:
        has_modules = session.execute(select(Module.id).limit(1)).first() is not None
        has_lessons = session.execute(select(Lesson.id).limit(1)).first() is not None
        if has_modules and has_lessons:
            return
        media_dir = tmp_path_factory.mktemp("seeded-media")
        make_media(media_dir, CONTENT_DIR)
        seed_content(session, CONTENT_DIR, media_dir)
        session.commit()

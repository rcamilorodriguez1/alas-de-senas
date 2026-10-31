"""Tarea 0.4 — motor y sesiones de SQLAlchemy (sin conectarse a la BD: el motor es perezoso)."""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import QueuePool

from app.core.config import get_settings
from app.infra.db import get_db, get_engine

DB_URL = "postgresql+psycopg://alas:alas@localhost:5433/alas_unit_sin_conectar"


@pytest.fixture(autouse=True)
def fixed_db_url(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    monkeypatch.setenv("APP_ENV", "development")
    monkeypatch.setenv("DATABASE_URL", DB_URL)
    get_settings.cache_clear()
    get_engine.cache_clear()
    yield
    get_engine.cache_clear()
    get_settings.cache_clear()


def test_get_engine_devuelve_un_engine() -> None:
    assert isinstance(get_engine(), Engine)


def test_get_engine_usa_la_url_de_la_configuracion() -> None:
    engine = get_engine()
    assert engine.url.render_as_string(hide_password=False) == DB_URL


def test_get_engine_usa_cache() -> None:
    assert get_engine() is get_engine()


def test_get_engine_configura_el_pool() -> None:
    pool = get_engine().pool

    assert isinstance(pool, QueuePool)
    assert pool.size() == 5
    assert pool._pre_ping is True
    assert pool._recycle == 300


def test_get_db_entrega_una_session_ligada_al_engine() -> None:
    generator = get_db()
    session = next(generator)

    assert isinstance(session, Session)
    assert session.get_bind() is get_engine()

    with pytest.raises(StopIteration):
        next(generator)


def test_get_db_entrega_sesiones_distintas_por_peticion() -> None:
    first_gen = get_db()
    second_gen = get_db()
    first = next(first_gen)
    second = next(second_gen)

    assert first is not second

    first_gen.close()
    second_gen.close()

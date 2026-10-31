"""Tarea 0.4 — `serializable_session()` (D21) contra PostgreSQL real."""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.infra.db import get_db, get_engine, serializable_session

SCRATCH_TABLE = "zz_prueba_serializable"


class BoomError(Exception):
    pass


@pytest.fixture
def scratch_table() -> Iterator[None]:
    """Tabla temporal real (no TEMP: debe verse desde otras conexiones). Se borra al terminar
    para que `alembic check` no la vea."""
    with get_engine().begin() as conn:
        conn.execute(text("CREATE TABLE zz_prueba_serializable (valor text NOT NULL)"))
    yield
    with get_engine().begin() as conn:
        conn.execute(text("DROP TABLE IF EXISTS zz_prueba_serializable"))


def _values() -> list[str]:
    with get_engine().connect() as conn:
        rows = conn.execute(text("SELECT valor FROM zz_prueba_serializable ORDER BY valor"))
        return [row[0] for row in rows]


def test_serializable_session_usa_aislamiento_serializable() -> None:
    with serializable_session() as session:
        assert isinstance(session, Session)
        level = session.execute(text("SHOW transaction_isolation")).scalar_one()

    assert level == "serializable"


def test_la_sesion_de_la_peticion_no_es_serializable() -> None:
    generator = get_db()
    session = next(generator)
    try:
        level = session.execute(text("SHOW transaction_isolation")).scalar_one()
    finally:
        generator.close()

    assert level == "read committed"


def test_serializable_session_es_independiente_de_la_sesion_de_la_peticion() -> None:
    generator = get_db()
    request_session = next(generator)
    try:
        request_session.execute(text("SELECT 1"))  # la sesión de la petición ya consultó (B61)
        with serializable_session() as session:
            assert session is not request_session
            level = session.execute(text("SHOW transaction_isolation")).scalar_one()
    finally:
        generator.close()

    assert level == "serializable"


@pytest.mark.usefixtures("scratch_table")
def test_serializable_session_hace_commit_al_salir_bien() -> None:
    with serializable_session() as session:
        session.execute(
            text("INSERT INTO zz_prueba_serializable (valor) VALUES (:v)"), {"v": "ñandú"}
        )

    assert _values() == ["ñandú"]


@pytest.mark.usefixtures("scratch_table")
def test_serializable_session_hace_rollback_si_hay_excepcion() -> None:
    with pytest.raises(BoomError), serializable_session() as session:
        session.execute(text("INSERT INTO zz_prueba_serializable (valor) VALUES (:v)"), {"v": "x"})
        raise BoomError

    assert _values() == []


def test_serializable_session_entrega_sesiones_nuevas() -> None:
    with serializable_session() as first, serializable_session() as second:
        assert first is not second

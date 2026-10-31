"""Tarea 0.3 — `GET /api/health` verifica la base de datos (sin BD real: sesión falsa)."""

from __future__ import annotations

from collections.abc import Iterator

from fastapi.testclient import TestClient
from sqlalchemy.exc import OperationalError

from app.infra.db import get_db
from app.main import create_app


class FakeSession:
    def __init__(self, *, fail: bool) -> None:
        self.fail = fail
        self.statements: list[str] = []

    def execute(self, statement: object) -> object:
        self.statements.append(str(statement))
        if self.fail:
            raise OperationalError("SELECT 1", None, Exception("conexión rechazada"))
        return object()


def _client_with(session: FakeSession) -> TestClient:
    app = create_app()

    def fake_db() -> Iterator[FakeSession]:
        yield session

    app.dependency_overrides[get_db] = fake_db
    return TestClient(app, raise_server_exceptions=False)


def test_health_ok_cuando_la_bd_responde() -> None:
    session = FakeSession(fail=False)
    response = _client_with(session).get("/api/health")

    assert response.status_code == 200
    assert response.json() == {"ok": True, "db": True}


def test_health_ejecuta_select_1() -> None:
    session = FakeSession(fail=False)
    _client_with(session).get("/api/health")

    assert len(session.statements) == 1
    assert "SELECT 1" in session.statements[0].upper()


def test_health_503_cuando_la_bd_falla() -> None:
    session = FakeSession(fail=True)
    response = _client_with(session).get("/api/health")

    assert response.status_code == 503
    assert response.json() == {"ok": False, "db": False}


def test_health_no_expone_el_error_de_la_bd() -> None:
    response = _client_with(FakeSession(fail=True)).get("/api/health")
    assert "conexión rechazada" not in response.text
    assert "OperationalError" not in response.text


def test_health_lleva_cabeceras_de_seguridad() -> None:
    response = _client_with(FakeSession(fail=False)).get("/api/health")
    assert response.headers["x-content-type-options"] == "nosniff"
    assert "content-security-policy" in response.headers

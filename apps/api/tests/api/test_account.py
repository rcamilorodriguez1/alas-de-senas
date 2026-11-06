"""Datos personales (Ley 1581 de 2012, D-022): `GET /me/export` y `DELETE /me`."""

from __future__ import annotations

import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.rate_limit import reset_rate_limits
from app.infra.db import get_engine
from app.infra.models import Favorite, LessonSession, RefreshToken, User
from tests.api.helpers import PASSWORD, auth, complete_lesson, register_user

pytestmark = pytest.mark.usefixtures("seeded_content")


@pytest.fixture(autouse=True)
def _limits() -> None:
    reset_rate_limits()


_USER_COLUMN = {
    User: User.id,
    LessonSession: LessonSession.user_id,
    Favorite: Favorite.user_id,
    RefreshToken: RefreshToken.user_id,
}


def _count(model: type[User | LessonSession | Favorite | RefreshToken], user_id: str) -> int:
    with Session(get_engine()) as db:
        column = _USER_COLUMN[model]
        return db.execute(select(func.count()).where(column == uuid.UUID(user_id))).scalar_one()


def test_exportar_requiere_sesion(client: TestClient) -> None:
    assert client.get("/api/me/export").status_code == 401


def test_exportar_trae_perfil_progreso_y_favoritos(client: TestClient) -> None:
    token, user_id = register_user(client)
    complete_lesson(user_id, "M1-N1-L1", 100, True)
    assert client.post("/api/dictionary/favorites/gracias", headers=auth(token)).status_code == 204

    response = client.get("/api/me/export", headers=auth(token))

    assert response.status_code == 200
    body = response.json()
    assert body["profile"]["email"] == "ana@ejemplo.com"
    assert body["profile"]["dailyGoalMinutes"] == 10
    assert [s["lessonId"] for s in body["lessonSessions"]] == ["M1-N1-L1"]
    assert [f["sign"] for f in body["favorites"]] == ["gracias"]
    assert set(body) == {
        "exportedAt",
        "profile",
        "streak",
        "lessonSessions",
        "reviewSessions",
        "dailyActivity",
        "achievements",
        "favorites",
        "signReviews",
    }


def test_exportar_nunca_incluye_la_contrasena_ni_tokens(client: TestClient) -> None:
    token, _ = register_user(client)
    text = client.get("/api/me/export", headers=auth(token)).text
    assert "password" not in text.lower()
    assert "$2b$" not in text  # hash de bcrypt
    assert "token" not in text.lower()


def test_exportar_solo_trae_datos_propios(client: TestClient) -> None:
    token, _ = register_user(client, "ana@ejemplo.com")
    _, other_id = register_user(client, "beto@ejemplo.com")
    complete_lesson(other_id, "M1-N1-L1", 100, True)
    body = client.get("/api/me/export", headers=auth(token)).json()
    assert body["lessonSessions"] == []
    assert body["profile"]["email"] == "ana@ejemplo.com"


def test_eliminar_con_contrasena_incorrecta_no_borra(client: TestClient) -> None:
    token, user_id = register_user(client)
    response = client.request(
        "DELETE", "/api/me", json={"password": "otra-clave-1"}, headers=auth(token)
    )
    assert response.status_code == 403
    assert response.json()["code"] == "WRONG_PASSWORD"
    assert _count(User, user_id) == 1


def test_eliminar_borra_la_cuenta_y_todos_sus_datos(client: TestClient) -> None:
    token, user_id = register_user(client)
    complete_lesson(user_id, "M1-N1-L1", 100, True)
    client.post("/api/dictionary/favorites/gracias", headers=auth(token))
    assert _count(RefreshToken, user_id) >= 1

    response = client.request("DELETE", "/api/me", json={"password": PASSWORD}, headers=auth(token))

    assert response.status_code == 204
    assert 'rt=""' in response.headers.get("set-cookie", "") or "Max-Age=0" in response.headers.get(
        "set-cookie", ""
    )
    for model in (User, LessonSession, Favorite, RefreshToken):
        assert _count(model, user_id) == 0, model.__name__
    # El token de acceso ya no sirve: el usuario no existe.
    assert client.get("/api/me", headers=auth(token)).status_code == 401


def test_eliminar_requiere_sesion(client: TestClient) -> None:
    response = client.request("DELETE", "/api/me", json={"password": PASSWORD})
    assert response.status_code == 401


def test_exportar_incluye_la_autorizacion_de_datos(client: TestClient) -> None:
    """Ley 1581: la persona puede ver cuándo autorizó el tratamiento y qué versión aceptó."""
    from app.core.privacy import DATA_POLICY_VERSION

    token, _ = register_user(client)
    profile = client.get("/api/me/export", headers=auth(token)).json()["profile"]

    assert profile["dataPolicyVersion"] == DATA_POLICY_VERSION
    assert isinstance(profile["dataPolicyAcceptedAt"], str)
    assert profile["dataPolicyAcceptedAt"].startswith("20")

"""Tarea 10.5 — `POST /recognition/results` y logro «Ojo de colibrí» (§7.9, fila de §8.2).

Solo cuenta si `correct` y `confidence ≥ 0,7`, como máximo una vez por seña cada 10 s (con el
Clock); 60 por minuto por usuario; `signId` debe existir y `0 ≤ confidence ≤ 1`.
"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime, timedelta

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import update
from sqlalchemy.orm import Session

from app.core import rate_limit
from app.core.clock import get_clock
from app.core.rate_limit import reset_rate_limits
from app.infra.db import get_engine
from app.infra.models import User
from app.services.recognition_service import reset_recognition_memory
from tests.api.helpers import auth, register_user
from tests.fakes import FakeClock

pytestmark = pytest.mark.usefixtures("seeded_content")

URL = "/api/recognition/results"
T0 = datetime.now(UTC).replace(microsecond=0) - timedelta(minutes=1)


@pytest.fixture(autouse=True)
def _fresh() -> Iterator[None]:
    reset_rate_limits()
    reset_recognition_memory()
    yield
    reset_rate_limits()
    reset_recognition_memory()


@pytest.fixture
def clock(client: TestClient) -> Iterator[FakeClock]:
    fake = FakeClock(T0)
    app = client.app
    assert isinstance(app, FastAPI)
    app.dependency_overrides[get_clock] = lambda: fake
    yield fake
    app.dependency_overrides.pop(get_clock, None)


def send(
    client: TestClient,
    token: str,
    sign: str = "letra-a",
    correct: bool = True,
    confidence: float = 0.9,
) -> dict[str, object]:
    response = client.post(
        URL,
        json={"signId": sign, "correct": correct, "confidence": confidence},
        headers=auth(token),
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert isinstance(body, dict)
    return body


def test_sin_token_401(client: TestClient) -> None:
    response = client.post(URL, json={"signId": "letra-a", "correct": True, "confidence": 0.9})
    assert response.status_code == 401


def test_resultado_correcto_y_seguro_cuenta(client: TestClient, clock: FakeClock) -> None:
    token, _ = register_user(client)
    body = send(client, token)
    assert body == {"counted": True, "recognitionsCorrect": 1, "newAchievements": []}


@pytest.mark.parametrize(("correct", "confidence"), [(False, 0.99), (True, 0.69)])
def test_incorrecto_o_poco_seguro_no_cuenta(
    client: TestClient, clock: FakeClock, correct: bool, confidence: float
) -> None:
    token, _ = register_user(client)
    body = send(client, token, correct=correct, confidence=confidence)
    assert body["counted"] is False
    assert body["recognitionsCorrect"] == 0


def test_justo_0_7_cuenta(client: TestClient, clock: FakeClock) -> None:
    token, _ = register_user(client)
    assert send(client, token, confidence=0.7)["counted"] is True


def test_misma_sena_cuenta_una_vez_cada_10_segundos(client: TestClient, clock: FakeClock) -> None:
    token, _ = register_user(client)
    assert send(client, token)["counted"] is True
    clock.advance(seconds=9)
    assert send(client, token)["counted"] is False
    assert send(client, token, sign="letra-b")["counted"] is True  # otra seña sí
    clock.advance(seconds=1)
    body = send(client, token)
    assert body["counted"] is True
    assert body["recognitionsCorrect"] == 3


def test_veinte_reconocimientos_otorgan_ojo_de_colibri_una_vez(
    client: TestClient, clock: FakeClock
) -> None:
    token, user_id = register_user(client)
    with Session(get_engine()) as db:
        db.execute(update(User).where(User.id == user_id).values(recognitions_correct=19))
        db.commit()
    body = send(client, token)
    assert body["recognitionsCorrect"] == 20
    assert body["newAchievements"] == [
        {"id": "HUMMINGBIRD_EYE", "title": "Ojo de colibrí", "nectar": 30}
    ]
    clock.advance(seconds=11)
    assert send(client, token)["newAchievements"] == []


def test_sena_inexistente_404(client: TestClient, clock: FakeClock) -> None:
    token, _ = register_user(client)
    response = client.post(
        URL, json={"signId": "no-existe", "correct": True, "confidence": 0.9}, headers=auth(token)
    )
    assert response.status_code == 404
    assert response.json()["code"] == "SIGN_NOT_FOUND"


@pytest.mark.parametrize("confidence", [-0.1, 1.01])
def test_confianza_fuera_de_rango_422(
    client: TestClient, clock: FakeClock, confidence: float
) -> None:
    token, _ = register_user(client)
    response = client.post(
        URL,
        json={"signId": "letra-a", "correct": True, "confidence": confidence},
        headers=auth(token),
    )
    assert response.status_code == 422


def test_campos_extra_como_imagenes_se_rechazan(client: TestClient, clock: FakeClock) -> None:
    """R8.3: el endpoint solo acepta números; un campo de imagen se rechaza."""
    token, _ = register_user(client)
    response = client.post(
        URL,
        json={"signId": "letra-a", "correct": True, "confidence": 0.9, "image": "data:image/png"},
        headers=auth(token),
    )
    assert response.status_code == 422


def test_limite_de_60_por_minuto(
    client: TestClient, clock: FakeClock, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(rate_limit, "RECOGNITION_LIMIT", "2/minute")
    token, _ = register_user(client)
    send(client, token)
    send(client, token)
    response = client.post(
        URL, json={"signId": "letra-a", "correct": True, "confidence": 0.9}, headers=auth(token)
    )
    assert response.status_code == 429

"""Ayudas compartidas por las pruebas de API (registro, cabeceras y sesiones de lección)."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.infra.db import get_engine
from app.infra.models import LessonSession

PASSWORD = "Clave-Segura-1"
STARTED_AT = datetime(2026, 11, 3, 14, 0, tzinfo=UTC)
COMPLETED_AT = STARTED_AT + timedelta(minutes=5)


def register_user(client: TestClient, email: str = "ana@ejemplo.com") -> tuple[str, str]:
    """Registra un usuario y devuelve (access token, id del usuario)."""
    response = client.post(
        "/api/auth/register",
        json={
            "name": "Ana",
            "email": email,
            "password": PASSWORD,
            "dailyGoalMinutes": 10,
            "acceptedDataPolicy": True,
        },
    )
    assert response.status_code == 201, response.text
    body = response.json()
    token = body["accessToken"]
    user_id = body["user"]["id"]
    assert isinstance(token, str)
    assert isinstance(user_id, str)
    return token, user_id


def auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def complete_lesson(
    user_id: str,
    lesson_id: str,
    score: int,
    passed: bool,
    *,
    completed_at: datetime | None = COMPLETED_AT,
) -> None:
    """Inserta directamente en la BD una `LessonSession` cerrada (o abierta si
    `completed_at` es None) con el puntaje indicado, sobre 10 preguntas."""
    total = 10
    with Session(get_engine()) as session:
        session.add(
            LessonSession(
                id=uuid.uuid4(),
                user_id=uuid.UUID(user_id),
                lesson_id=lesson_id,
                started_at=STARTED_AT,
                completed_at=completed_at,
                hearts_lost=0,
                score=score,
                correct=score * total // 100,
                total=total,
                passed=passed,
            )
        )
        session.commit()

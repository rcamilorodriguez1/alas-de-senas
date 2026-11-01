"""Ayudas compartidas por las pruebas de API (registro, cabeceras y sesiones de lección)."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.domain.exercises.models import (
    SIDE_SPELLING,
    SIDE_VIDEO,
    SIDE_WORD,
    ConversationPayload,
    ExercisePayload,
    MeaningToVideoPayload,
    MemoryMatchPayload,
    ObservePayload,
    ProducePayload,
    SpellingPayload,
    Tokenize,
    VideoToMeaningPayload,
    parse_payload,
)
from app.infra.db import get_engine
from app.infra.models import Exercise, LessonSession
from app.services.option_tokens import make_tokenizer

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


# ---------- Respuestas calculadas por la prueba (B89: la API nunca revela la respuesta) ----------


def exercise_payload(exercise_id: str) -> ExercisePayload:
    """Payload real (solo servidor) del ejercicio, leído de la BD."""
    with Session(get_engine()) as session:
        raw = session.execute(
            select(Exercise.payload).where(Exercise.id == exercise_id)
        ).scalar_one()
    return parse_payload(raw)


def tokenizer(session_id: str, exercise_id: str) -> Tokenize:
    return make_tokenizer(get_settings().jwt_secret, session_id, exercise_id)


def correct_tokens(session_id: str, exercise_id: str) -> list[str]:
    """Tokens de la respuesta correcta (lo que `answers` devuelve en `correctTokens`)."""
    payload = exercise_payload(exercise_id)
    tok = tokenizer(session_id, exercise_id)
    if isinstance(payload, VideoToMeaningPayload):
        return [tok(SIDE_WORD, payload.correct_id)]
    if isinstance(payload, MeaningToVideoPayload):
        return [tok(SIDE_VIDEO, payload.correct_id)]
    if isinstance(payload, ConversationPayload):
        return [tok(SIDE_VIDEO, turn.correct_id) for turn in payload.turns]
    if isinstance(payload, SpellingPayload):
        return [tok(SIDE_SPELLING, payload.word)]
    return []


def correct_answer(session_id: str, exercise_id: str) -> dict[str, object]:
    """Cuerpo `answer` correcto para el ejercicio, calculado con el secreto del servidor."""
    payload = exercise_payload(exercise_id)
    tok = tokenizer(session_id, exercise_id)
    if isinstance(payload, ObservePayload):
        return {"watched": True}
    if isinstance(payload, VideoToMeaningPayload):
        return {"optionToken": tok(SIDE_WORD, payload.correct_id)}
    if isinstance(payload, MeaningToVideoPayload):
        return {"optionToken": tok(SIDE_VIDEO, payload.correct_id)}
    if isinstance(payload, MemoryMatchPayload):
        return {
            "attempts": [
                {"videoToken": tok(SIDE_VIDEO, s), "wordToken": tok(SIDE_WORD, s)}
                for s in payload.sign_ids
            ]
        }
    if isinstance(payload, ProducePayload):
        return {"method": "self", "ok": True}
    if isinstance(payload, ConversationPayload):
        return {"choices": [tok(SIDE_VIDEO, turn.correct_id) for turn in payload.turns]}
    return {"optionToken": tok(SIDE_SPELLING, payload.word)}


def wrong_answer(session_id: str, exercise_id: str) -> dict[str, object] | None:
    """Cuerpo `answer` incorrecto, o None si el tipo no admite error (OBSERVE)."""
    payload = exercise_payload(exercise_id)
    tok = tokenizer(session_id, exercise_id)
    if isinstance(payload, ObservePayload):
        return None
    if isinstance(payload, VideoToMeaningPayload):
        other = next(o for o in payload.option_ids if o != payload.correct_id)
        return {"optionToken": tok(SIDE_WORD, other)}
    if isinstance(payload, MeaningToVideoPayload):
        other = next(o for o in payload.option_ids if o != payload.correct_id)
        return {"optionToken": tok(SIDE_VIDEO, other)}
    if isinstance(payload, MemoryMatchPayload):
        return {"attempts": []}  # ninguna pareja emparejada
    if isinstance(payload, ProducePayload):
        return {"method": "self", "ok": False}
    if isinstance(payload, ConversationPayload):
        return {
            "choices": [
                tok(SIDE_VIDEO, next(o for o in turn.option_ids if o != turn.correct_id))
                for turn in payload.turns
            ]
        }
    other_word = next(w for w in payload.option_words if w != payload.word)
    return {"optionToken": tok(SIDE_SPELLING, other_word)}

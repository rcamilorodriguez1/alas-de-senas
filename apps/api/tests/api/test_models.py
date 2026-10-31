"""Tarea 2.1 — modelos de §5 contra PostgreSQL real: enums por valor y PK compuestas (B3, B5).

Cada prueba trabaja dentro de una transacción externa que se revierte al final: los datos de
contenido no se truncan entre pruebas (ver conftest), así que no deben quedar filas.
"""

from __future__ import annotations

import uuid
from collections.abc import Iterator
from datetime import UTC, datetime

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.domain.enums import ExerciseType, LessonType, NodeKind
from app.infra.db import get_engine
from app.infra.models import (
    Achievement,
    ActivityKind,
    Exercise,
    Lesson,
    LessonSession,
    Module,
    Node,
    Role,
    SessionAnswer,
    User,
    UserAchievement,
)

MOMENT = datetime(2026, 11, 3, 15, 0, tzinfo=UTC)


@pytest.fixture
def db() -> Iterator[Session]:
    with get_engine().connect() as conn:
        outer = conn.begin()
        session = Session(bind=conn, join_transaction_mode="create_savepoint")
        try:
            yield session
        finally:
            session.close()
            outer.rollback()


def _content(db: Session) -> Exercise:
    # Sin `relationship()`, el orden de inserción lo fija la prueba: un flush por nivel.
    db.add(Module(id="MZ", order=99, title="Módulo de prueba", description="Prueba."))
    db.flush()
    db.add(Node(id="MZ-N1", module_id="MZ", order=1, title="Nodo", kind=NodeKind.ALPHABET))
    db.flush()
    db.add(Lesson(id="MZ-N1-L1", node_id="MZ-N1", order=1, type=LessonType.LEARN, title="Aprende"))
    db.flush()
    exercise = Exercise(
        id="MZ-N1-L1-01",
        lesson_id="MZ-N1-L1",
        order=1,
        activity=ActivityKind.OBSERVE,
        type=ExerciseType.OBSERVE,
        scored=False,
        payload={"kind": "observe"},
    )
    db.add(exercise)
    db.flush()
    return exercise


def _user(db: Session) -> User:
    user = User(name="Ñandú Pérez", email="prueba-modelos@example.com", password_hash="x" * 60)
    db.add(user)
    db.flush()
    return user


def test_lesson_type_se_guarda_por_valor(db: Session) -> None:
    _content(db)

    raw = db.execute(text("SELECT type::text FROM lessons WHERE id = :id"), {"id": "MZ-N1-L1"})

    assert raw.scalar_one() == "LEARN"


def test_strenum_se_lee_como_strenum(db: Session) -> None:
    _content(db)
    db.expire_all()

    lesson = db.get(Lesson, "MZ-N1-L1")

    assert lesson is not None
    assert lesson.type is LessonType.LEARN


def test_todos_los_strenum_se_guardan_por_valor(db: Session) -> None:
    _content(db)
    user = _user(db)

    node_kind = db.execute(text("SELECT kind::text FROM nodes WHERE id = 'MZ-N1'")).scalar_one()
    activity, ex_type = db.execute(
        text("SELECT activity::text, type::text FROM exercises WHERE id = 'MZ-N1-L1-01'")
    ).one()
    role = db.execute(
        text("SELECT role::text FROM users WHERE id = :id"), {"id": user.id}
    ).scalar_one()

    assert node_kind == "ALPHABET"
    assert (activity, ex_type) == ("OBSERVE", "OBSERVE")
    assert role == Role.LEARNER.value == "LEARNER"


def test_valores_por_defecto_del_usuario(db: Session) -> None:
    user = _user(db)
    db.expire_all()

    loaded = db.get(User, user.id)

    assert loaded is not None
    assert loaded.name == "Ñandú Pérez"
    assert loaded.role is Role.LEARNER
    assert loaded.hearts == 5
    assert loaded.total_xp == 0
    assert loaded.hearts_updated_at is None
    assert loaded.created_at is not None


def test_session_answers_tiene_pk_compuesta_b3(db: Session) -> None:
    exercise = _content(db)
    user = _user(db)
    lesson_session = LessonSession(user_id=user.id, lesson_id="MZ-N1-L1", started_at=MOMENT)
    db.add(lesson_session)
    db.flush()
    db.add(
        SessionAnswer(
            session_id=lesson_session.id,
            exercise_id=exercise.id,
            answer={"token": "a"},
            correct=True,
            answered_at=MOMENT,
        )
    )
    db.flush()
    db.expunge_all()

    db.add(
        SessionAnswer(
            session_id=lesson_session.id,
            exercise_id=exercise.id,
            answer={"token": "b"},
            correct=False,
            answered_at=MOMENT,
        )
    )
    with pytest.raises(IntegrityError):
        db.flush()


def test_user_achievements_no_se_duplican_b5(db: Session) -> None:
    user = _user(db)
    db.add(
        Achievement(
            id="ZZ_PRUEBA",
            title="Prueba",
            description="Logro de prueba.",
            icon="star",
            nectar_reward=5,
            order=99,
        )
    )
    db.flush()
    db.add(UserAchievement(user_id=user.id, achievement_id="ZZ_PRUEBA", unlocked_at=MOMENT))
    db.flush()
    db.expunge_all()

    db.add(UserAchievement(user_id=user.id, achievement_id="ZZ_PRUEBA", unlocked_at=MOMENT))
    with pytest.raises(IntegrityError):
        db.flush()


def test_started_at_no_tiene_valor_por_defecto_del_servidor_d22(db: Session) -> None:
    _content(db)
    user = _user(db)
    db.add(LessonSession(id=uuid.uuid4(), user_id=user.id, lesson_id="MZ-N1-L1"))

    with pytest.raises(IntegrityError):
        db.flush()

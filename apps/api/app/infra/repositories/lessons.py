"""Consultas de lecciones, ejercicios, señas y respuestas para las sesiones (§8.3)."""

from __future__ import annotations

import hashlib
import json
import uuid
from collections.abc import Collection, Sequence
from datetime import datetime
from typing import Literal

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.domain.exercises.models import CatalogSign, SignCatalog, VideoRef
from app.infra.models import (
    Exercise,
    Lesson,
    LessonSession,
    Module,
    Node,
    SessionAnswer,
    Sign,
    User,
)


def get_lesson(session: Session, lesson_id: str) -> tuple[Lesson, Node, Module] | None:
    row = session.execute(
        select(Lesson, Node, Module)
        .join(Node, Lesson.node_id == Node.id)
        .join(Module, Node.module_id == Module.id)
        .where(Lesson.id == lesson_id)
    ).first()
    return (row[0], row[1], row[2]) if row else None


def lesson_exercises(session: Session, lesson_id: str) -> list[Exercise]:
    statement = select(Exercise).where(Exercise.lesson_id == lesson_id).order_by(Exercise.order)
    return list(session.execute(statement).scalars().all())


def exercises_fingerprint(exercises: Sequence[Exercise]) -> str:
    """SHA-256 de los ejercicios (id + payload): cambia si el contenido se recargó distinto."""
    data = [[e.id, e.payload] for e in exercises]
    return hashlib.sha256(json.dumps(data, sort_keys=True).encode("utf-8")).hexdigest()


def sign_catalog(session: Session, sign_ids: Collection[str]) -> SignCatalog:
    if not sign_ids:
        return {}
    rows = session.execute(select(Sign).where(Sign.id.in_(sign_ids)).order_by(Sign.id)).scalars()
    return {
        sign.id: CatalogSign(
            id=sign.id,
            word=sign.word,
            how_to=sign.how_to,
            usage_example=sign.usage_example,
            video=video_ref(sign),
        )
        for sign in rows
    }


def video_ref(sign: Sign) -> VideoRef:
    return VideoRef(
        src=sign.video_path,
        poster=sign.poster_path,
        placeholder=sign.is_placeholder,
        source=_media_source(sign.media_source),
    )


def _media_source(value: str) -> Literal["video", "images", "placeholder"]:
    if value == "images":
        return "images"
    if value == "placeholder":
        return "placeholder"
    return "video"


def lock_user(session: Session, user_id: uuid.UUID) -> User | None:
    """Bloquea y RELEE al usuario: sin populate_existing, SQLAlchemy devolvería el objeto ya
    cargado en la sesión con vidas viejas y dos errores simultáneos descontarían una sola."""
    statement = (
        select(User)
        .where(User.id == user_id)
        .with_for_update(key_share=True)
        .execution_options(populate_existing=True)
    )
    return session.execute(statement).scalar_one_or_none()


def get_user_session(
    session: Session, session_id: uuid.UUID, user_id: uuid.UUID, *, for_update: bool = False
) -> LessonSession | None:
    statement = select(LessonSession).where(
        LessonSession.id == session_id, LessonSession.user_id == user_id
    )
    if for_update:
        # FOR NO KEY UPDATE: no choca con el KEY SHARE que toma la FK de session_answers.
        statement = statement.with_for_update(key_share=True).execution_options(
            populate_existing=True
        )
    return session.execute(statement).scalar_one_or_none()


def insert_answer(
    session: Session,
    session_id: uuid.UUID,
    exercise_id: str,
    answer: dict[str, object],
    correct: bool,
    answered_at: datetime,
) -> bool:
    """Primer intento (B3): ON CONFLICT DO NOTHING RETURNING. True solo si se insertó."""
    statement = (
        insert(SessionAnswer)
        .values(
            session_id=session_id,
            exercise_id=exercise_id,
            answer=answer,
            correct=correct,
            answered_at=answered_at,
        )
        .on_conflict_do_nothing(index_elements=["session_id", "exercise_id"])
        .returning(SessionAnswer.exercise_id)
    )
    return session.execute(statement).first() is not None


def get_answer(session: Session, session_id: uuid.UUID, exercise_id: str) -> SessionAnswer | None:
    return session.get(SessionAnswer, (session_id, exercise_id))


def session_answers(session: Session, session_id: uuid.UUID) -> list[SessionAnswer]:
    statement = (
        select(SessionAnswer)
        .where(SessionAnswer.session_id == session_id)
        .order_by(SessionAnswer.exercise_id)
    )
    return list(session.execute(statement).scalars().all())


def has_passed_before(
    session: Session, user_id: uuid.UUID, lesson_id: str, exclude: uuid.UUID
) -> bool:
    statement = (
        select(LessonSession.id)
        .where(
            LessonSession.user_id == user_id,
            LessonSession.lesson_id == lesson_id,
            LessonSession.passed.is_(True),
            LessonSession.id != exclude,
        )
        .limit(1)
    )
    return session.execute(statement).first() is not None

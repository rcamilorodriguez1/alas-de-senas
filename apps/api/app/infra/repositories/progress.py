"""Consultas del seguimiento del progreso (§8.2): historial, señas aprendidas y precisión."""

from __future__ import annotations

import uuid
from collections.abc import Collection, Mapping
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import distinct, func, select
from sqlalchemy.orm import Session

from app.infra.models import Exercise, Lesson, LessonSession, Node, SessionAnswer, Sign


@dataclass(frozen=True, slots=True)
class HistoryRow:
    session_id: uuid.UUID
    lesson_id: str
    lesson_title: str
    node_title: str
    completed_at: datetime
    score: int
    passed: bool
    xp_earned: int


@dataclass(frozen=True, slots=True)
class LessonTotals:
    """Sumas por lección para promediar por nodo y módulo sin perder precisión."""

    score_sum: int = 0
    sessions: int = 0
    correct: int = 0
    answered: int = 0


def history(
    session: Session, user_id: uuid.UUID, offset: int, limit: int
) -> tuple[list[HistoryRow], int]:
    completed = (LessonSession.user_id == user_id, LessonSession.completed_at.is_not(None))
    total = session.execute(select(func.count()).where(*completed)).scalar_one()
    statement = (
        select(LessonSession, Lesson.title, Node.title)
        .join(Lesson, LessonSession.lesson_id == Lesson.id)
        .join(Node, Lesson.node_id == Node.id)
        .where(*completed)
        .order_by(LessonSession.completed_at.desc(), LessonSession.id.desc())
        .offset(offset)
        .limit(limit)
    )
    rows = [
        HistoryRow(
            session_id=record.id,
            lesson_id=record.lesson_id,
            lesson_title=lesson_title,
            node_title=node_title,
            completed_at=record.completed_at or record.started_at,
            score=record.score or 0,
            passed=bool(record.passed),
            xp_earned=record.xp_earned or 0,
        )
        for record, lesson_title, node_title in session.execute(statement).tuples()
    ]
    return rows, total


def signs_learned(session: Session, passed_lessons: Collection[str]) -> int:
    if not passed_lessons:
        return 0
    statement = select(func.count(distinct(Sign.id))).where(
        Sign.introduced_in_lesson_id.in_(list(passed_lessons))
    )
    return session.execute(statement).scalar_one()


def lesson_totals(session: Session, user_id: uuid.UUID) -> Mapping[str, LessonTotals]:
    """Por lección: suma y número de puntajes completados; aciertos y respuestas con puntaje."""
    scores = (
        select(LessonSession.lesson_id, func.sum(LessonSession.score), func.count())
        .where(LessonSession.user_id == user_id, LessonSession.completed_at.is_not(None))
        .group_by(LessonSession.lesson_id)
        .order_by(LessonSession.lesson_id)
    )
    answers = (
        select(
            LessonSession.lesson_id,
            func.count().filter(SessionAnswer.correct.is_(True)),
            func.count(),
        )
        .select_from(SessionAnswer)
        .join(LessonSession, SessionAnswer.session_id == LessonSession.id)
        .join(Exercise, SessionAnswer.exercise_id == Exercise.id)
        .where(
            LessonSession.user_id == user_id,
            LessonSession.completed_at.is_not(None),  # coherente con el promedio
            Exercise.scored.is_(True),
        )
        .group_by(LessonSession.lesson_id)
        .order_by(LessonSession.lesson_id)
    )
    totals: dict[str, LessonTotals] = {}
    for lesson_id, score_sum, count in session.execute(scores).tuples():
        totals[lesson_id] = LessonTotals(score_sum=int(score_sum or 0), sessions=count)
    for lesson_id, correct, answered in session.execute(answers).tuples():
        base = totals.get(lesson_id, LessonTotals())
        totals[lesson_id] = LessonTotals(base.score_sum, base.sessions, correct, answered)
    return totals

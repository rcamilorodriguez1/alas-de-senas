"""Consultas de racha, actividad diaria, repasos y logros (§7.5, §7.7, §7.9)."""

from __future__ import annotations

import uuid
from collections.abc import Iterable
from datetime import datetime

from sqlalchemy import distinct, func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.domain.enums import LessonType
from app.infra.models import (
    Achievement,
    DailyActivity,
    Exercise,
    Lesson,
    LessonSession,
    Module,
    Node,
    SessionAnswer,
    SignReview,
    Streak,
    UserAchievement,
)


def lock_streak(session: Session, user_id: uuid.UUID) -> Streak:
    """Fila de racha bloqueada (la crea si no existe)."""
    session.execute(
        insert(Streak).values(user_id=user_id).on_conflict_do_nothing(index_elements=["user_id"])
    )
    statement = (
        select(Streak)
        .where(Streak.user_id == user_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    return session.execute(statement).scalar_one()


def get_streak(session: Session, user_id: uuid.UUID) -> Streak | None:
    return session.get(Streak, user_id)


def add_daily_activity(
    session: Session,
    user_id: uuid.UUID,
    day: str,
    *,
    seconds: int = 0,
    xp: int = 0,
    lessons: int = 0,
    reviews: int = 0,
) -> None:
    """Suma a la actividad del día con un upsert atómico."""
    statement = insert(DailyActivity).values(
        user_id=user_id, day=day, seconds=seconds, xp=xp, lessons=lessons, reviews=reviews
    )
    excluded = statement.excluded
    session.execute(
        statement.on_conflict_do_update(
            index_elements=["user_id", "day"],
            set_={
                "seconds": DailyActivity.seconds + excluded.seconds,
                "xp": DailyActivity.xp + excluded.xp,
                "lessons": DailyActivity.lessons + excluded.lessons,
                "reviews": DailyActivity.reviews + excluded.reviews,
            },
        )
    )


def get_daily_activity(session: Session, user_id: uuid.UUID, day: str) -> DailyActivity | None:
    return session.get(DailyActivity, (user_id, day))


def sign_reviews(
    session: Session, user_id: uuid.UUID, sign_ids: Iterable[str]
) -> dict[str, SignReview]:
    ids = list(sign_ids)
    if not ids:
        return {}
    statement = (
        select(SignReview)
        .where(SignReview.user_id == user_id, SignReview.sign_id.in_(ids))
        .order_by(SignReview.sign_id)
    )
    return {row.sign_id: row for row in session.execute(statement).scalars()}


def upsert_sign_review(
    session: Session,
    user_id: uuid.UUID,
    sign_id: str,
    strength: int,
    next_review_day: str,
    seen_at: datetime,
) -> None:
    statement = insert(SignReview).values(
        user_id=user_id,
        sign_id=sign_id,
        strength=strength,
        next_review_day=next_review_day,
        last_seen_at=seen_at,
    )
    session.execute(
        statement.on_conflict_do_update(
            index_elements=["user_id", "sign_id"],
            set_={
                "strength": statement.excluded.strength,
                "next_review_day": statement.excluded.next_review_day,
                "last_seen_at": statement.excluded.last_seen_at,
            },
        )
    )


# ---------- Estadísticas para los logros ---------------------------------------------------


def lessons_passed(session: Session, user_id: uuid.UUID) -> int:
    statement = select(func.count()).where(
        LessonSession.user_id == user_id, LessonSession.passed.is_(True)
    )
    return session.execute(statement).scalar_one()


def challenges(session: Session, user_id: uuid.UUID) -> tuple[int, int]:
    """(retos aprobados, retos con 100 %)."""
    statement = (
        select(
            func.count(),
            func.count().filter(LessonSession.score == 100),
        )
        .select_from(LessonSession)
        .join(Lesson, LessonSession.lesson_id == Lesson.id)
        .where(
            LessonSession.user_id == user_id,
            LessonSession.passed.is_(True),
            Lesson.type == LessonType.CHALLENGE,
        )
    )
    passed, golden = session.execute(statement).one()
    return passed, golden


def first_module_completed(session: Session, user_id: uuid.UUID) -> bool:
    """Todas las lecciones del primer módulo aprobadas al menos una vez."""
    first = select(Module.id).order_by(Module.order).limit(1).scalar_subquery()
    total = (
        select(func.count(Lesson.id))
        .join(Node, Lesson.node_id == Node.id)
        .where(Node.module_id == first)
    )
    passed = (
        select(func.count(distinct(LessonSession.lesson_id)))
        .join(Lesson, LessonSession.lesson_id == Lesson.id)
        .join(Node, Lesson.node_id == Node.id)
        .where(
            Node.module_id == first,
            LessonSession.user_id == user_id,
            LessonSession.passed.is_(True),
        )
    )
    lessons_total = session.execute(total).scalar_one()
    return lessons_total > 0 and session.execute(passed).scalar_one() == lessons_total


def distinct_signs_correct(session: Session, user_id: uuid.UUID) -> int:
    statement = (
        select(func.count(distinct(Exercise.sign_id)))
        .select_from(SessionAnswer)
        .join(LessonSession, SessionAnswer.session_id == LessonSession.id)
        .join(Exercise, SessionAnswer.exercise_id == Exercise.id)
        .where(
            LessonSession.user_id == user_id,
            SessionAnswer.correct.is_(True),
            Exercise.scored.is_(True),
            Exercise.sign_id.is_not(None),
        )
    )
    return session.execute(statement).scalar_one()


# ---------- Logros --------------------------------------------------------------------------


def unlocked_ids(session: Session, user_id: uuid.UUID) -> set[str]:
    statement = select(UserAchievement.achievement_id).where(UserAchievement.user_id == user_id)
    return set(session.execute(statement).scalars())


def insert_achievements(
    session: Session, user_id: uuid.UUID, achievement_ids: Iterable[str], unlocked_at: datetime
) -> list[str]:
    """INSERT … ON CONFLICT DO NOTHING RETURNING: solo los ids realmente insertados (B5).

    Solo los logros del catálogo sembrado: sin el catálogo (BD sin contenido) no se otorga nada
    en lugar de romper la FK y, con ella, el registro o el `complete`.
    """
    wanted = list(achievement_ids)
    if not wanted:
        return []
    known = set(
        session.execute(
            select(Achievement.id).where(Achievement.id.in_(wanted)).order_by(Achievement.id)
        ).scalars()
    )
    rows = [
        {"user_id": user_id, "achievement_id": achievement_id, "unlocked_at": unlocked_at}
        for achievement_id in wanted
        if achievement_id in known
    ]
    if not rows:
        return []
    statement = (
        insert(UserAchievement)
        .values(rows)
        .on_conflict_do_nothing(index_elements=["user_id", "achievement_id"])
        .returning(UserAchievement.achievement_id)
    )
    return list(session.execute(statement).scalars())


def achievements_with_unlock(
    session: Session, user_id: uuid.UUID
) -> list[tuple[Achievement, datetime | None]]:
    statement = (
        select(Achievement, UserAchievement.unlocked_at)
        .outerjoin(
            UserAchievement,
            (UserAchievement.achievement_id == Achievement.id)
            & (UserAchievement.user_id == user_id),
        )
        .order_by(Achievement.order)
    )
    return [(row[0], row[1]) for row in session.execute(statement)]

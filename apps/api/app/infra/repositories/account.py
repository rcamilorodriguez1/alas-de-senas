"""Consultas de la exportación de datos de una cuenta (Ley 1581 de 2012, D-022)."""

from __future__ import annotations

import uuid

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.infra.models import (
    DailyActivity,
    Favorite,
    LessonSession,
    ReviewSession,
    SignReview,
    Streak,
    User,
    UserAchievement,
)


def lesson_sessions(session: Session, user_id: uuid.UUID) -> list[LessonSession]:
    statement = (
        select(LessonSession)
        .where(LessonSession.user_id == user_id)
        .order_by(LessonSession.started_at, LessonSession.id)
    )
    return list(session.execute(statement).scalars())


def review_sessions(session: Session, user_id: uuid.UUID) -> list[ReviewSession]:
    statement = (
        select(ReviewSession)
        .where(ReviewSession.user_id == user_id)
        .order_by(ReviewSession.started_at, ReviewSession.id)
    )
    return list(session.execute(statement).scalars())


def daily_activity(session: Session, user_id: uuid.UUID) -> list[DailyActivity]:
    statement = (
        select(DailyActivity).where(DailyActivity.user_id == user_id).order_by(DailyActivity.day)
    )
    return list(session.execute(statement).scalars())


def achievements(session: Session, user_id: uuid.UUID) -> list[UserAchievement]:
    statement = (
        select(UserAchievement)
        .where(UserAchievement.user_id == user_id)
        .order_by(UserAchievement.unlocked_at, UserAchievement.achievement_id)
    )
    return list(session.execute(statement).scalars())


def favorites(session: Session, user_id: uuid.UUID) -> list[Favorite]:
    statement = (
        select(Favorite)
        .where(Favorite.user_id == user_id)
        .order_by(Favorite.created_at, Favorite.sign_id)
    )
    return list(session.execute(statement).scalars())


def sign_reviews(session: Session, user_id: uuid.UUID) -> list[SignReview]:
    statement = select(SignReview).where(SignReview.user_id == user_id).order_by(SignReview.sign_id)
    return list(session.execute(statement).scalars())


def streak(session: Session, user_id: uuid.UUID) -> Streak | None:
    return session.get(Streak, user_id)


def delete_user(session: Session, user_id: uuid.UUID) -> None:
    """Borra al usuario; todas sus tablas tienen ON DELETE CASCADE (sesiones, tokens, logros…)."""
    session.execute(delete(User).where(User.id == user_id))

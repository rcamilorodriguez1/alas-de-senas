"""Derechos sobre los datos personales (Ley 1581 de 2012, D-022): descargarlos y suprimirlos."""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.core.security import verify_password
from app.domain.dates import Clock
from app.infra.models import User
from app.infra.repositories import account as repo
from app.schemas.account import (
    AccountExportOut,
    AchievementExportOut,
    DailyActivityExportOut,
    FavoriteExportOut,
    LessonSessionExportOut,
    ProfileExportOut,
    ReviewSessionExportOut,
    SignReviewExportOut,
    StreakExportOut,
)


class AccountService:
    def __init__(self, session: Session, clock: Clock) -> None:
        self.session = session
        self.clock = clock

    def export_data(self, user: User) -> AccountExportOut:
        """Todo lo que la app guarda del usuario (sin la contraseña ni los tokens)."""
        streak = repo.streak(self.session, user.id)
        return AccountExportOut(
            exported_at=self.clock.now(),
            profile=ProfileExportOut(
                name=user.name,
                email=user.email,
                role=user.role.value,
                daily_goal_minutes=user.daily_goal_minutes,
                dominant_hand=user.dominant_hand,
                created_at=user.created_at,
                total_xp=user.total_xp,
                nectar=user.nectar,
                hearts=user.hearts,
                recognitions_correct=user.recognitions_correct,
                has_avatar=user.avatar_updated_at is not None,
            ),
            streak=StreakExportOut(
                current=streak.current,
                longest=streak.longest,
                freezes_available=streak.freezes_available,
                last_active_day=streak.last_active_day,
            )
            if streak is not None
            else None,
            lesson_sessions=[
                LessonSessionExportOut(
                    lesson_id=s.lesson_id,
                    started_at=s.started_at,
                    completed_at=s.completed_at,
                    score=s.score,
                    passed=s.passed,
                    xp_earned=s.xp_earned,
                    nectar_earned=s.nectar_earned,
                )
                for s in repo.lesson_sessions(self.session, user.id)
            ],
            review_sessions=[
                ReviewSessionExportOut(
                    started_at=s.started_at,
                    completed_at=s.completed_at,
                    correct=s.correct,
                    total=s.total,
                )
                for s in repo.review_sessions(self.session, user.id)
            ],
            daily_activity=[
                DailyActivityExportOut(
                    day=a.day, seconds=a.seconds, xp=a.xp, lessons=a.lessons, reviews=a.reviews
                )
                for a in repo.daily_activity(self.session, user.id)
            ],
            achievements=[
                AchievementExportOut(id=a.achievement_id, unlocked_at=a.unlocked_at)
                for a in repo.achievements(self.session, user.id)
            ],
            favorites=[
                FavoriteExportOut(sign=f.sign_id, created_at=f.created_at)
                for f in repo.favorites(self.session, user.id)
            ],
            sign_reviews=[
                SignReviewExportOut(
                    sign=r.sign_id, strength=r.strength, next_review_day=r.next_review_day
                )
                for r in repo.sign_reviews(self.session, user.id)
            ],
        )

    def delete_account(self, user: User, password: str) -> None:
        """Supresión: pide la contraseña y borra al usuario con todos sus datos (en cascada)."""
        if not verify_password(password, user.password_hash):
            raise AppError(403, "WRONG_PASSWORD", "La contraseña no es correcta.")
        repo.delete_user(self.session, user.id)

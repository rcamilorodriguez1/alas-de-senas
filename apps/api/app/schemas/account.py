"""Exportación y eliminación de la cuenta (Ley 1581 de 2012: acceso y supresión, D-022)."""

from __future__ import annotations

from datetime import datetime

from pydantic import Field

from app.schemas.common import ApiModel


class ProfileExportOut(ApiModel):
    name: str
    email: str
    role: str
    daily_goal_minutes: int
    dominant_hand: str
    created_at: datetime
    total_xp: int
    nectar: int
    hearts: int
    recognitions_correct: int
    has_avatar: bool  # la foto misma no se exporta en el JSON (D-023)


class StreakExportOut(ApiModel):
    current: int
    longest: int
    freezes_available: int
    last_active_day: str | None


class LessonSessionExportOut(ApiModel):
    lesson_id: str
    started_at: datetime
    completed_at: datetime | None
    score: int | None
    passed: bool | None
    xp_earned: int | None
    nectar_earned: int | None


class ReviewSessionExportOut(ApiModel):
    started_at: datetime
    completed_at: datetime | None
    correct: int | None
    total: int | None


class DailyActivityExportOut(ApiModel):
    day: str
    seconds: int
    xp: int
    lessons: int
    reviews: int


class AchievementExportOut(ApiModel):
    id: str
    unlocked_at: datetime


class FavoriteExportOut(ApiModel):
    sign: str
    created_at: datetime


class SignReviewExportOut(ApiModel):
    sign: str
    strength: int
    next_review_day: str


class AccountExportOut(ApiModel):
    exported_at: datetime
    profile: ProfileExportOut
    streak: StreakExportOut | None
    lesson_sessions: list[LessonSessionExportOut]
    review_sessions: list[ReviewSessionExportOut]
    daily_activity: list[DailyActivityExportOut]
    achievements: list[AchievementExportOut]
    favorites: list[FavoriteExportOut]
    sign_reviews: list[SignReviewExportOut]


class DeleteAccountIn(ApiModel):
    password: str = Field(min_length=1, max_length=200)

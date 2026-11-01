"""Esquemas de gamificación (§8.2): estadísticas, logros, protector y recarga de vidas."""

from __future__ import annotations

from datetime import datetime

from app.schemas.common import ApiModel
from app.schemas.lessons import HeartsOut


class StreakStatsOut(ApiModel):
    current: int
    longest: int
    freezes_available: int
    at_risk: bool


class TodayOut(ApiModel):
    seconds: int
    goal_seconds: int
    xp: int


class StatsOut(ApiModel):
    total_xp: int
    nectar: int
    streak: StreakStatsOut
    today: TodayOut
    hearts: HeartsOut


class AchievementStatusOut(ApiModel):
    id: str
    title: str
    description: str
    icon: str
    nectar: int
    unlocked_at: datetime | None

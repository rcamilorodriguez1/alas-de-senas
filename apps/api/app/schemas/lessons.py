"""Esquemas de la sesión de lección (§8.2, §8.3)."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal

from pydantic import Field, JsonValue

from app.domain.enums import ExerciseType, LessonType
from app.domain.exercises.models import PublicExercise
from app.infra.models import ActivityKind
from app.schemas.common import ApiModel


class HeartsOut(ApiModel):
    enabled: bool
    current: int
    max: int
    next_heart_at: datetime | None


class LessonInfoOut(ApiModel):
    id: str
    order: int
    type: LessonType
    title: str
    node_id: str
    node_title: str
    node_order: int
    module_order: int
    estimated_xp: int


class PublicExerciseOut(ApiModel):
    id: str
    order: int
    activity: ActivityKind
    type: ExerciseType
    scored: bool
    # Índice de la seña (agrupación por seña de L1 a L3); null en los finales y en L4.
    group: int | None
    content: PublicExercise


class LessonStartOut(ApiModel):
    session_id: uuid.UUID
    lesson: LessonInfoOut
    exercises: list[PublicExerciseOut]
    hearts: HeartsOut


class AnswerIn(ApiModel):
    exercise_id: str = Field(max_length=32)
    answer: dict[str, JsonValue]


class AnswerOut(ApiModel):
    correct: bool
    correct_token: str | None
    correct_tokens: list[str]
    correct_word: str | None
    already_answered: bool
    hearts: HeartsOut


class StreakResultOut(ApiModel):
    current: int
    extended: bool


class AchievementOut(ApiModel):
    id: str
    title: str


class UnlockedOut(ApiModel):
    type: Literal["LESSON"]
    id: str


class LessonCompletionOut(ApiModel):
    score: int
    correct: int
    total: int
    passed: bool
    xp_earned: int
    nectar_earned: int
    streak: StreakResultOut
    new_achievements: list[AchievementOut]
    unlocked: list[UnlockedOut]
    mascot_mood: Literal["happy", "cheer", "sad", "thinking", "sleeping"]
    mascot_message: str

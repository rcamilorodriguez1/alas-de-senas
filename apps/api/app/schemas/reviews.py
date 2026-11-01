"""Esquemas de la sesión de repaso (§8.2, §8.5, D23)."""

from __future__ import annotations

import uuid

from app.domain.enums import ExerciseType
from app.domain.exercises.models import PublicExercise
from app.schemas.common import ApiModel
from app.schemas.lessons import AchievementOut, StreakResultOut


class QueueSignOut(ApiModel):
    word: str


class ReviewQueueOut(ApiModel):
    due: int
    signs: list[QueueSignOut]


class ReviewExerciseOut(ApiModel):
    id: str  # "R-01"
    type: ExerciseType
    content: PublicExercise


class ReviewStartOut(ApiModel):
    session_id: uuid.UUID
    exercises: list[ReviewExerciseOut]


class ReviewAnswerOut(ApiModel):
    correct: bool
    correct_token: str | None
    correct_tokens: list[str]
    correct_word: str | None
    already_answered: bool


class ReviewCompletionOut(ApiModel):
    correct: int
    total: int
    score: int
    streak: StreakResultOut
    hearts_gained: int
    new_achievements: list[AchievementOut]

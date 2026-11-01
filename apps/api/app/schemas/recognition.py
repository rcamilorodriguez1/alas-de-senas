"""Esquemas del reconocimiento por cámara (§8.2): solo números, nunca imágenes (R8.3)."""

from __future__ import annotations

from pydantic import Field

from app.schemas.common import ApiModel
from app.schemas.lessons import AchievementOut


class RecognitionIn(ApiModel):
    sign_id: str = Field(min_length=1, max_length=64)
    correct: bool
    confidence: float = Field(ge=0, le=1)


class RecognitionOut(ApiModel):
    counted: bool  # sumó para «Ojo de colibrí»
    recognitions_correct: int
    new_achievements: list[AchievementOut]

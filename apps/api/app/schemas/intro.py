"""Esquemas del módulo introductorio (§6.3, §8.2). Incluye la respuesta: el intro no da XP."""

from __future__ import annotations

from app.domain.exercises.models import VideoRef
from app.schemas.common import ApiModel


class IntroCardOut(ApiModel):
    slug: str
    word: str
    video: VideoRef


class IntroOptionOut(ApiModel):
    word: str
    correct: bool


class IntroQuestionOut(ApiModel):
    slug: str
    video: VideoRef
    options: list[IntroOptionOut]


class IntroOut(ApiModel):
    cards: list[IntroCardOut]
    quiz: list[IntroQuestionOut]

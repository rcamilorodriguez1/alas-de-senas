"""Esquemas del diccionario (§8.2, R7)."""

from __future__ import annotations

from app.domain.enums import ProgressStatus
from app.domain.exercises.models import VideoRef
from app.schemas.common import ApiModel


class CategoryRefOut(ApiModel):
    id: str
    name: str


class CategoryOut(ApiModel):
    id: str
    name: str
    count: int


class SignCardOut(ApiModel):
    slug: str
    word: str
    category: CategoryRefOut
    video: VideoRef


class SuggestionOut(ApiModel):
    slug: str
    word: str


class SignSearchOut(ApiModel):
    items: list[SignCardOut]
    page: int
    page_size: int
    total: int
    suggestions: list[SuggestionOut]


class RelatedLessonOut(ApiModel):
    id: str
    title: str
    status: ProgressStatus | None  # null sin sesión


class SignDetailOut(ApiModel):
    slug: str
    word: str
    meaning: str
    category: CategoryRefOut
    how_to: str | None
    usage_example: str
    video: VideoRef
    related_lesson: RelatedLessonOut | None
    is_favorite: bool

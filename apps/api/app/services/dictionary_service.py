"""Diccionario (§8.1, R7): búsqueda sin tildes ni mayúsculas, sugerencias, ficha y favoritos."""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.domain.dates import Clock
from app.domain.enums import ProgressStatus
from app.domain.text import levenshtein, normalize_text
from app.infra.models import Category, Sign, User
from app.infra.repositories import dictionary as repo
from app.infra.repositories.lessons import video_ref
from app.schemas.dictionary import (
    CategoryOut,
    CategoryRefOut,
    RelatedLessonOut,
    SignCardOut,
    SignDetailOut,
    SignSearchOut,
    SuggestionOut,
)
from app.services.curriculum_service import CurriculumService

PAGE_SIZE = 24
MAX_DISTANCE = 2
MAX_SUGGESTIONS = 5


def _not_found() -> AppError:
    return AppError(404, "SIGN_NOT_FOUND", "No encontramos esta seña.")


def _card(sign: Sign, category: Category) -> SignCardOut:
    return SignCardOut(
        slug=sign.id,
        word=sign.word,
        category=CategoryRefOut(id=category.id, name=category.name),
        video=video_ref(sign),
    )


class DictionaryService:
    def __init__(self, session: Session, clock: Clock) -> None:
        self.session = session
        self.clock = clock

    def search(self, q: str, category: str | None, page: int) -> SignSearchOut:
        term = normalize_text(q)
        rows, total = repo.search(self.session, term, category, (page - 1) * PAGE_SIZE, PAGE_SIZE)
        suggestions: list[SuggestionOut] = []
        if total == 0 and term:
            suggestions = self._suggest(term, category)
        return SignSearchOut(
            items=[_card(sign, cat) for sign, cat in rows],
            page=page,
            page_size=PAGE_SIZE,
            total=total,
            suggestions=suggestions,
        )

    def _suggest(self, term: str, category: str | None) -> list[SuggestionOut]:
        """Palabras a distancia de Levenshtein ≤ 2 (la más cercana primero)."""
        scored = [
            (distance, word, slug)
            for slug, word, normalized in repo.all_words(self.session, category)
            if (distance := levenshtein(term, normalized)) <= MAX_DISTANCE
        ]
        scored.sort()
        return [SuggestionOut(slug=slug, word=word) for _, word, slug in scored[:MAX_SUGGESTIONS]]

    def get_categories(self) -> list[CategoryOut]:
        return [
            CategoryOut(id=category.id, name=category.name, count=count)
            for category, count in repo.categories_with_signs(self.session)
        ]

    def get_sign(self, user: User | None, slug: str) -> SignDetailOut:
        found = repo.get_sign(self.session, slug)
        if found is None:
            raise _not_found()
        sign, category = found
        related = None
        if sign.introduced_in_lesson_id is not None:
            lesson = repo.published_lesson(self.session, sign.introduced_in_lesson_id)
            if lesson is not None:
                status: ProgressStatus | None = None
                if user is not None:
                    lessons = CurriculumService(self.session).progress_map(user.id).lessons
                    status = lessons.get(lesson.id, ProgressStatus.LOCKED)
                related = RelatedLessonOut(id=lesson.id, title=lesson.title, status=status)
        return SignDetailOut(
            slug=sign.id,
            word=sign.word,
            meaning=sign.meaning,
            category=CategoryRefOut(id=category.id, name=category.name),
            how_to=sign.how_to,
            usage_example=sign.usage_example,
            video=video_ref(sign),
            related_lesson=related,
            is_favorite=user is not None and repo.is_favorite(self.session, user.id, sign.id),
        )

    def list_favorites(self, user: User) -> list[SignCardOut]:
        return [_card(sign, category) for sign, category in repo.favorites(self.session, user.id)]

    def add_favorite(self, user: User, slug: str) -> None:
        if repo.get_sign(self.session, slug) is None:
            raise _not_found()
        repo.add_favorite(self.session, user.id, slug, self.clock.now())

    def remove_favorite(self, user: User, slug: str) -> None:
        repo.remove_favorite(self.session, user.id, slug)

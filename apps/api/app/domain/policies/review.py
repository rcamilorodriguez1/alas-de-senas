"""Repaso espaciado (§7.7)."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

from app.domain.dates import add_days

INTERVALS: tuple[int, ...] = (1, 2, 4, 7, 15, 30)
MAX_STRENGTH = 5
QUEUE_LIMIT = 15


@dataclass(frozen=True, slots=True)
class SignReview:
    sign_id: str
    strength: int
    next_review_day: str


class ReviewScheduler:
    def schedule(
        self, review: SignReview | None, sign_id: str, correct: bool, today: str
    ) -> SignReview:
        """`review=None`: primera vez (fuerza inicial 0)."""
        strength = review.strength if review is not None else 0
        strength = min(MAX_STRENGTH, strength + 1) if correct else 0
        return SignReview(sign_id, strength, add_days(today, INTERVALS[strength]))

    def due(
        self, reviews: Iterable[SignReview], today: str, limit: int = QUEUE_LIMIT
    ) -> list[SignReview]:
        """Vencidas (next_review_day <= today), menor fuerza primero; empates por día y sign_id."""
        # Días «YYYY-MM-DD»: el orden de texto coincide con el cronológico.
        pending = [r for r in reviews if r.next_review_day <= today]
        pending.sort(key=lambda r: (r.strength, r.next_review_day, r.sign_id))
        return pending[:limit]

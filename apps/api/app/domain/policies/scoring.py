"""Puntaje de una sesión (§7.2)."""

from __future__ import annotations

from dataclasses import dataclass

from app.domain.enums import LessonType

PASSING_SCORE = 60
CHALLENGE_PASSING_SCORE = 70


def round_half_up(a: int, b: int) -> int:
    """a / b redondeado hacia arriba en .5, solo con enteros (b > 0)."""
    return (2 * a + b) // (2 * b)


@dataclass(frozen=True, slots=True)
class SessionScore:
    correct: int
    total: int
    score: int
    passed: bool


def score_session(correct: int, total: int, lesson_type: LessonType) -> SessionScore:
    passing = CHALLENGE_PASSING_SCORE if lesson_type is LessonType.CHALLENGE else PASSING_SCORE
    score = 100 if total == 0 else round_half_up(correct * 100, total)
    passed = correct * 100 >= passing * total  # comparación entera, sin flotantes
    return SessionScore(correct, total, score, passed)

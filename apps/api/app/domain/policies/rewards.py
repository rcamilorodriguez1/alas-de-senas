"""XP y néctar al completar una lección (§7.3)."""

from __future__ import annotations

from dataclasses import dataclass

from app.domain.enums import LessonType
from app.domain.policies.scoring import SessionScore, round_half_up, score_session

BASE_XP = 10
CHALLENGE_BASE_XP = 20
PERFECT_BONUS = 5
PASS_NECTAR = 5
FIRST_CHALLENGE_NECTAR = 10


@dataclass(frozen=True, slots=True)
class Reward:
    xp: int
    nectar: int


class RewardPolicy:
    def calculate(
        self, lesson_type: LessonType, score: SessionScore, previously_passed: bool
    ) -> Reward:
        """`previously_passed`: el usuario ya había aprobado esta misma lección antes."""
        if not score.passed:
            return Reward(xp=0, nectar=0)
        is_challenge = lesson_type is LessonType.CHALLENGE
        xp = CHALLENGE_BASE_XP if is_challenge else BASE_XP
        xp += round_half_up(score.score * 5, 100)
        if score.score == 100:
            xp += PERFECT_BONUS
        if previously_passed:
            xp = -(-xp // 2)  # ceil(xp / 2) sin flotantes
        nectar = PASS_NECTAR
        if is_challenge and not previously_passed:
            nectar += FIRST_CHALLENGE_NECTAR
        return Reward(xp=xp, nectar=nectar)

    def max_xp(self, lesson_type: LessonType, previously_passed: bool) -> int:
        """XP de aprobar la lección con 100 % (la «XP estimada» que muestra la ruta)."""
        perfect = score_session(1, 1, lesson_type)
        return self.calculate(lesson_type, perfect, previously_passed).xp

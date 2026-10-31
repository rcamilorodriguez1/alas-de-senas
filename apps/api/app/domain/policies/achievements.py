"""Logros (§7.9)."""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Collection
from dataclasses import dataclass
from typing import ClassVar


@dataclass(frozen=True, slots=True)
class AchievementStats:
    intro_completed: bool = False
    lessons_passed: int = 0
    current_streak: int = 0
    challenges_passed: int = 0
    golden_challenges: int = 0
    module1_completed: bool = False
    distinct_signs_correct: int = 0
    camera_correct: int = 0


class AchievementRule(ABC):
    id: ClassVar[str]
    title: ClassVar[str]
    nectar_reward: ClassVar[int]

    @abstractmethod
    def is_satisfied(self, stats: AchievementStats) -> bool: ...


class FirstFlap(AchievementRule):
    id = "FIRST_FLAP"
    title = "Primer aleteo"
    nectar_reward = 10

    def is_satisfied(self, stats: AchievementStats) -> bool:
        return stats.intro_completed


class FirstLesson(AchievementRule):
    id = "FIRST_LESSON"
    title = "Primeras alas"
    nectar_reward = 10

    def is_satisfied(self, stats: AchievementStats) -> bool:
        return stats.lessons_passed >= 1


class Streak3(AchievementRule):
    id = "STREAK_3"
    title = "Aleteo constante"
    nectar_reward = 15

    def is_satisfied(self, stats: AchievementStats) -> bool:
        return stats.current_streak >= 3


class Streak7(AchievementRule):
    id = "STREAK_7"
    title = "Vuelo de una semana"
    nectar_reward = 30

    def is_satisfied(self, stats: AchievementStats) -> bool:
        return stats.current_streak >= 7


class NodeDone(AchievementRule):
    id = "NODE_DONE"
    title = "Nodo superado"
    nectar_reward = 15

    def is_satisfied(self, stats: AchievementStats) -> bool:
        return stats.challenges_passed >= 1


class GoldenNode(AchievementRule):
    id = "GOLDEN_NODE"
    title = "Nodo dorado"
    nectar_reward = 20

    def is_satisfied(self, stats: AchievementStats) -> bool:
        return stats.golden_challenges >= 1


class Module1(AchievementRule):
    id = "MODULE_1"
    title = "Fundamentos dominados"
    nectar_reward = 40

    def is_satisfied(self, stats: AchievementStats) -> bool:
        return stats.module1_completed


class Signs50(AchievementRule):
    id = "SIGNS_50"
    title = "Manos que hablan"
    nectar_reward = 40

    def is_satisfied(self, stats: AchievementStats) -> bool:
        return stats.distinct_signs_correct >= 50


class HummingbirdEye(AchievementRule):
    id = "HUMMINGBIRD_EYE"
    title = "Ojo de colibrí"
    nectar_reward = 30

    def is_satisfied(self, stats: AchievementStats) -> bool:
        return stats.camera_correct >= 20


ACHIEVEMENTS: tuple[AchievementRule, ...] = (
    FirstFlap(),
    FirstLesson(),
    Streak3(),
    Streak7(),
    NodeDone(),
    GoldenNode(),
    Module1(),
    Signs50(),
    HummingbirdEye(),
)


def evaluate_achievements(stats: AchievementStats, already_unlocked: Collection[str]) -> list[str]:
    """IDs recién cumplidos (no incluidos en `already_unlocked`), en el orden de ACHIEVEMENTS."""
    unlocked = set(already_unlocked)
    return [
        rule.id for rule in ACHIEVEMENTS if rule.id not in unlocked and rule.is_satisfied(stats)
    ]

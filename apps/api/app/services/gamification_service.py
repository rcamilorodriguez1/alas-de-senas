"""Racha, actividad diaria, repasos, logros, protector y vidas (§7.5, §7.7, §7.9, §7.10).

Siempre trabaja dentro de la transacción del llamador (§8.1): el `complete` de la lección la
llama en su sesión SERIALIZABLE y los endpoints de compra en la sesión de la petición.
"""

from __future__ import annotations

import uuid
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Literal

from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.errors import AppError, unauthorized
from app.domain.dates import Clock, to_local_day
from app.domain.policies.achievements import (
    ACHIEVEMENTS,
    AchievementStats,
    FirstFlap,
    evaluate_achievements,
)
from app.domain.policies.hearts import MAX_HEARTS, REFILL_COST, HeartsPolicy, HeartsState
from app.domain.policies.review import ReviewScheduler
from app.domain.policies.review import SignReview as ReviewState
from app.domain.policies.streak import FREEZE_COST, MAX_FREEZES, StreakPolicy
from app.domain.policies.streak import Streak as StreakState
from app.infra.models import Exercise, SessionAnswer, Streak, User
from app.infra.repositories import gamification as repo
from app.infra.repositories import lessons as lessons_repo
from app.schemas.gamification import AchievementStatusOut, StatsOut, StreakStatsOut, TodayOut
from app.schemas.lessons import AchievementOut, HeartsOut, StreakResultOut

NOT_ENOUGH_NECTAR = ("NOT_ENOUGH_NECTAR", "No tienes suficiente néctar")
_RULES = {rule.id: rule for rule in ACHIEVEMENTS}
FIRST_FLAP = FirstFlap()


@dataclass(frozen=True, slots=True)
class CompletionGamification:
    streak: StreakResultOut
    new_achievements: list[AchievementOut]


def hearts_out(user: User, clock: Clock, settings: Settings) -> HeartsOut:
    state = HeartsState(hearts=user.hearts, updated_at=user.hearts_updated_at)
    current, next_heart = HeartsPolicy().current(state, clock.now())
    return HeartsOut(
        enabled=settings.hearts_enabled, current=current, max=MAX_HEARTS, next_heart_at=next_heart
    )


class GamificationService:
    def __init__(self, session: Session, clock: Clock, settings: Settings) -> None:
        self.session = session
        self.clock = clock
        self.settings = settings
        self.streaks = StreakPolicy()
        self.reviews = ReviewScheduler()

    # ---- al completar una lección --------------------------------------------------------

    def apply_completion(
        self,
        user: User,
        exercises: Sequence[Exercise],
        answers: Mapping[str, SessionAnswer],
        *,
        seconds: int,
        xp: int,
    ) -> CompletionGamification:
        """Actividad del día, racha, repasos de las señas y logros. `user` ya está bloqueado."""
        day = to_local_day(self.clock.now())
        streak = self.register_activity(user.id, day, seconds=seconds, xp=xp, kind="lesson")
        self._schedule_reviews(user.id, exercises, answers, day)
        new = self.evaluate_achievements(user)
        return CompletionGamification(streak=streak, new_achievements=new)

    def register_activity(
        self,
        user_id: uuid.UUID,
        day: str,
        *,
        seconds: int,
        kind: Literal["lesson", "review"],
        xp: int = 0,
    ) -> StreakResultOut:
        """Único punto que actualiza la racha y la actividad diaria (lecciones y repasos)."""
        repo.add_daily_activity(
            self.session,
            user_id,
            day,
            seconds=seconds,
            xp=xp,
            lessons=1 if kind == "lesson" else 0,
            reviews=1 if kind == "review" else 0,
        )
        row = repo.lock_streak(self.session, user_id)
        before = _streak_state(row)
        after = self.streaks.apply_activity(before, day)
        row.current = after.current
        row.longest = after.longest
        row.freezes_available = after.freezes_available
        row.last_active_day = after.last_active_day
        self.session.flush()
        extended = before.last_active_day != day and after.last_active_day == day
        return StreakResultOut(current=after.current, extended=extended)

    def _schedule_reviews(
        self,
        user_id: uuid.UUID,
        exercises: Sequence[Exercise],
        answers: Mapping[str, SessionAnswer],
        day: str,
    ) -> None:
        """Una seña queda bien solo si todos sus ejercicios de la sesión fueron correctos; un
        error o «Necesito repasar» la programa para mañana (§7.7, R6.4)."""
        correct: dict[str, bool] = {}
        for exercise in exercises:
            if exercise.sign_id is None or exercise.id not in answers:
                continue
            ok = answers[exercise.id].correct
            correct[exercise.sign_id] = correct.get(exercise.sign_id, True) and ok
        stored = repo.sign_reviews(self.session, user_id, correct)
        now = self.clock.now()
        for sign_id in sorted(correct):
            row = stored.get(sign_id)
            previous = (
                ReviewState(sign_id, row.strength, row.next_review_day) if row is not None else None
            )
            review = self.reviews.schedule(previous, sign_id, correct[sign_id], day)
            repo.upsert_sign_review(
                self.session, user_id, sign_id, review.strength, review.next_review_day, now
            )

    def evaluate_achievements(self, user: User) -> list[AchievementOut]:
        """Inserta los logros recién cumplidos y suma su néctar solo por filas insertadas."""
        streak = repo.get_streak(self.session, user.id)
        challenges_passed, golden = repo.challenges(self.session, user.id)
        stats = AchievementStats(
            lessons_passed=repo.lessons_passed(self.session, user.id),
            current_streak=streak.current if streak is not None else 0,
            challenges_passed=challenges_passed,
            golden_challenges=golden,
            module1_completed=repo.first_module_completed(self.session, user.id),
            distinct_signs_correct=repo.distinct_signs_correct(self.session, user.id),
            camera_correct=user.recognitions_correct,
        )
        candidates = evaluate_achievements(stats, repo.unlocked_ids(self.session, user.id))
        inserted = set(
            repo.insert_achievements(self.session, user.id, candidates, self.clock.now())
        )
        new = [
            _RULES[achievement_id] for achievement_id in candidates if achievement_id in inserted
        ]
        user.nectar += sum(rule.nectar_reward for rule in new)
        self.session.flush()
        return [AchievementOut(id=r.id, title=r.title, nectar=r.nectar_reward) for r in new]

    def grant_intro(self, user: User) -> list[AchievementOut]:
        """Logro «Primer aleteo» al registrarse con el intro completo (R1.6), una sola vez."""
        inserted = repo.insert_achievements(
            self.session, user.id, [FIRST_FLAP.id], self.clock.now()
        )
        if not inserted:
            return []
        user.nectar += FIRST_FLAP.nectar_reward
        self.session.flush()
        return [
            AchievementOut(
                id=FIRST_FLAP.id, title=FIRST_FLAP.title, nectar=FIRST_FLAP.nectar_reward
            )
        ]

    # ---- consultas -----------------------------------------------------------------------

    def get_stats(self, user: User) -> StatsOut:
        today = to_local_day(self.clock.now())
        row = repo.get_streak(self.session, user.id)
        state = _streak_state(row)
        activity = repo.get_daily_activity(self.session, user.id, today)
        return StatsOut(
            total_xp=user.total_xp,
            nectar=user.nectar,
            streak=StreakStatsOut(
                current=self.streaks.display(state, today),
                longest=state.longest,
                freezes_available=state.freezes_available,
                at_risk=self.streaks.is_at_risk(state, today),
            ),
            today=TodayOut(
                seconds=activity.seconds if activity is not None else 0,
                goal_seconds=user.daily_goal_minutes * 60,
                xp=activity.xp if activity is not None else 0,
            ),
            hearts=hearts_out(user, self.clock, self.settings),
        )

    def list_achievements(self, user_id: uuid.UUID) -> list[AchievementStatusOut]:
        return [
            AchievementStatusOut(
                id=achievement.id,
                title=achievement.title,
                description=achievement.description,
                icon=achievement.icon,
                nectar=achievement.nectar_reward,
                unlocked_at=unlocked_at,
            )
            for achievement, unlocked_at in repo.achievements_with_unlock(self.session, user_id)
        ]

    # ---- compras con néctar --------------------------------------------------------------

    def buy_streak_freeze(self, user_id: uuid.UUID) -> StatsOut:
        user = self._lock_user(user_id)
        streak = repo.lock_streak(self.session, user_id)
        if streak.freezes_available >= MAX_FREEZES:
            raise AppError(409, "MAX_FREEZES", "Ya tienes 2 protectores guardados.")
        if user.nectar < FREEZE_COST:
            raise AppError(409, *NOT_ENOUGH_NECTAR)
        today = to_local_day(self.clock.now())
        if self.streaks.display(_streak_state(streak), today) == 0:
            # La racha ya se rompió: el protector no es retroactivo (D-013.8).
            streak.current = 0
            streak.last_active_day = None
        user.nectar -= FREEZE_COST
        streak.freezes_available += 1
        self.session.flush()
        return self.get_stats(user)

    def refill_hearts(self, user_id: uuid.UUID) -> StatsOut:
        user = self._lock_user(user_id)
        policy = HeartsPolicy()
        now = self.clock.now()
        current, _ = policy.current(HeartsState(user.hearts, user.hearts_updated_at), now)
        if not self.settings.hearts_enabled or current >= MAX_HEARTS:
            raise AppError(409, "HEARTS_FULL", "Ya tienes todas tus vidas.")
        if user.nectar < REFILL_COST:
            raise AppError(409, *NOT_ENOUGH_NECTAR)
        state = policy.refill(now)
        user.nectar -= REFILL_COST
        user.hearts = state.hearts
        user.hearts_updated_at = state.updated_at
        self.session.flush()
        return self.get_stats(user)

    def _lock_user(self, user_id: uuid.UUID) -> User:
        user = lessons_repo.lock_user(self.session, user_id)
        if user is None:
            raise unauthorized()
        return user


def _streak_state(row: Streak | None) -> StreakState:
    if row is None:
        return StreakState()
    return StreakState(
        current=row.current,
        longest=row.longest,
        freezes_available=row.freezes_available,
        last_active_day=row.last_active_day,
    )

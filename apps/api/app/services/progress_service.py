"""Resumen, historial y resultados por unidad (§8.1, R6.1 a R6.3). Solo lectura."""

from __future__ import annotations

import uuid
from collections.abc import Iterable, Mapping

from sqlalchemy.orm import Session

from app.domain.dates import Clock, to_local_day
from app.domain.policies.progress import module_progress_percent
from app.domain.policies.streak import Streak as StreakState
from app.domain.policies.streak import StreakPolicy
from app.infra.models import Lesson, Module, User
from app.infra.repositories import curriculum as curriculum_repo
from app.infra.repositories import gamification as gamification_repo
from app.infra.repositories import progress as repo
from app.infra.repositories.progress import LessonTotals
from app.schemas.progress import (
    HistoryItemOut,
    HistoryPageOut,
    ModuleProgressOut,
    ModuleUnitOut,
    NodeUnitOut,
    ProgressSummaryOut,
    UnitsOut,
)

PAGE_SIZE = 20


class ProgressService:
    def __init__(self, session: Session, clock: Clock) -> None:
        self.session = session
        self.clock = clock

    def get_summary(self, user: User) -> ProgressSummaryOut:
        modules = self._published()
        facts = curriculum_repo.lesson_facts(self.session, user.id)
        passed = {lesson_id for lesson_id, fact in facts.items() if fact.passed}
        all_lessons = [lesson.id for module in modules for lesson in _lessons(module)]
        row = gamification_repo.get_streak(self.session, user.id)
        state = (
            StreakState(row.current, row.longest, row.freezes_available, row.last_active_day)
            if row is not None
            else StreakState()
        )
        return ProgressSummaryOut(
            percent=module_progress_percent(all_lessons, passed),
            modules=[
                ModuleProgressOut(
                    id=module.id,
                    title=module.title,
                    order=module.order,
                    percent=module_progress_percent([lsn.id for lsn in _lessons(module)], passed),
                )
                for module in modules
            ],
            total_xp=user.total_xp,
            streak=StreakPolicy().display(state, to_local_day(self.clock.now())),
            signs_learned=repo.signs_learned(self.session, passed),
        )

    def get_history(self, user_id: uuid.UUID, page: int) -> HistoryPageOut:
        rows, total = repo.history(self.session, user_id, (page - 1) * PAGE_SIZE, PAGE_SIZE)
        return HistoryPageOut(
            items=[
                HistoryItemOut(
                    session_id=row.session_id,
                    lesson_id=row.lesson_id,
                    lesson_title=row.lesson_title,
                    node_title=row.node_title,
                    completed_at=row.completed_at,
                    score=row.score,
                    passed=row.passed,
                    xp_earned=row.xp_earned,
                )
                for row in rows
            ],
            page=page,
            page_size=PAGE_SIZE,
            total=total,
        )

    def get_units(self, user_id: uuid.UUID) -> UnitsOut:
        totals = repo.lesson_totals(self.session, user_id)
        modules: list[ModuleUnitOut] = []
        for module in self._published():
            nodes = [
                NodeUnitOut(
                    id=node.id,
                    title=node.title,
                    order=node.order,
                    **_averages(totals, [lesson.id for lesson in node.lessons]),
                )
                for node in module.nodes
            ]
            modules.append(
                ModuleUnitOut(
                    id=module.id,
                    title=module.title,
                    order=module.order,
                    nodes=nodes,
                    **_averages(totals, [lesson.id for lesson in _lessons(module)]),
                )
            )
        return UnitsOut(modules=modules)

    def _published(self) -> list[Module]:
        return [m for m in curriculum_repo.load_curriculum(self.session) if m.published]


def _lessons(module: Module) -> list[Lesson]:
    return [lesson for node in module.nodes for lesson in node.lessons]


def _averages(
    totals: Mapping[str, LessonTotals], lesson_ids: Iterable[str]
) -> dict[str, int | None]:
    """Puntaje promedio y precisión (%, división entera) de un grupo de lecciones."""
    score_sum = sessions = correct = answered = 0
    for lesson_id in lesson_ids:
        item = totals.get(lesson_id)
        if item is None:
            continue
        score_sum += item.score_sum
        sessions += item.sessions
        correct += item.correct
        answered += item.answered
    return {
        "average_score": score_sum // sessions if sessions else None,
        "accuracy": correct * 100 // answered if answered else None,
    }

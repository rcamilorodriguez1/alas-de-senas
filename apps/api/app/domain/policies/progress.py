"""Desbloqueo derivado: el estado se calcula, no se guarda (D3, §7.4)."""

from __future__ import annotations

from collections.abc import Collection, Mapping, Sequence
from dataclasses import dataclass

from app.domain.enums import LessonType, ProgressStatus
from app.domain.policies.scoring import round_half_up


@dataclass(frozen=True, slots=True)
class CurriculumLesson:
    id: str
    order: int  # 1..4
    type: LessonType


@dataclass(frozen=True, slots=True)
class CurriculumNode:
    id: str
    order: int
    lessons: tuple[CurriculumLesson, ...]


@dataclass(frozen=True, slots=True)
class CurriculumModule:
    id: str
    order: int
    published: bool
    nodes: tuple[CurriculumNode, ...]


@dataclass(frozen=True, slots=True)
class ProgressFacts:
    best_scores: Mapping[str, int]  # lesson_id → mejor puntaje
    passed: Collection[str]  # lesson_ids aprobadas


@dataclass(frozen=True, slots=True)
class ProgressMap:
    lessons: Mapping[str, ProgressStatus]
    nodes: Mapping[str, ProgressStatus]
    modules: Mapping[str, ProgressStatus]


def compute_progress(modules: Sequence[CurriculumModule], facts: ProgressFacts) -> ProgressMap:
    """Ordena por `order` (módulos → nodos → lecciones) sin depender del orden de entrada.

    Lecciones de módulos no publicados no aparecen en `lessons`; sus nodos y el módulo quedan
    COMING_SOON. Módulo publicado: LOCKED si su primer nodo está bloqueado; COMPLETED si todos
    sus nodos están COMPLETED o GOLDEN; si no, IN_PROGRESS.
    """
    passed = set(facts.passed)
    lessons: dict[str, ProgressStatus] = {}
    nodes: dict[str, ProgressStatus] = {}
    module_status: dict[str, ProgressStatus] = {}
    previous_passed = True  # la primera lección del orden global siempre está disponible

    for module in sorted(modules, key=lambda m: m.order):
        ordered_nodes = sorted(module.nodes, key=lambda n: n.order)
        if not module.published:
            module_status[module.id] = ProgressStatus.COMING_SOON
            for node in ordered_nodes:
                nodes[node.id] = ProgressStatus.COMING_SOON
            continue
        node_states: list[ProgressStatus] = []
        for node in ordered_nodes:
            ordered_lessons = sorted(node.lessons, key=lambda lesson: lesson.order)
            for lesson in ordered_lessons:
                lessons[lesson.id] = _lesson_status(lesson, passed, facts, previous_passed)
                previous_passed = lesson.id in passed
            state = _node_status(ordered_lessons, lessons)
            nodes[node.id] = state
            node_states.append(state)
        module_status[module.id] = _module_status(node_states)
    return ProgressMap(lessons=lessons, nodes=nodes, modules=module_status)


def _lesson_status(
    lesson: CurriculumLesson, passed: set[str], facts: ProgressFacts, previous_passed: bool
) -> ProgressStatus:
    if lesson.id in passed:
        golden = lesson.type is LessonType.CHALLENGE and facts.best_scores.get(lesson.id) == 100
        return ProgressStatus.GOLDEN if golden else ProgressStatus.COMPLETED
    return ProgressStatus.AVAILABLE if previous_passed else ProgressStatus.LOCKED


def _node_status(
    ordered_lessons: Sequence[CurriculumLesson], lessons: Mapping[str, ProgressStatus]
) -> ProgressStatus:
    if not ordered_lessons or lessons[ordered_lessons[0].id] is ProgressStatus.LOCKED:
        return ProgressStatus.LOCKED
    last = lessons[ordered_lessons[-1].id]
    if last in (ProgressStatus.COMPLETED, ProgressStatus.GOLDEN):
        return last
    return ProgressStatus.IN_PROGRESS


def _module_status(node_states: Sequence[ProgressStatus]) -> ProgressStatus:
    if not node_states or node_states[0] is ProgressStatus.LOCKED:
        return ProgressStatus.LOCKED
    done = (ProgressStatus.COMPLETED, ProgressStatus.GOLDEN)
    if all(state in done for state in node_states):
        return ProgressStatus.COMPLETED
    return ProgressStatus.IN_PROGRESS


def module_progress_percent(lesson_ids: Collection[str], passed: Collection[str]) -> int:
    """% de avance de un módulo publicado = aprobadas ÷ lecciones del módulo (§8.2), sin round()."""
    if not lesson_ids:
        return 0
    approved_set = set(passed)
    approved = sum(1 for lesson_id in lesson_ids if lesson_id in approved_set)
    return round_half_up(approved * 100, len(lesson_ids))

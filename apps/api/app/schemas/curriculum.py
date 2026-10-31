"""Esquemas de la ruta de aprendizaje (§8.2)."""

from __future__ import annotations

from app.domain.enums import LessonType, NodeKind, ProgressStatus
from app.schemas.common import ApiModel

# Lecciones: LOCKED · AVAILABLE · COMPLETED · GOLDEN. Nodos: LOCKED · IN_PROGRESS · COMPLETED ·
# GOLDEN · COMING_SOON. Módulos: LOCKED · IN_PROGRESS · COMPLETED · COMING_SOON (§7.4).


class LessonSummaryOut(ApiModel):
    id: str
    order: int
    type: LessonType
    title: str
    status: ProgressStatus
    best_score: int | None
    estimated_xp: int


class NodeSummaryOut(ApiModel):
    id: str
    order: int
    title: str
    kind: NodeKind
    status: ProgressStatus
    lessons: list[LessonSummaryOut]


class ModuleOut(ApiModel):
    id: str
    order: int
    title: str
    description: str
    published: bool
    status: ProgressStatus
    progress: int  # de 0 a 100: lecciones aprobadas ÷ lecciones del módulo publicado
    nodes: list[NodeSummaryOut]


class LearningPathOut(ApiModel):
    modules: list[ModuleOut]


class NodeSignOut(ApiModel):
    slug: str
    word: str
    poster: str
    introduced_in_lesson_id: str | None


class NodeDetailOut(ApiModel):
    id: str
    title: str
    kind: NodeKind
    status: ProgressStatus
    module_id: str
    module_title: str
    lessons: list[LessonSummaryOut]
    signs: list[NodeSignOut]

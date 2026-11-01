"""Contenido ya leído de `content/` (sin E/S) y resultado del generador (§6)."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

from app.domain.enums import ExerciseType, LessonType, Motion, NodeKind
from app.domain.exercises.models import ExercisePayload


@dataclass(frozen=True, slots=True)
class SignSpec:
    id: str  # slug
    word: str
    category: str
    node_id: str | None  # None = solo diccionario
    order: int
    motion: Motion | None = None  # letras y números


@dataclass(frozen=True, slots=True)
class NodeSpec:
    id: str
    order: int
    title: str
    kind: NodeKind


@dataclass(frozen=True, slots=True)
class ModuleSpec:
    id: str
    order: int
    title: str
    published: bool
    nodes: tuple[NodeSpec, ...]


@dataclass(frozen=True, slots=True)
class ConversationTurnSpec:
    prompt: str
    answer: str
    distractors: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class ConversationSpec:
    turns: tuple[ConversationTurnSpec, ...]


@dataclass(frozen=True, slots=True)
class NodeConversations:
    conversations: tuple[ConversationSpec, ...] = ()
    spelling: tuple[str, ...] = ()  # palabras en mayúsculas, sin tildes (la Ñ se conserva)


ConversationsByNode = Mapping[str, NodeConversations]


@dataclass(frozen=True, slots=True)
class LessonSpec:
    id: str  # "<nodo>-L1"…"-L4"
    node_id: str
    order: int  # 1..4
    type: LessonType
    title: str
    sign_ids: tuple[str, ...]  # L1 a L3: señas nuevas de la lección · L4: todas las del nodo


@dataclass(frozen=True, slots=True)
class ExerciseSpec:
    id: str  # "<lessonId>-NN"
    lesson_id: str
    order: int  # 1..N dentro de la lección
    activity: int  # 1 Observa · 2 Reconoce · 3 Produce · 4 Conversa/Deletrea
    type: ExerciseType
    sign_id: str | None
    scored: bool
    payload: ExercisePayload


@dataclass(frozen=True, slots=True)
class GeneratedContent:
    lessons: tuple[LessonSpec, ...]
    exercises: tuple[ExerciseSpec, ...]


class GenerationError(ValueError):
    """El contenido no permite generar una lección (mensaje en español para content check)."""

"""Enumeraciones del dominio (valores = texto que se guarda en la BD y se expone en la API)."""

from __future__ import annotations

from enum import StrEnum


class LessonType(StrEnum):
    LEARN = "LEARN"  # L1 Aprende
    RECOGNIZE = "RECOGNIZE"  # L2 Reconoce
    PRACTICE = "PRACTICE"  # L3 Practica
    CHALLENGE = "CHALLENGE"  # L4 Reto final


class NodeKind(StrEnum):
    STANDARD = "STANDARD"
    ALPHABET = "ALPHABET"
    NUMBERS = "NUMBERS"


class ExerciseType(StrEnum):
    OBSERVE = "OBSERVE"
    VIDEO_TO_MEANING = "VIDEO_TO_MEANING"
    MEANING_TO_VIDEO = "MEANING_TO_VIDEO"
    MEMORY_MATCH = "MEMORY_MATCH"
    PRODUCE = "PRODUCE"
    CONVERSATION = "CONVERSATION"
    SPELLING = "SPELLING"


class ProgressStatus(StrEnum):
    LOCKED = "LOCKED"
    AVAILABLE = "AVAILABLE"
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"
    GOLDEN = "GOLDEN"
    COMING_SOON = "COMING_SOON"


class Motion(StrEnum):
    STATIC = "static"
    DYNAMIC = "dynamic"

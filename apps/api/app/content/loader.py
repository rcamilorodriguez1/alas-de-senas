"""Carga de `content/` a estructuras del dominio (sin validar reglas: eso es `validation.py`)."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

from app.content.csv_reader import SignRow
from app.domain.content.models import ModuleSpec, NodeConversations, SignSpec

# Categorías y su orden (§6.2): `content` las crea así.
CATEGORIES: tuple[tuple[str, str], ...] = (
    ("saludos", "Saludos"),
    ("presentaciones", "Presentaciones"),
    ("cortesia", "Cortesía"),
    ("alfabeto", "Alfabeto"),
    ("familia", "Familia"),
    ("emociones", "Emociones"),
    ("numeros", "Números"),
    ("actividades", "Actividades"),
    ("alimentos", "Alimentos"),
    ("lugares", "Lugares"),
    ("transporte", "Transporte y objetos"),
    ("necesidades", "Necesidades"),
    ("animales", "Animales"),
)


@dataclass(frozen=True, slots=True)
class ModuleRecord:
    spec: ModuleSpec
    description: str


@dataclass(frozen=True, slots=True)
class IntroSpec:
    cards: tuple[str, ...]
    quiz: tuple[str, ...]  # slugs de `quiz[].sign`


@dataclass(frozen=True, slots=True)
class ContentBundle:
    modules: tuple[ModuleRecord, ...]
    signs: tuple[SignRow, ...]
    conversations: dict[str, NodeConversations]
    intro: IntroSpec


def load_curriculum(path: Path) -> list[ModuleRecord]:
    """`curriculum.json` (§6.1). ContentError en español si el JSON es inválido o incompleto."""
    raise NotImplementedError


def load_conversations(path: Path) -> dict[str, NodeConversations]:
    """`conversations.yaml` (§6.5) con `yaml.safe_load`. Nodo → conversaciones y/o `spelling`.

    Archivo vacío o inexistente → {}. Estructura inválida → ContentError en español que nombra
    el nodo.
    """
    raise NotImplementedError


def load_intro(path: Path) -> IntroSpec:
    raise NotImplementedError


def load_content(content_dir: Path) -> ContentBundle:
    """Lee los cuatro archivos de `content_dir` (§6.1 a §6.5)."""
    raise NotImplementedError


def to_sign_specs(rows: Sequence[SignRow]) -> list[SignSpec]:
    """Filas del CSV → SignSpec del dominio (motion «static»/«dynamic» → Motion; otro → None)."""
    raise NotImplementedError

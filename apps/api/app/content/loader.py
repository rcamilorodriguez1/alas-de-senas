"""Carga de `content/` a estructuras del dominio (sin validar reglas: eso es `validation.py`)."""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path

import yaml
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from app.content.csv_reader import SignRow, read_signs_csv
from app.content.errors import ContentError
from app.domain.content.models import (
    ConversationSpec,
    ConversationTurnSpec,
    ModuleSpec,
    NodeConversations,
    NodeSpec,
    SignSpec,
)
from app.domain.enums import Motion, NodeKind

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


class _ContentYamlLoader(yaml.SafeLoader):
    """SafeLoader sin booleanos implícitos: en YAML 1.1 la seña «no» (sin comillas) se leería
    como False. En el contenido todos los valores son texto."""


_ContentYamlLoader.yaml_implicit_resolvers = {
    first: [(tag, regexp) for tag, regexp in resolvers if tag != "tag:yaml.org,2002:bool"]
    for first, resolvers in yaml.SafeLoader.yaml_implicit_resolvers.items()
}


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
    data = _read_json(path)
    raw_modules = data.get("modules") if isinstance(data, dict) else None
    if not isinstance(raw_modules, list):
        raise ContentError('curriculum.json debe tener una lista "modules".')
    records: list[ModuleRecord] = []
    for index, raw in enumerate(raw_modules, start=1):
        label = _label(raw, f"#{index}")
        try:
            module = _ModuleIn.model_validate(raw)
        except ValidationError as exc:
            raise ContentError(f"curriculum.json, módulo {label}: {_explain(exc)}") from exc
        nodes: list[NodeSpec] = []
        for node_index, raw_node in enumerate(module.nodes, start=1):
            node_label = _label(raw_node, f"{label} nodo #{node_index}")
            try:
                node = _NodeIn.model_validate(raw_node)
            except ValidationError as exc:
                raise ContentError(f"curriculum.json, nodo {node_label}: {_explain(exc)}") from exc
            nodes.append(NodeSpec(id=node.id, order=node.order, title=node.title, kind=node.kind))
        spec = ModuleSpec(
            id=module.id,
            order=module.order,
            title=module.title,
            published=module.published,
            nodes=tuple(nodes),
        )
        records.append(ModuleRecord(spec=spec, description=module.description))
    return records


def load_conversations(path: Path) -> dict[str, NodeConversations]:
    """`conversations.yaml` (§6.5) con `yaml.safe_load`. Nodo → conversaciones y/o `spelling`.

    Archivo vacío o inexistente → {}. Estructura inválida → ContentError en español que nombra
    el nodo.
    """
    if not path.exists():
        return {}
    try:
        data = yaml.load(path.read_text(encoding="utf-8-sig"), Loader=_ContentYamlLoader)  # noqa: S506 — SafeLoader
    except yaml.YAMLError as exc:
        raise ContentError(f"conversations.yaml no es un YAML válido: {exc}") from exc
    if data is None:
        return {}
    if not isinstance(data, dict):
        raise ContentError("conversations.yaml debe ser un mapa nodo → conversaciones.")
    return {
        str(node_id): _node_conversations(str(node_id), value) for node_id, value in data.items()
    }


def load_intro(path: Path) -> IntroSpec:
    try:
        intro = _IntroIn.model_validate(_read_json(path))
    except ValidationError as exc:
        raise ContentError(f"intro.json: {_explain(exc)}") from exc
    return IntroSpec(cards=tuple(intro.cards), quiz=tuple(q.sign for q in intro.quiz))


def load_content(content_dir: Path) -> ContentBundle:
    """Lee los cuatro archivos de `content_dir` (§6.1 a §6.5)."""
    for name in ("curriculum.json", "signs.csv", "intro.json"):
        if not (content_dir / name).exists():
            raise ContentError(f"Falta el archivo content/{name}.")
    return ContentBundle(
        modules=tuple(load_curriculum(content_dir / "curriculum.json")),
        signs=tuple(read_signs_csv(content_dir / "signs.csv")),
        conversations=load_conversations(content_dir / "conversations.yaml"),
        intro=load_intro(content_dir / "intro.json"),
    )


def to_sign_specs(rows: Sequence[SignRow]) -> list[SignSpec]:
    """Filas del CSV → SignSpec del dominio (motion «static»/«dynamic» → Motion; otro → None)."""
    motions = {m.value: m for m in Motion}
    return [
        SignSpec(
            id=row.slug,
            word=row.word,
            category=row.category,
            node_id=row.node,
            order=row.order,
            motion=motions.get(row.motion or ""),
        )
        for row in rows
    ]


# ---------- Formatos de entrada (validación estructural) --------------------------------------


class _In(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class _NodeIn(_In):
    id: str = Field(min_length=1)
    order: int
    title: str = Field(min_length=1)
    kind: NodeKind = Field(strict=False)


class _ModuleIn(_In):
    id: str = Field(min_length=1)
    order: int
    title: str = Field(min_length=1)
    description: str
    published: bool
    nodes: list[object]


class _QuizIn(_In):
    sign: str = Field(min_length=1)


class _IntroIn(_In):
    cards: list[str]
    quiz: list[_QuizIn]


class _TurnIn(_In):
    prompt: str = Field(min_length=1)
    answer: str = Field(min_length=1)
    distractors: list[str]


class _ConversationIn(_In):
    turns: list[_TurnIn] = Field(min_length=1)


def _label(raw: object, fallback: str) -> str:
    if isinstance(raw, Mapping):
        value = raw.get("id")
        if isinstance(value, str) and value:
            return value
    return fallback


def _read_json(path: Path) -> object:
    try:
        data: object = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ContentError(f"{path.name} no es un JSON válido: {exc}") from exc
    return data


def _explain(exc: ValidationError) -> str:
    first = exc.errors()[0]
    where = ".".join(str(part) for part in first["loc"]) or "raíz"
    kind = first["type"]
    if kind == "missing":
        return f'falta el campo "{where}".'
    if kind == "extra_forbidden":
        return f'el campo "{where}" no está permitido.'
    return f'el campo "{where}" no tiene un valor válido.'


def _node_conversations(node_id: str, value: object) -> NodeConversations:
    if isinstance(value, Mapping):
        spelling = value.get("spelling")
        valid = (
            set(value) == {"spelling"}
            and isinstance(spelling, list)
            and all(isinstance(word, str) for word in spelling)
        )
        if not valid or not isinstance(spelling, list):
            raise ContentError(
                f"conversations.yaml, {node_id}: «spelling» debe ser una lista de palabras."
            )
        return NodeConversations(spelling=tuple(str(word) for word in spelling))
    if not isinstance(value, list):
        raise ContentError(
            f"conversations.yaml, {node_id}: debe ser una lista de conversaciones o un «spelling»."
        )
    conversations: list[ConversationSpec] = []
    for index, raw in enumerate(value, start=1):
        try:
            parsed = _ConversationIn.model_validate(raw)
        except ValidationError as exc:
            raise ContentError(
                f"conversations.yaml, {node_id}, conversación {index}: {_explain(exc)}"
            ) from exc
        turns = tuple(
            ConversationTurnSpec(prompt=t.prompt, answer=t.answer, distractors=tuple(t.distractors))
            for t in parsed.turns
        )
        conversations.append(ConversationSpec(turns=turns))
    return NodeConversations(conversations=tuple(conversations))

"""Modelos de ejercicios (§7.6): lo que guarda el servidor, lo que responde el cliente y lo que ve.

Todos usan alias camelCase (así se guardan en JSONB y se exponen en la API).
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Annotated, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, TypeAdapter, model_validator
from pydantic.alias_generators import to_camel

from app.domain.enums import ExerciseType

# Lado del token de una opción (D20): palabra, video o palabra de deletreo.
SIDE_WORD = "w"
SIDE_VIDEO = "v"
SIDE_SPELLING = "s"

# tokenize(lado, valor) -> token opaco. El servicio la construye con el secreto, la sesión y el
# ejercicio; el dominio solo la recibe.
Tokenize = Callable[[str, str], str]


class _Model(BaseModel):
    model_config = ConfigDict(
        alias_generator=to_camel, populate_by_name=True, extra="forbid", frozen=True
    )


# ---------- Payload (solo servidor) --------------------------------------------------------


class ObservePayload(_Model):
    type: Literal[ExerciseType.OBSERVE] = ExerciseType.OBSERVE
    sign_id: str


class _ChoicePayload(_Model):
    sign_id: str
    option_ids: list[str] = Field(min_length=2, max_length=4)
    correct_id: str

    @model_validator(mode="after")
    def _check_options(self) -> Self:
        if len(set(self.option_ids)) != len(self.option_ids):
            raise ValueError("Opciones repetidas")
        if self.correct_id not in self.option_ids:
            raise ValueError("La respuesta correcta no está entre las opciones")
        return self


class VideoToMeaningPayload(_ChoicePayload):
    type: Literal[ExerciseType.VIDEO_TO_MEANING] = ExerciseType.VIDEO_TO_MEANING


class MeaningToVideoPayload(_ChoicePayload):
    type: Literal[ExerciseType.MEANING_TO_VIDEO] = ExerciseType.MEANING_TO_VIDEO


class MemoryMatchPayload(_Model):
    type: Literal[ExerciseType.MEMORY_MATCH] = ExerciseType.MEMORY_MATCH
    sign_ids: list[str] = Field(min_length=2, max_length=6)


class ProducePayload(_Model):
    type: Literal[ExerciseType.PRODUCE] = ExerciseType.PRODUCE
    sign_id: str
    camera_label: str | None = None


class ConversationTurn(_Model):
    prompt_id: str
    option_ids: list[str] = Field(min_length=2, max_length=4)
    correct_id: str

    @model_validator(mode="after")
    def _check_options(self) -> Self:
        if len(set(self.option_ids)) != len(self.option_ids):
            raise ValueError("Opciones repetidas")
        if self.correct_id not in self.option_ids:
            raise ValueError("La respuesta correcta no está entre las opciones")
        return self


class ConversationPayload(_Model):
    type: Literal[ExerciseType.CONVERSATION] = ExerciseType.CONVERSATION
    turns: list[ConversationTurn] = Field(min_length=1)


class SpellingPayload(_Model):
    type: Literal[ExerciseType.SPELLING] = ExerciseType.SPELLING
    word: str
    letter_ids: list[str] = Field(min_length=1)
    option_words: list[str] = Field(min_length=2, max_length=4)

    @model_validator(mode="after")
    def _check_options(self) -> Self:
        if len(set(self.option_words)) != len(self.option_words):
            raise ValueError("Opciones repetidas")
        if self.word not in self.option_words:
            raise ValueError("La palabra no está entre las opciones")
        return self


ExercisePayload = Annotated[
    ObservePayload
    | VideoToMeaningPayload
    | MeaningToVideoPayload
    | MemoryMatchPayload
    | ProducePayload
    | ConversationPayload
    | SpellingPayload,
    Field(discriminator="type"),
]

_PAYLOAD_ADAPTER: TypeAdapter[ExercisePayload] = TypeAdapter(ExercisePayload)


def parse_payload(raw: object) -> ExercisePayload:
    """Valida un payload leído de la BD (lanza pydantic.ValidationError si está corrupto)."""
    return _PAYLOAD_ADAPTER.validate_python(raw)


def dump_payload(payload: ExercisePayload) -> dict[str, object]:
    """Payload como JSON (camelCase) para guardarlo en la BD."""
    return payload.model_dump(mode="json", by_alias=True)


# ---------- Respuestas del cliente ----------------------------------------------------------


class ObserveAnswer(_Model):
    watched: Literal[True]


class OptionAnswer(_Model):
    """VIDEO_TO_MEANING, MEANING_TO_VIDEO y SPELLING."""

    option_token: str = Field(max_length=32)


class MatchAttempt(_Model):
    video_token: str = Field(max_length=32)
    word_token: str = Field(max_length=32)


class MemoryMatchAnswer(_Model):
    attempts: list[MatchAttempt] = Field(max_length=36)


class ProduceAnswer(_Model):
    method: Literal["camera", "self"]
    ok: bool
    confidence: float | None = Field(default=None, ge=0, le=1)


class ConversationAnswer(_Model):
    choices: list[Annotated[str, Field(max_length=32)]] = Field(max_length=6)


Answer = ObserveAnswer | OptionAnswer | MemoryMatchAnswer | ProduceAnswer | ConversationAnswer


# ---------- Vista pública (lo que recibe el cliente) ----------------------------------------


class VideoRef(_Model):
    src: str
    poster: str
    # Para la interfaz (§9.4, R9.13): «Video en preparación» / «Secuencia de imágenes».
    placeholder: bool = False
    source: Literal["video", "images", "placeholder"] = "video"


class WordOption(_Model):
    token: str
    word: str


class VideoOption(_Model):
    token: str
    video: VideoRef


class PublicObserve(_Model):
    type: Literal[ExerciseType.OBSERVE] = ExerciseType.OBSERVE
    video: VideoRef
    word: str
    how_to: str | None
    usage_example: str


class PublicVideoToMeaning(_Model):
    type: Literal[ExerciseType.VIDEO_TO_MEANING] = ExerciseType.VIDEO_TO_MEANING
    video: VideoRef
    options: list[WordOption]


class PublicMeaningToVideo(_Model):
    type: Literal[ExerciseType.MEANING_TO_VIDEO] = ExerciseType.MEANING_TO_VIDEO
    word: str
    options: list[VideoOption]


class PublicMemoryMatch(_Model):
    type: Literal[ExerciseType.MEMORY_MATCH] = ExerciseType.MEMORY_MATCH
    video_cards: list[VideoOption]
    word_cards: list[WordOption]


class PublicProduce(_Model):
    type: Literal[ExerciseType.PRODUCE] = ExerciseType.PRODUCE
    video: VideoRef
    word: str
    camera_label: str | None


class PublicConversationTurn(_Model):
    prompt: VideoRef
    options: list[VideoOption]


class PublicConversation(_Model):
    type: Literal[ExerciseType.CONVERSATION] = ExerciseType.CONVERSATION
    turns: list[PublicConversationTurn]


class PublicSpelling(_Model):
    type: Literal[ExerciseType.SPELLING] = ExerciseType.SPELLING
    letters: list[VideoRef]
    options: list[WordOption]


PublicExercise = Annotated[
    PublicObserve
    | PublicVideoToMeaning
    | PublicMeaningToVideo
    | PublicMemoryMatch
    | PublicProduce
    | PublicConversation
    | PublicSpelling,
    Field(discriminator="type"),
]


# ---------- Catálogo de señas y retroalimentación -------------------------------------------


@dataclass(frozen=True, slots=True)
class CatalogSign:
    id: str
    word: str
    how_to: str | None
    usage_example: str
    video: VideoRef


SignCatalog = Mapping[str, CatalogSign]


@dataclass(frozen=True, slots=True)
class CorrectFeedback:
    """Lo que la interfaz necesita para marcar la respuesta correcta después de contestar."""

    tokens: tuple[str, ...] = ()
    word: str | None = None

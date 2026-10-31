"""Evaluadores de ejercicios: un tipo de ejercicio = una clase (polimorfismo, §7.6)."""

from __future__ import annotations

import builtins
from abc import ABC, abstractmethod
from collections.abc import Sequence
from typing import ClassVar, Protocol

from pydantic import BaseModel

from app.domain.enums import ExerciseType
from app.domain.exercises.models import (
    SIDE_SPELLING,
    SIDE_VIDEO,
    SIDE_WORD,
    ConversationAnswer,
    ConversationPayload,
    CorrectFeedback,
    ExercisePayload,
    MeaningToVideoPayload,
    MemoryMatchAnswer,
    MemoryMatchPayload,
    ObserveAnswer,
    ObservePayload,
    OptionAnswer,
    ProduceAnswer,
    ProducePayload,
    PublicConversation,
    PublicConversationTurn,
    PublicExercise,
    PublicMeaningToVideo,
    PublicMemoryMatch,
    PublicObserve,
    PublicProduce,
    PublicSpelling,
    PublicVideoToMeaning,
    SignCatalog,
    SpellingPayload,
    Tokenize,
    VideoOption,
    VideoToMeaningPayload,
    WordOption,
)


def _expect[T](value: object, kind: builtins.type[T]) -> T:
    if not isinstance(value, kind):
        raise TypeError(f"Se esperaba {kind.__name__} y llegó {builtins.type(value).__name__}")
    return value


class _Tokened(Protocol):
    @property
    def token(self) -> str: ...


def _by_token[O: _Tokened](options: Sequence[O]) -> list[O]:
    """Orden público de las opciones: por token (D-008).

    Los tokens son HMAC con el secreto del servidor: el orden es estable dentro de la sesión y no
    se puede reproducir desde lo que conoce el cliente (`sessionId`, `exerciseId`), a diferencia de
    un barajado con semilla pública. Videos y palabras tienen tokens independientes, así que en
    MEMORY_MATCH las dos columnas no revelan las parejas.
    """
    return sorted(options, key=lambda option: option.token)


class ExerciseEvaluator(ABC):
    type: ClassVar[ExerciseType]
    scored: ClassVar[bool]
    answer_model: ClassVar[builtins.type[BaseModel]]

    def parse_answer(self, raw: object) -> BaseModel:
        """Valida la respuesta del cliente (lanza pydantic.ValidationError)."""
        return self.answer_model.model_validate(raw)

    @abstractmethod
    def evaluate(self, payload: ExercisePayload, answer: BaseModel, tokenize: Tokenize) -> bool:
        """TypeError si el payload o la respuesta no son del tipo de este evaluador."""

    @abstractmethod
    def to_public(
        self,
        payload: ExercisePayload,
        catalog: SignCatalog,
        tokenize: Tokenize,
    ) -> PublicExercise:
        """Vista para el cliente: sin `correctId`, `signId` ni slugs en las opciones (D20)."""

    def feedback(
        self, payload: ExercisePayload, catalog: SignCatalog, tokenize: Tokenize
    ) -> CorrectFeedback:
        if payload.type is not self.type:
            raise TypeError(f"Payload {payload.type} no corresponde a {self.type}")
        return CorrectFeedback()


class ObserveEvaluator(ExerciseEvaluator):
    type = ExerciseType.OBSERVE
    scored = False
    answer_model = ObserveAnswer

    def evaluate(self, payload: ExercisePayload, answer: BaseModel, tokenize: Tokenize) -> bool:
        _expect(payload, ObservePayload)
        _expect(answer, ObserveAnswer)
        return True

    def to_public(
        self,
        payload: ExercisePayload,
        catalog: SignCatalog,
        tokenize: Tokenize,
    ) -> PublicExercise:
        sign = catalog[_expect(payload, ObservePayload).sign_id]
        return PublicObserve(
            video=sign.video, word=sign.word, how_to=sign.how_to, usage_example=sign.usage_example
        )


class VideoToMeaningEvaluator(ExerciseEvaluator):
    type = ExerciseType.VIDEO_TO_MEANING
    scored = True
    answer_model = OptionAnswer

    def evaluate(self, payload: ExercisePayload, answer: BaseModel, tokenize: Tokenize) -> bool:
        p = _expect(payload, VideoToMeaningPayload)
        return _expect(answer, OptionAnswer).option_token == tokenize(SIDE_WORD, p.correct_id)

    def to_public(
        self,
        payload: ExercisePayload,
        catalog: SignCatalog,
        tokenize: Tokenize,
    ) -> PublicExercise:
        p = _expect(payload, VideoToMeaningPayload)
        options = [
            WordOption(token=tokenize(SIDE_WORD, sign_id), word=catalog[sign_id].word)
            for sign_id in p.option_ids
        ]
        return PublicVideoToMeaning(video=catalog[p.sign_id].video, options=_by_token(options))

    def feedback(
        self, payload: ExercisePayload, catalog: SignCatalog, tokenize: Tokenize
    ) -> CorrectFeedback:
        p = _expect(payload, VideoToMeaningPayload)
        return CorrectFeedback((tokenize(SIDE_WORD, p.correct_id),), catalog[p.correct_id].word)


class MeaningToVideoEvaluator(ExerciseEvaluator):
    type = ExerciseType.MEANING_TO_VIDEO
    scored = True
    answer_model = OptionAnswer

    def evaluate(self, payload: ExercisePayload, answer: BaseModel, tokenize: Tokenize) -> bool:
        p = _expect(payload, MeaningToVideoPayload)
        return _expect(answer, OptionAnswer).option_token == tokenize(SIDE_VIDEO, p.correct_id)

    def to_public(
        self,
        payload: ExercisePayload,
        catalog: SignCatalog,
        tokenize: Tokenize,
    ) -> PublicExercise:
        p = _expect(payload, MeaningToVideoPayload)
        options = [
            VideoOption(token=tokenize(SIDE_VIDEO, sign_id), video=catalog[sign_id].video)
            for sign_id in p.option_ids
        ]
        return PublicMeaningToVideo(word=catalog[p.sign_id].word, options=_by_token(options))

    def feedback(
        self, payload: ExercisePayload, catalog: SignCatalog, tokenize: Tokenize
    ) -> CorrectFeedback:
        p = _expect(payload, MeaningToVideoPayload)
        return CorrectFeedback((tokenize(SIDE_VIDEO, p.correct_id),), catalog[p.correct_id].word)


class MemoryMatchEvaluator(ExerciseEvaluator):
    type = ExerciseType.MEMORY_MATCH
    scored = True
    answer_model = MemoryMatchAnswer

    def evaluate(self, payload: ExercisePayload, answer: BaseModel, tokenize: Tokenize) -> bool:
        p = _expect(payload, MemoryMatchPayload)
        attempts = _expect(answer, MemoryMatchAnswer).attempts
        pairs = {(tokenize(SIDE_VIDEO, s), tokenize(SIDE_WORD, s)): s for s in p.sign_ids}
        matched: set[str] = set()
        errors = 0
        for attempt in attempts:
            sign_id = pairs.get((attempt.video_token, attempt.word_token))
            if sign_id is None:
                errors += 1
            else:
                matched.add(sign_id)  # repetir un par ya emparejado no suma ni resta
        return len(matched) == len(p.sign_ids) and errors <= len(p.sign_ids)

    def to_public(
        self,
        payload: ExercisePayload,
        catalog: SignCatalog,
        tokenize: Tokenize,
    ) -> PublicExercise:
        p = _expect(payload, MemoryMatchPayload)
        videos = [
            VideoOption(token=tokenize(SIDE_VIDEO, s), video=catalog[s].video) for s in p.sign_ids
        ]
        words = [WordOption(token=tokenize(SIDE_WORD, s), word=catalog[s].word) for s in p.sign_ids]
        return PublicMemoryMatch(video_cards=_by_token(videos), word_cards=_by_token(words))


class ProduceEvaluator(ExerciseEvaluator):
    type = ExerciseType.PRODUCE
    scored = False
    answer_model = ProduceAnswer

    def evaluate(self, payload: ExercisePayload, answer: BaseModel, tokenize: Tokenize) -> bool:
        _expect(payload, ProducePayload)
        return _expect(answer, ProduceAnswer).ok

    def to_public(
        self,
        payload: ExercisePayload,
        catalog: SignCatalog,
        tokenize: Tokenize,
    ) -> PublicExercise:
        p = _expect(payload, ProducePayload)
        sign = catalog[p.sign_id]
        return PublicProduce(video=sign.video, word=sign.word, camera_label=p.camera_label)


class ConversationEvaluator(ExerciseEvaluator):
    type = ExerciseType.CONVERSATION
    scored = True
    answer_model = ConversationAnswer

    def evaluate(self, payload: ExercisePayload, answer: BaseModel, tokenize: Tokenize) -> bool:
        p = _expect(payload, ConversationPayload)
        choices = _expect(answer, ConversationAnswer).choices
        if len(choices) != len(p.turns):
            return False
        return all(
            choice == tokenize(SIDE_VIDEO, turn.correct_id)
            for choice, turn in zip(choices, p.turns, strict=True)
        )

    def to_public(
        self,
        payload: ExercisePayload,
        catalog: SignCatalog,
        tokenize: Tokenize,
    ) -> PublicExercise:
        p = _expect(payload, ConversationPayload)
        turns = [
            PublicConversationTurn(
                prompt=catalog[turn.prompt_id].video,
                options=_by_token(
                    [
                        VideoOption(token=tokenize(SIDE_VIDEO, s), video=catalog[s].video)
                        for s in turn.option_ids
                    ]
                ),
            )
            for turn in p.turns
        ]
        return PublicConversation(turns=turns)

    def feedback(
        self, payload: ExercisePayload, catalog: SignCatalog, tokenize: Tokenize
    ) -> CorrectFeedback:
        p = _expect(payload, ConversationPayload)
        return CorrectFeedback(tuple(tokenize(SIDE_VIDEO, t.correct_id) for t in p.turns))


class SpellingEvaluator(ExerciseEvaluator):
    type = ExerciseType.SPELLING
    scored = True
    answer_model = OptionAnswer

    def evaluate(self, payload: ExercisePayload, answer: BaseModel, tokenize: Tokenize) -> bool:
        p = _expect(payload, SpellingPayload)
        return _expect(answer, OptionAnswer).option_token == tokenize(SIDE_SPELLING, p.word)

    def to_public(
        self,
        payload: ExercisePayload,
        catalog: SignCatalog,
        tokenize: Tokenize,
    ) -> PublicExercise:
        p = _expect(payload, SpellingPayload)
        options = [WordOption(token=tokenize(SIDE_SPELLING, w), word=w) for w in p.option_words]
        return PublicSpelling(
            letters=[catalog[letter].video for letter in p.letter_ids],
            options=_by_token(options),
        )

    def feedback(
        self, payload: ExercisePayload, catalog: SignCatalog, tokenize: Tokenize
    ) -> CorrectFeedback:
        p = _expect(payload, SpellingPayload)
        return CorrectFeedback((tokenize(SIDE_SPELLING, p.word),), p.word)


EVALUATORS: dict[ExerciseType, ExerciseEvaluator] = {
    e.type: e
    for e in (
        ObserveEvaluator(),
        VideoToMeaningEvaluator(),
        MeaningToVideoEvaluator(),
        MemoryMatchEvaluator(),
        ProduceEvaluator(),
        ConversationEvaluator(),
        SpellingEvaluator(),
    )
}


def get_evaluator(exercise_type: ExerciseType) -> ExerciseEvaluator:
    return EVALUATORS[exercise_type]

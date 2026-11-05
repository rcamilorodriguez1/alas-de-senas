"""Generador determinista de lecciones y ejercicios (§6.7): `random.Random` con semilla de texto."""

from __future__ import annotations

import random
from collections.abc import Callable, Collection, Mapping, Sequence
from dataclasses import dataclass

from pydantic import ValidationError

from app.domain.content.distractors import pick_distractors
from app.domain.content.models import (
    ConversationsByNode,
    ConversationSpec,
    ExerciseSpec,
    GeneratedContent,
    GenerationError,
    LessonSpec,
    ModuleSpec,
    NodeConversations,
    NodeSpec,
    SignSpec,
)
from app.domain.enums import ExerciseType, LessonType, Motion, NodeKind
from app.domain.exercises.evaluators import EVALUATORS
from app.domain.exercises.models import (
    ConversationPayload,
    ConversationTurn,
    ExercisePayload,
    MeaningToVideoPayload,
    MemoryMatchPayload,
    ObservePayload,
    ProducePayload,
    SpellingPayload,
    VideoToMeaningPayload,
)

LESSON_TITLES: Mapping[LessonType, str] = {
    LessonType.LEARN: "Aprende",
    LessonType.RECOGNIZE: "Reconoce",
    LessonType.PRACTICE: "Practica",
    LessonType.CHALLENGE: "Reto final",
}
LESSON_TYPES = (LessonType.LEARN, LessonType.RECOGNIZE, LessonType.PRACTICE, LessonType.CHALLENGE)

ACTIVITY: Mapping[ExerciseType, int] = {
    ExerciseType.OBSERVE: 1,
    ExerciseType.VIDEO_TO_MEANING: 2,
    ExerciseType.MEANING_TO_VIDEO: 2,
    ExerciseType.MEMORY_MATCH: 2,
    ExerciseType.PRODUCE: 3,
    ExerciseType.CONVERSATION: 4,
    ExerciseType.SPELLING: 4,
}

ALPHABET_CATEGORY = "alfabeto"
DISTRACTORS = 3
MAX_MEMORY_PAIRS = 6


def split_counts(kind: NodeKind, n: int) -> tuple[int, int, int]:
    """Cuántas señas nuevas tienen L1, L2 y L3 en un nodo de `n` señas."""
    if kind is NodeKind.ALPHABET:
        a = -(-n // 3)
        b = -(-(n - a) // 2)
    else:
        a = 3 if n >= 7 else 2
        b = min(3 if n >= 6 else 2, n - a - 1)
    return a, b, n - a - b


def split_word_into_letters(word: str, letters: Mapping[str, str]) -> list[str]:
    """Separa `word` en slugs de letras por coincidencia más larga primero.

    `letters`: texto de la letra en mayúsculas («A», «Ñ», «LL») → slug. ValueError si no se puede
    (incluida una palabra en minúsculas: el contenido debe venir en mayúsculas).
    """
    text = word  # las palabras de deletreo se escriben en mayúsculas (§6.5)
    longest = max((len(key) for key in letters), default=0)
    result: list[str] = []
    i = 0
    while i < len(text):
        for size in range(min(longest, len(text) - i), 0, -1):
            slug = letters.get(text[i : i + size])
            if slug is not None:
                result.append(slug)
                i += size
                break
        else:
            raise ValueError(f"«{word}» usa «{text[i]}», que no es una letra del alfabeto.")
    return result


@dataclass(frozen=True, slots=True)
class _NodeContext:
    node: NodeSpec
    signs: tuple[SignSpec, ...]  # del nodo, por `order`
    split: tuple[tuple[SignSpec, ...], tuple[SignSpec, ...], tuple[SignSpec, ...]]
    previous: tuple[SignSpec, ...]  # señas de nodos anteriores (orden global)
    pool: tuple[SignSpec, ...]  # señas de todos los nodos publicados
    conversations: NodeConversations
    letters: Mapping[str, str]


def generate_content(
    modules: Sequence[ModuleSpec],
    signs: Sequence[SignSpec],
    conversations: ConversationsByNode,
) -> GeneratedContent:
    nodes = [
        node
        for module in sorted(modules, key=lambda m: m.order)
        if module.published
        for node in sorted(module.nodes, key=lambda n: n.order)
    ]
    by_node: dict[str, list[SignSpec]] = {}
    for sign in signs:
        if sign.node_id is not None:
            by_node.setdefault(sign.node_id, []).append(sign)
    node_signs = {
        node.id: tuple(sorted(by_node.get(node.id, []), key=lambda s: s.order)) for node in nodes
    }
    pool = tuple(s for node in nodes for s in node_signs[node.id])
    letters = {s.word.upper(): s.id for s in signs if s.category == ALPHABET_CATEGORY}

    lessons: list[LessonSpec] = []
    exercises: list[ExerciseSpec] = []
    previous: list[SignSpec] = []
    for node in nodes:
        own = node_signs[node.id]
        a, b, c = split_counts(node.kind, len(own))
        if min(a, b, c) < 1:
            raise GenerationError(
                f"{node.id} tiene {len(own)} señas: no alcanzan para repartirlas en 3 lecciones."
            )
        ctx = _NodeContext(
            node=node,
            signs=own,
            split=(own[:a], own[a : a + b], own[a + b :]),
            previous=tuple(previous),
            pool=pool,
            conversations=conversations.get(node.id, NodeConversations()),
            letters=letters,
        )
        used_words: list[str] = []
        for order, lesson_type in enumerate(LESSON_TYPES, start=1):
            lesson_id = f"{node.id}-L{order}"
            new = ctx.split[order - 1] if order <= 3 else own
            lessons.append(
                LessonSpec(
                    id=lesson_id,
                    node_id=node.id,
                    order=order,
                    type=lesson_type,
                    title=LESSON_TITLES[lesson_type],
                    sign_ids=tuple(s.id for s in new),
                )
            )
            builder = _LessonBuilder(ctx, lesson_id, order, used_words)
            exercises.extend(builder.build())
        previous.extend(own)
    return GeneratedContent(lessons=tuple(lessons), exercises=tuple(exercises))


def generate_exercises(
    modules: Sequence[ModuleSpec],
    signs: Sequence[SignSpec],
    conversations: ConversationsByNode,
) -> list[ExerciseSpec]:
    return list(generate_content(modules, signs, conversations).exercises)


class _LessonBuilder:
    def __init__(
        self, ctx: _NodeContext, lesson_id: str, order: int, used_words: list[str]
    ) -> None:
        self.ctx = ctx
        self.lesson_id = lesson_id
        self.order = order
        self.used_words = used_words
        self.rng = random.Random(f"alas:{lesson_id}")  # noqa: S311 — barajado reproducible, no criptográfico
        self.new = ctx.split[order - 1] if order <= 3 else ctx.signs
        introduced = [s for part in ctx.split[: min(order, 3)] for s in part]
        self.introduced = tuple(introduced)  # señas del nodo enseñadas hasta esta lección
        self.allowed = {s.id for s in (*ctx.previous, *introduced)}
        self.items: list[tuple[ExerciseType, str | None, ExercisePayload]] = []

    # ---- construcción ----------------------------------------------------------------------

    def build(self) -> list[ExerciseSpec]:
        steps: Mapping[int, Callable[[], None]] = {
            1: self._learn,
            2: self._recognize,
            3: self._practice,
            4: self._challenge,
        }
        steps[self.order]()
        return [
            ExerciseSpec(
                id=f"{self.lesson_id}-{i:02d}",
                lesson_id=self.lesson_id,
                order=i,
                activity=ACTIVITY[kind],
                type=kind,
                sign_id=sign_id,
                scored=EVALUATORS[kind].scored,
                payload=payload,
            )
            for i, (kind, sign_id, payload) in enumerate(self.items, start=1)
        ]

    # Primero se observan todas las señas nuevas y después se recuerdan en orden mezclado (D-021):
    # preguntar justo después de mostrar la respuesta no hacía recordar nada.

    def _learn(self) -> None:
        self._observe_all()
        for sign in self._mixed():
            self._choice(ExerciseType.VIDEO_TO_MEANING, sign)
        for sign in self.new:
            self._produce(sign)
        for sign in self._mixed():
            self._choice(ExerciseType.MEANING_TO_VIDEO, sign)

    def _recognize(self) -> None:
        self._observe_all()
        for sign in self._mixed():
            self._choice(ExerciseType.VIDEO_TO_MEANING, sign)
        for sign in self._mixed():
            self._choice(ExerciseType.MEANING_TO_VIDEO, sign)
        self._final_activity(turns=2)

    def _practice(self) -> None:
        self._observe_all()
        for sign in self._mixed():
            self._choice(ExerciseType.VIDEO_TO_MEANING, sign)
        for sign in self._mixed():
            self._choice(ExerciseType.MEANING_TO_VIDEO, sign)
        for sign in self.new:
            self._produce(sign)
        self._memory_match()
        self._final_activity(turns=2)

    def _observe_all(self) -> None:
        for sign in self.new:
            self._observe(sign)

    def _mixed(self) -> list[SignSpec]:
        """Señas nuevas en orden aleatorio reproducible (rng de la lección); la primera nunca es
        la última que se acaba de mostrar, para que haya que recordar y no solo repetir."""
        signs = list(self.new)
        self.rng.shuffle(signs)
        if len(signs) > 1 and signs[0] == self.new[-1]:
            signs[0], signs[1] = signs[1], signs[0]
        return signs

    def _challenge(self) -> None:
        signs = list(self.ctx.signs)
        n = len(signs)
        self.rng.shuffle(signs)
        for i in range(min(10, max(8, 2 * n))):
            kind = ExerciseType.VIDEO_TO_MEANING if i % 2 == 0 else ExerciseType.MEANING_TO_VIDEO
            self._choice(kind, signs[i % n])
        self._memory_match()
        self._final_activity(turns=3)

    # ---- ejercicios ------------------------------------------------------------------------

    def _observe(self, sign: SignSpec) -> None:
        self.items.append((ExerciseType.OBSERVE, sign.id, ObservePayload(sign_id=sign.id)))

    def _produce(self, sign: SignSpec) -> None:
        # Letras y números estáticos: modelo del alfabeto (§10, D-019). Con movimiento: modelo de
        # gestos (anexo A.10); el cliente usa la cámara solo si el modelo publicado conoce la seña.
        static_sign = sign.motion is Motion.STATIC
        payload = ProducePayload(
            sign_id=sign.id,
            camera_label=sign.id if static_sign else None,
            gesture_label=None if static_sign else sign.id,
        )
        self.items.append((ExerciseType.PRODUCE, sign.id, payload))

    def _choice(self, kind: ExerciseType, sign: SignSpec) -> None:
        option_ids = [sign.id, *(d.id for d in self._distractors(sign))]
        payload: ExercisePayload
        if kind is ExerciseType.VIDEO_TO_MEANING:
            payload = VideoToMeaningPayload(
                sign_id=sign.id, option_ids=option_ids, correct_id=sign.id
            )
        else:
            payload = MeaningToVideoPayload(
                sign_id=sign.id, option_ids=option_ids, correct_id=sign.id
            )
        self.items.append((kind, sign.id, payload))

    def _memory_match(self) -> None:
        candidates = list(self.introduced)
        if len(candidates) > MAX_MEMORY_PAIRS:
            chosen = set(self.rng.sample([s.id for s in candidates], MAX_MEMORY_PAIRS))
            candidates = [s for s in candidates if s.id in chosen]
        payload = MemoryMatchPayload(sign_ids=[s.id for s in candidates])
        self.items.append((ExerciseType.MEMORY_MATCH, None, payload))

    def _final_activity(self, turns: int) -> None:
        if self.ctx.node.kind is NodeKind.ALPHABET:
            self._spelling()
        else:
            self._conversation(turns)

    def _conversation(self, turns: int) -> None:
        conversation = _first_conversation(
            self.ctx.conversations.conversations, turns, self.allowed
        )
        if conversation is None:
            node_id = self.ctx.node.id
            if self.order == 2:
                raise GenerationError(
                    f"{node_id} necesita una conversación que use solo señas de L1–L2 "  # noqa: RUF001 — texto exacto de §6.5
                    "o de nodos anteriores."
                )
            raise GenerationError(
                f"{self.lesson_id} necesita una conversación de {turns} turnos con señas ya "
                "enseñadas."
            )
        for t in conversation.turns:
            if t.prompt in (t.answer, *t.distractors):
                # El video del estímulo sería idéntico al de una opción (D-008).
                raise GenerationError(
                    f"{self.ctx.node.id}: en la conversación, «{t.prompt}» no puede aparecer "
                    "entre sus propias opciones."
                )
        try:
            payload = ConversationPayload(
                turns=[
                    ConversationTurn(
                        prompt_id=t.prompt,
                        option_ids=[t.answer, *t.distractors],
                        correct_id=t.answer,
                    )
                    for t in conversation.turns
                ]
            )
        except ValidationError as exc:
            raise GenerationError(
                f"{self.ctx.node.id}: un turno de conversación tiene opciones repetidas o más de "
                "3 distractores."
            ) from exc
        self.items.append((ExerciseType.CONVERSATION, None, payload))

    def _spelling(self) -> None:
        words = self.ctx.conversations.spelling
        for word in words:
            if word != word.upper():
                raise GenerationError(
                    f"{self.ctx.node.id}: la palabra de deletreo «{word}» debe ir en mayúsculas."
                )
        valid: list[tuple[str, list[str]]] = []
        for word in words:
            try:
                letters = split_word_into_letters(word, self.ctx.letters)
            except ValueError:
                continue
            if all(letter in self.allowed for letter in letters):
                valid.append((word, letters))
        if not valid:
            raise GenerationError(f"{self.lesson_id} no tiene palabras de deletreo válidas.")
        fresh = [item for item in valid if item[0] not in self.used_words]
        word, letters = (fresh or valid)[0]
        self.used_words.append(word)
        others = [w for w in dict.fromkeys(words) if w != word]
        if not others:
            raise GenerationError(
                f"{self.ctx.node.id} necesita al menos 2 palabras de deletreo para dar opciones."
            )
        option_words = [word, *self.rng.sample(others, min(DISTRACTORS, len(others)))]
        payload = SpellingPayload(word=word, letter_ids=letters, option_words=option_words)
        self.items.append((ExerciseType.SPELLING, None, payload))

    # ---- distractores ----------------------------------------------------------------------

    def _distractors(self, sign: SignSpec) -> list[SignSpec]:
        node_ids = {s.id for s in self.ctx.signs}
        tiers: list[Sequence[SignSpec]] = [
            self.new,
            [s for s in self.ctx.signs if s not in self.new],
            [s for s in self.ctx.pool if s.category == sign.category and s.id not in node_ids],
            self.ctx.previous,
        ]
        chosen = pick_distractors(sign, tiers, self.rng, DISTRACTORS)
        if len(chosen) < DISTRACTORS:
            raise GenerationError(
                f"{self.lesson_id}: no hay suficientes señas distintas para las opciones de "
                f"«{sign.word}»."
            )
        return chosen


def _first_conversation(
    conversations: Sequence[ConversationSpec], turns: int, allowed: Collection[str]
) -> ConversationSpec | None:
    for conversation in conversations:
        if len(conversation.turns) != turns:
            continue
        used = {slug for t in conversation.turns for slug in (t.prompt, t.answer, *t.distractors)}
        if used <= set(allowed):
            return conversation
    return None

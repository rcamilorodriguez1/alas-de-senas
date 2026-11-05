"""Tarea 1.8 — evaluadores de ejercicios, tokens opacos (D20) y vistas públicas (§7.6, R4.4-4.7)."""

from __future__ import annotations

import random
from collections.abc import Iterator
from functools import cache

import pytest
from pydantic import BaseModel, ValidationError

from app.domain.content.generator import generate_content
from app.domain.content.models import GeneratedContent
from app.domain.enums import ExerciseType
from app.domain.exercises.evaluators import EVALUATORS, ExerciseEvaluator, get_evaluator
from app.domain.exercises.models import (
    ConversationAnswer,
    ConversationPayload,
    ConversationTurn,
    CorrectFeedback,
    ExercisePayload,
    MatchAttempt,
    MeaningToVideoPayload,
    MemoryMatchAnswer,
    MemoryMatchPayload,
    ObserveAnswer,
    ObservePayload,
    OptionAnswer,
    ProduceAnswer,
    ProducePayload,
    PublicConversation,
    PublicMeaningToVideo,
    PublicMemoryMatch,
    PublicObserve,
    PublicProduce,
    PublicSpelling,
    PublicVideoToMeaning,
    SpellingPayload,
    VideoOption,
    VideoToMeaningPayload,
    WordOption,
)
from tests.unit.domain.content_fixture import (
    all_slugs,
    build_catalog,
    build_conversations,
    build_modules,
    build_signs,
    fake_tokenize,
)

CATALOG = build_catalog()
TOK = fake_tokenize("S1", "M1-N1-L1-01")
T = ExerciseType

V2M = VideoToMeaningPayload(
    sign_id="hola", option_ids=["hola", "adios", "gracias", "yo"], correct_id="hola"
)
M2V = MeaningToVideoPayload(
    sign_id="adios", option_ids=["adios", "hola", "gracias", "yo"], correct_id="adios"
)
OBSERVE = ObservePayload(sign_id="gracias")
PRODUCE = ProducePayload(sign_id="letra-a", camera_label="letra-a")
MEMORY = MemoryMatchPayload(sign_ids=["hola", "adios", "gracias"])
CONVERSATION = ConversationPayload(
    turns=[
        ConversationTurn(
            prompt_id="hola", option_ids=["hola", "adios", "buenas-noches"], correct_id="hola"
        ),
        ConversationTurn(
            prompt_id="como-estas",
            option_ids=["buenos-dias", "adios", "buenas-noches"],
            correct_id="buenos-dias",
        ),
    ]
)
SPELLING = SpellingPayload(
    word="CADA",
    letter_ids=["letra-c", "letra-a", "letra-d", "letra-a"],
    option_words=["CADA", "BEBE", "HADA", "FE"],
)

PAYLOADS: dict[ExerciseType, ExercisePayload] = {
    T.OBSERVE: OBSERVE,
    T.VIDEO_TO_MEANING: V2M,
    T.MEANING_TO_VIDEO: M2V,
    T.MEMORY_MATCH: MEMORY,
    T.PRODUCE: PRODUCE,
    T.CONVERSATION: CONVERSATION,
    T.SPELLING: SPELLING,
}

VALID_RAW_ANSWERS: dict[ExerciseType, object] = {
    T.OBSERVE: {"watched": True},
    T.VIDEO_TO_MEANING: {"optionToken": "abc"},
    T.MEANING_TO_VIDEO: {"optionToken": "abc"},
    T.MEMORY_MATCH: {"attempts": [{"videoToken": "a", "wordToken": "b"}]},
    T.PRODUCE: {"method": "self", "ok": True},
    T.CONVERSATION: {"choices": ["a", "b"]},
    T.SPELLING: {"optionToken": "abc"},
}

ANSWER_MODELS: dict[ExerciseType, type[BaseModel]] = {
    T.OBSERVE: ObserveAnswer,
    T.VIDEO_TO_MEANING: OptionAnswer,
    T.MEANING_TO_VIDEO: OptionAnswer,
    T.MEMORY_MATCH: MemoryMatchAnswer,
    T.PRODUCE: ProduceAnswer,
    T.CONVERSATION: ConversationAnswer,
    T.SPELLING: OptionAnswer,
}

SAMPLE_ANSWERS: dict[type[BaseModel], BaseModel] = {
    ObserveAnswer: ObserveAnswer(watched=True),
    OptionAnswer: OptionAnswer(option_token="abc"),
    MemoryMatchAnswer: MemoryMatchAnswer(attempts=[]),
    ProduceAnswer: ProduceAnswer(method="self", ok=True),
    ConversationAnswer: ConversationAnswer(choices=[]),
}


def ev(exercise_type: ExerciseType) -> ExerciseEvaluator:
    return get_evaluator(exercise_type)


# ---------- Registro --------------------------------------------------------------------------


def test_registry_has_the_seven_types() -> None:
    assert set(EVALUATORS) == set(ExerciseType)
    assert len(EVALUATORS) == 7


@pytest.mark.parametrize("exercise_type", list(ExerciseType))
def test_get_evaluator_returns_registered_instance(exercise_type: ExerciseType) -> None:
    evaluator = get_evaluator(exercise_type)
    assert evaluator is EVALUATORS[exercise_type]
    assert isinstance(evaluator, ExerciseEvaluator)
    assert evaluator.type is exercise_type


@pytest.mark.parametrize(
    ("exercise_type", "scored"),
    [
        (T.OBSERVE, False),
        (T.PRODUCE, False),
        (T.VIDEO_TO_MEANING, True),
        (T.MEANING_TO_VIDEO, True),
        (T.MEMORY_MATCH, True),
        (T.CONVERSATION, True),
        (T.SPELLING, True),
    ],
)
def test_scored_flag(exercise_type: ExerciseType, scored: bool) -> None:
    assert ev(exercise_type).scored is scored


# ---------- parse_answer ----------------------------------------------------------------------


@pytest.mark.parametrize("exercise_type", list(ExerciseType))
def test_parse_answer_returns_expected_model(exercise_type: ExerciseType) -> None:
    evaluator = ev(exercise_type)
    assert evaluator.answer_model is ANSWER_MODELS[exercise_type]
    parsed = evaluator.parse_answer(VALID_RAW_ANSWERS[exercise_type])
    assert type(parsed) is ANSWER_MODELS[exercise_type]


@pytest.mark.parametrize("exercise_type", list(ExerciseType))
def test_parse_answer_rejects_extra_fields(exercise_type: ExerciseType) -> None:
    raw = VALID_RAW_ANSWERS[exercise_type]
    assert isinstance(raw, dict)
    with pytest.raises(ValidationError):
        ev(exercise_type).parse_answer({**raw, "isCorrect": True})


@pytest.mark.parametrize("exercise_type", list(ExerciseType))
@pytest.mark.parametrize("raw", [None, "x", 7, [], {}])
def test_parse_answer_rejects_invalid_input(exercise_type: ExerciseType, raw: object) -> None:
    with pytest.raises(ValidationError):
        ev(exercise_type).parse_answer(raw)


def test_parse_answer_accepts_camel_case_option_token() -> None:
    parsed = ev(T.VIDEO_TO_MEANING).parse_answer({"optionToken": "a1b2c3d4e5"})
    assert parsed == OptionAnswer(option_token="a1b2c3d4e5")


def test_parse_answer_observe_requires_watched_true() -> None:
    with pytest.raises(ValidationError):
        ev(T.OBSERVE).parse_answer({"watched": False})


def test_parse_answer_produce_validates_confidence_range() -> None:
    with pytest.raises(ValidationError):
        ev(T.PRODUCE).parse_answer({"method": "camera", "ok": True, "confidence": 2})


def test_parse_answer_memory_match_camel_case() -> None:
    parsed = ev(T.MEMORY_MATCH).parse_answer(
        {"attempts": [{"videoToken": "v1", "wordToken": "w1"}]}
    )
    assert parsed == MemoryMatchAnswer(attempts=[MatchAttempt(video_token="v1", word_token="w1")])


# ---------- evaluate --------------------------------------------------------------------------


def test_observe_is_always_correct() -> None:
    assert ev(T.OBSERVE).evaluate(OBSERVE, ObserveAnswer(watched=True), TOK) is True


@pytest.mark.parametrize("ok", [True, False])
def test_produce_returns_answer_ok(ok: bool) -> None:
    for method in ("camera", "self"):
        answer = ProduceAnswer(method=method, ok=ok, confidence=0.5 if method == "camera" else None)
        assert ev(T.PRODUCE).evaluate(PRODUCE, answer, TOK) is ok


def test_video_to_meaning_correct_word_token() -> None:
    answer = OptionAnswer(option_token=TOK("w", "hola"))
    assert ev(T.VIDEO_TO_MEANING).evaluate(V2M, answer, TOK) is True


@pytest.mark.parametrize(
    "token",
    [
        TOK("w", "adios"),  # distractor
        TOK("v", "hola"),  # lado equivocado
        TOK("s", "hola"),
        "hola",  # el slug nunca es un token válido
        "",
        "0000000000",
    ],
)
def test_video_to_meaning_wrong_tokens(token: str) -> None:
    assert ev(T.VIDEO_TO_MEANING).evaluate(V2M, OptionAnswer(option_token=token), TOK) is False


def test_video_to_meaning_token_of_another_exercise_is_wrong() -> None:
    other = fake_tokenize("S1", "M1-N1-L1-02")
    answer = OptionAnswer(option_token=other("w", "hola"))
    assert ev(T.VIDEO_TO_MEANING).evaluate(V2M, answer, TOK) is False


def test_meaning_to_video_correct_video_token() -> None:
    answer = OptionAnswer(option_token=TOK("v", "adios"))
    assert ev(T.MEANING_TO_VIDEO).evaluate(M2V, answer, TOK) is True


@pytest.mark.parametrize("token", [TOK("v", "hola"), TOK("w", "adios"), "adios", ""])
def test_meaning_to_video_wrong_tokens(token: str) -> None:
    assert ev(T.MEANING_TO_VIDEO).evaluate(M2V, OptionAnswer(option_token=token), TOK) is False


def test_spelling_correct_word_token() -> None:
    answer = OptionAnswer(option_token=TOK("s", "CADA"))
    assert ev(T.SPELLING).evaluate(SPELLING, answer, TOK) is True


@pytest.mark.parametrize("token", [TOK("s", "BEBE"), TOK("w", "CADA"), TOK("v", "CADA"), "CADA"])
def test_spelling_wrong_tokens(token: str) -> None:
    assert ev(T.SPELLING).evaluate(SPELLING, OptionAnswer(option_token=token), TOK) is False


def _conv_choices(*ids: str) -> ConversationAnswer:
    return ConversationAnswer(choices=[TOK("v", i) for i in ids])


def test_conversation_all_turns_correct() -> None:
    answer = _conv_choices("hola", "buenos-dias")
    assert ev(T.CONVERSATION).evaluate(CONVERSATION, answer, TOK) is True


@pytest.mark.parametrize(
    "answer",
    [
        _conv_choices("hola", "adios"),  # segundo turno mal
        _conv_choices("adios", "buenos-dias"),  # primer turno mal
        _conv_choices("buenos-dias", "hola"),  # orden invertido
        _conv_choices("hola"),  # faltan turnos
        _conv_choices("hola", "buenos-dias", "adios"),  # sobran
        ConversationAnswer(choices=[]),
        ConversationAnswer(choices=[TOK("w", "hola"), TOK("w", "buenos-dias")]),  # lado
    ],
)
def test_conversation_wrong(answer: ConversationAnswer) -> None:
    assert ev(T.CONVERSATION).evaluate(CONVERSATION, answer, TOK) is False


def _pair(video: str, word: str) -> MatchAttempt:
    return MatchAttempt(video_token=TOK("v", video), word_token=TOK("w", word))


def _mm(*attempts: MatchAttempt) -> MemoryMatchAnswer:
    return MemoryMatchAnswer(attempts=list(attempts))


@pytest.mark.parametrize(
    ("answer", "expected"),
    [
        pytest.param(
            _mm(_pair("hola", "hola"), _pair("adios", "adios"), _pair("gracias", "gracias")),
            True,
            id="perfecto",
        ),
        pytest.param(
            _mm(_pair("gracias", "gracias"), _pair("hola", "hola"), _pair("adios", "adios")),
            True,
            id="cualquier-orden",
        ),
        pytest.param(
            _mm(
                _pair("hola", "adios"),
                _pair("adios", "gracias"),
                _pair("gracias", "hola"),
                _pair("hola", "hola"),
                _pair("adios", "adios"),
                _pair("gracias", "gracias"),
            ),
            True,
            id="errores-igual-a-pares",
        ),
        pytest.param(
            _mm(
                _pair("hola", "adios"),
                _pair("adios", "gracias"),
                _pair("gracias", "hola"),
                _pair("hola", "gracias"),
                _pair("hola", "hola"),
                _pair("adios", "adios"),
                _pair("gracias", "gracias"),
            ),
            False,
            id="errores-mas-que-pares",
        ),
        pytest.param(
            _mm(
                _pair("hola", "hola"),
                _pair("hola", "hola"),
                _pair("hola", "hola"),
                _pair("hola", "hola"),
                _pair("hola", "hola"),
                _pair("adios", "adios"),
                _pair("gracias", "gracias"),
            ),
            True,
            id="repetir-par-emparejado-no-es-error",
        ),
        pytest.param(
            _mm(_pair("hola", "hola"), _pair("hola", "hola"), _pair("adios", "adios")),
            False,
            id="repetir-par-no-suma",
        ),
        pytest.param(_mm(_pair("hola", "hola"), _pair("adios", "adios")), False, id="falta-par"),
        pytest.param(_mm(), False, id="sin-intentos"),
        pytest.param(
            _mm(
                MatchAttempt(video_token=TOK("w", "hola"), word_token=TOK("v", "hola")),
                MatchAttempt(video_token=TOK("w", "adios"), word_token=TOK("v", "adios")),
                MatchAttempt(video_token=TOK("w", "gracias"), word_token=TOK("v", "gracias")),
            ),
            False,
            id="lados-invertidos-no-emparejan",
        ),
        pytest.param(
            _mm(
                _pair("yo", "yo"),  # seña fuera del ejercicio: error
                MatchAttempt(video_token="basura", word_token="basura"),
                _pair("hola", "hola"),
                _pair("adios", "adios"),
                _pair("gracias", "gracias"),
            ),
            True,
            id="intentos-invalidos-cuentan-como-error",
        ),
        pytest.param(
            _mm(
                _pair("yo", "yo"),
                MatchAttempt(video_token="basura", word_token="basura"),
                _pair("tu", "tu"),
                _pair("nombre", "nombre"),
                _pair("hola", "hola"),
                _pair("adios", "adios"),
                _pair("gracias", "gracias"),
            ),
            False,
            id="cuatro-intentos-invalidos",
        ),
    ],
)
def test_memory_match_evaluation(answer: MemoryMatchAnswer, expected: bool) -> None:
    assert ev(T.MEMORY_MATCH).evaluate(MEMORY, answer, TOK) is expected


def _wrong_payloads(exercise_type: ExerciseType) -> Iterator[ExercisePayload]:
    for other_type, payload in PAYLOADS.items():
        if other_type is not exercise_type:
            yield payload


@pytest.mark.parametrize("exercise_type", list(ExerciseType))
def test_evaluate_rejects_payload_of_another_type(exercise_type: ExerciseType) -> None:
    evaluator = ev(exercise_type)
    answer = SAMPLE_ANSWERS[ANSWER_MODELS[exercise_type]]
    for payload in _wrong_payloads(exercise_type):
        with pytest.raises(TypeError):
            evaluator.evaluate(payload, answer, TOK)


@pytest.mark.parametrize("exercise_type", list(ExerciseType))
def test_evaluate_rejects_answer_of_another_type(exercise_type: ExerciseType) -> None:
    evaluator = ev(exercise_type)
    for model, answer in SAMPLE_ANSWERS.items():
        if model is ANSWER_MODELS[exercise_type]:
            continue
        with pytest.raises(TypeError):
            evaluator.evaluate(PAYLOADS[exercise_type], answer, TOK)


@pytest.mark.parametrize("exercise_type", list(ExerciseType))
def test_to_public_and_feedback_reject_payload_of_another_type(
    exercise_type: ExerciseType,
) -> None:
    evaluator = ev(exercise_type)
    for payload in _wrong_payloads(exercise_type):
        with pytest.raises(TypeError):
            evaluator.to_public(payload, CATALOG, TOK)
        with pytest.raises(TypeError):
            evaluator.feedback(payload, CATALOG, TOK)


# ---------- to_public -------------------------------------------------------------------------


def test_public_observe() -> None:
    public = ev(T.OBSERVE).to_public(OBSERVE, CATALOG, TOK)
    sign = CATALOG["gracias"]
    assert public == PublicObserve(
        video=sign.video, word=sign.word, how_to=sign.how_to, usage_example=sign.usage_example
    )


def test_public_produce_keeps_camera_label() -> None:
    public = ev(T.PRODUCE).to_public(PRODUCE, CATALOG, TOK)
    sign = CATALOG["letra-a"]
    assert public == PublicProduce(video=sign.video, word="A", camera_label="letra-a")
    without = ev(T.PRODUCE).to_public(ProducePayload(sign_id="hola"), CATALOG, TOK)
    assert isinstance(without, PublicProduce)
    assert without.camera_label is None
    assert without.word == "Hola"


def test_public_video_to_meaning() -> None:
    public = ev(T.VIDEO_TO_MEANING).to_public(V2M, CATALOG, TOK)
    assert isinstance(public, PublicVideoToMeaning)
    assert public.video == CATALOG["hola"].video
    expected = {WordOption(token=TOK("w", i), word=CATALOG[i].word) for i in V2M.option_ids}
    assert set(public.options) == expected
    assert len(public.options) == 4


def test_public_meaning_to_video() -> None:
    public = ev(T.MEANING_TO_VIDEO).to_public(M2V, CATALOG, TOK)
    assert isinstance(public, PublicMeaningToVideo)
    assert public.word == "Adiós"
    expected = {VideoOption(token=TOK("v", i), video=CATALOG[i].video) for i in M2V.option_ids}
    assert set(public.options) == expected
    assert len(public.options) == 4


def test_public_memory_match() -> None:
    public = ev(T.MEMORY_MATCH).to_public(MEMORY, CATALOG, TOK)
    assert isinstance(public, PublicMemoryMatch)
    ids = MEMORY.sign_ids
    assert set(public.video_cards) == {
        VideoOption(token=TOK("v", i), video=CATALOG[i].video) for i in ids
    }
    assert set(public.word_cards) == {
        WordOption(token=TOK("w", i), word=CATALOG[i].word) for i in ids
    }
    assert len(public.video_cards) == len(public.word_cards) == 3


def test_public_conversation() -> None:
    public = ev(T.CONVERSATION).to_public(CONVERSATION, CATALOG, TOK)
    assert isinstance(public, PublicConversation)
    assert len(public.turns) == 2
    for turn, source in zip(public.turns, CONVERSATION.turns, strict=True):
        assert turn.prompt == CATALOG[source.prompt_id].video
        assert set(turn.options) == {
            VideoOption(token=TOK("v", i), video=CATALOG[i].video) for i in source.option_ids
        }


def test_public_spelling() -> None:
    public = ev(T.SPELLING).to_public(SPELLING, CATALOG, TOK)
    assert isinstance(public, PublicSpelling)
    assert public.letters == [CATALOG[i].video for i in SPELLING.letter_ids]  # en orden
    assert set(public.options) == {
        WordOption(token=TOK("s", w), word=w) for w in SPELLING.option_words
    }


def _option_tokens(public: object) -> list[list[str]]:
    if isinstance(public, PublicVideoToMeaning | PublicMeaningToVideo | PublicSpelling):
        return [[o.token for o in public.options]]
    if isinstance(public, PublicConversation):
        return [[o.token for o in turn.options] for turn in public.turns]
    if isinstance(public, PublicMemoryMatch):
        return [[c.token for c in public.video_cards], [c.token for c in public.word_cards]]
    raise AssertionError(f"Tipo sin opciones: {type(public).__name__}")


SHUFFLED_TYPES = [
    T.VIDEO_TO_MEANING,
    T.MEANING_TO_VIDEO,
    T.MEMORY_MATCH,
    T.CONVERSATION,
    T.SPELLING,
]


@pytest.mark.parametrize("exercise_type", SHUFFLED_TYPES)
def test_public_options_are_ordered_by_token(exercise_type: ExerciseType) -> None:
    # D-008: el orden depende de tokens con secreto, no de una semilla que el cliente conoce.
    public = ev(exercise_type).to_public(PAYLOADS[exercise_type], CATALOG, TOK)
    for tokens in _option_tokens(public):
        assert tokens == sorted(tokens)


@pytest.mark.parametrize("exercise_type", SHUFFLED_TYPES)
def test_same_payload_same_public_order(exercise_type: ExerciseType) -> None:
    payload = PAYLOADS[exercise_type]
    first = ev(exercise_type).to_public(payload, CATALOG, TOK)
    assert first == ev(exercise_type).to_public(payload, CATALOG, TOK)


def test_public_seed_does_not_reveal_the_correct_option() -> None:
    """Ataque del revisor: barajar con la semilla pública «sesión:ejercicio» y tomar el índice 0.

    Con opciones ordenadas por token (HMAC con secreto) el ataque no debe acertar siempre, y la
    posición de la correcta en lo público debe variar entre ejercicios.
    """
    content = generate_content(build_modules(), build_signs(), build_conversations())
    hits = total = 0
    positions: set[int] = set()
    for exercise in content.exercises:
        payload = exercise.payload
        if not isinstance(payload, VideoToMeaningPayload | MeaningToVideoPayload):
            continue
        tokenize = fake_tokenize("S-demo", exercise.id)
        public = get_evaluator(exercise.type).to_public(payload, CATALOG, tokenize)
        assert isinstance(public, PublicVideoToMeaning | PublicMeaningToVideo)
        order = list(range(len(payload.option_ids)))
        random.Random(f"S-demo:{exercise.id}").shuffle(order)  # noqa: S311 — simula al atacante
        guessed = public.options[order.index(0)].token
        side = "w" if isinstance(payload, VideoToMeaningPayload) else "v"
        correct = tokenize(side, payload.correct_id)
        hits += guessed == correct
        total += 1
        positions.add([o.token for o in public.options].index(correct))
    assert total > 50
    assert hits < total * 0.6
    assert len(positions) == 4


def test_memory_match_columns_do_not_reveal_the_pairs() -> None:
    content = generate_content(build_modules(), build_signs(), build_conversations())
    same_order = total = 0
    for exercise in content.exercises:
        if not isinstance(exercise.payload, MemoryMatchPayload):
            continue
        tokenize = fake_tokenize("S-demo", exercise.id)
        public = get_evaluator(T.MEMORY_MATCH).to_public(exercise.payload, CATALOG, tokenize)
        assert isinstance(public, PublicMemoryMatch)
        by_video = {tokenize("v", s): s for s in exercise.payload.sign_ids}
        by_word = {tokenize("w", s): s for s in exercise.payload.sign_ids}
        videos = [by_video[c.token] for c in public.video_cards]
        words = [by_word[c.token] for c in public.word_cards]
        same_order += videos == words
        total += 1
    assert total > 0
    assert same_order < total


def test_conversation_prompt_video_is_never_an_option() -> None:
    content = generate_content(build_modules(), build_signs(), build_conversations())
    checked = 0
    for exercise in content.exercises:
        if not isinstance(exercise.payload, ConversationPayload):
            continue
        public = get_evaluator(T.CONVERSATION).to_public(
            exercise.payload, CATALOG, fake_tokenize("S-demo", exercise.id)
        )
        assert isinstance(public, PublicConversation)
        for turn in public.turns:
            assert turn.prompt.src not in {o.video.src for o in turn.options}
            checked += 1
    assert checked > 0


# ---------- feedback --------------------------------------------------------------------------


def test_feedback_video_to_meaning() -> None:
    assert ev(T.VIDEO_TO_MEANING).feedback(V2M, CATALOG, TOK) == CorrectFeedback(
        tokens=(TOK("w", "hola"),), word="Hola"
    )


def test_feedback_meaning_to_video() -> None:
    assert ev(T.MEANING_TO_VIDEO).feedback(M2V, CATALOG, TOK) == CorrectFeedback(
        tokens=(TOK("v", "adios"),), word="Adiós"
    )


def test_feedback_spelling() -> None:
    assert ev(T.SPELLING).feedback(SPELLING, CATALOG, TOK) == CorrectFeedback(
        tokens=(TOK("s", "CADA"),), word="CADA"
    )


def test_feedback_conversation() -> None:
    assert ev(T.CONVERSATION).feedback(CONVERSATION, CATALOG, TOK) == CorrectFeedback(
        tokens=(TOK("v", "hola"), TOK("v", "buenos-dias")), word=None
    )


@pytest.mark.parametrize("exercise_type", [T.OBSERVE, T.PRODUCE, T.MEMORY_MATCH])
def test_feedback_empty_for_non_choice_types(exercise_type: ExerciseType) -> None:
    assert ev(exercise_type).feedback(PAYLOADS[exercise_type], CATALOG, TOK) == CorrectFeedback()


# ---------- PRUEBA OBLIGATORIA (§7.6, D20): el JSON público nunca revela la respuesta --------

FORBIDDEN_KEYS = {"correctId", "signId", "optionIds", "signIds"}
SLUGS = all_slugs()


@cache
def _generated() -> GeneratedContent:
    return generate_content(build_modules(), build_signs(), build_conversations())


def _walk(value: object, path: str = "") -> Iterator[tuple[str, str, object]]:
    """Recorre el JSON y produce (ruta, clave, valor) de cada entrada."""
    if isinstance(value, dict):
        for key, item in value.items():
            yield path, str(key), item
            yield from _walk(item, f"{path}.{key}")
    elif isinstance(value, list):
        for i, item in enumerate(value):
            yield from _walk(item, f"{path}[{i}]")


def _option_values(public: dict[str, object]) -> Iterator[str]:
    """Valores de las opciones: token, word, src y poster de options/cards/letters/prompt."""
    containers: list[object] = []
    for key in ("options", "videoCards", "wordCards", "letters"):
        containers.append(public.get(key, []))
    turns = public.get("turns", [])
    assert isinstance(turns, list)
    for turn in turns:
        assert isinstance(turn, dict)
        containers.append(turn["options"])
        containers.append([turn["prompt"]])
    for container in containers:
        assert isinstance(container, list)
        for option in container:
            assert isinstance(option, dict)
            for key in ("token", "word", "src", "poster"):
                if key in option:
                    yield str(option[key])
            video = option.get("video")
            if isinstance(video, dict):
                yield str(video["src"])
                yield str(video["poster"])


def test_public_json_of_all_generated_exercises_never_reveals_answers() -> None:
    content = _generated()
    assert content.exercises, "el fixture debe generar ejercicios"
    seen_types: set[ExerciseType] = set()
    for exercise in content.exercises:
        tokenize = fake_tokenize("S-demo", exercise.id)
        public = get_evaluator(exercise.type).to_public(exercise.payload, CATALOG, tokenize)
        assert public.type is exercise.type
        seen_types.add(exercise.type)
        data = public.model_dump(mode="json", by_alias=True)
        for path, key, value in _walk(data):
            assert key not in FORBIDDEN_KEYS, f"{exercise.id}: clave {key} en {path}"
            # Etiquetas de los modelos de cámara: solo en PRODUCE, que muestra la palabra (D-026).
            if key not in {"cameraLabel", "gestureLabel"} and isinstance(value, str):
                assert value not in SLUGS, f"{exercise.id}: slug {value!r} en {path}.{key}"
        for value in _option_values(data):
            assert value not in SLUGS, f"{exercise.id}: opción con slug {value!r}"
    assert seen_types == set(ExerciseType)


def test_feedback_tokens_of_generated_exercises_are_public_options_and_correct() -> None:
    """La respuesta marcada por feedback() existe en la vista pública y evaluate() la acepta."""
    for exercise in _generated().exercises:
        if exercise.type not in (
            T.VIDEO_TO_MEANING,
            T.MEANING_TO_VIDEO,
            T.SPELLING,
            T.CONVERSATION,
        ):
            continue
        tokenize = fake_tokenize("S-demo", exercise.id)
        evaluator = get_evaluator(exercise.type)
        public = evaluator.to_public(exercise.payload, CATALOG, tokenize)
        feedback = evaluator.feedback(exercise.payload, CATALOG, tokenize)
        if isinstance(public, PublicConversation):
            assert len(feedback.tokens) == len(public.turns)
            for token, turn in zip(feedback.tokens, public.turns, strict=True):
                assert token in {o.token for o in turn.options}
            answer: BaseModel = ConversationAnswer(choices=list(feedback.tokens))
        else:
            assert isinstance(public, PublicVideoToMeaning | PublicMeaningToVideo | PublicSpelling)
            assert len(feedback.tokens) == 1
            assert feedback.tokens[0] in {o.token for o in public.options}
            answer = OptionAnswer(option_token=feedback.tokens[0])
        assert evaluator.evaluate(exercise.payload, answer, tokenize) is True, exercise.id


def test_public_produce_passes_gesture_label() -> None:
    """Señas con movimiento: el cliente recibe la etiqueta del modelo de gestos (D-026)."""
    payload = ProducePayload(sign_id="letra-a", gesture_label="letra-a")
    public = ev(T.PRODUCE).to_public(payload, CATALOG, TOK)
    assert isinstance(public, PublicProduce)
    assert public.gesture_label == "letra-a"
    assert public.camera_label is None

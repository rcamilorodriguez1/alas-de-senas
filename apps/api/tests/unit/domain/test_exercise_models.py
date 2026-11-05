"""Tarea 1.8 — modelos Pydantic de payloads, respuestas y vistas públicas (§7.6)."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.domain.enums import ExerciseType
from app.domain.exercises.models import (
    SIDE_SPELLING,
    SIDE_VIDEO,
    SIDE_WORD,
    ConversationAnswer,
    ConversationPayload,
    ConversationTurn,
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
    PublicObserve,
    PublicProduce,
    SpellingPayload,
    VideoRef,
    VideoToMeaningPayload,
    dump_payload,
    parse_payload,
)

ALL_PAYLOADS: list[ExercisePayload] = [
    ObservePayload(sign_id="hola"),
    VideoToMeaningPayload(
        sign_id="hola", option_ids=["hola", "adios", "gracias", "yo"], correct_id="hola"
    ),
    MeaningToVideoPayload(
        sign_id="adios", option_ids=["adios", "hola", "gracias", "yo"], correct_id="adios"
    ),
    MemoryMatchPayload(sign_ids=["hola", "adios", "gracias"]),
    ProducePayload(sign_id="letra-a", camera_label="letra-a"),
    ProducePayload(sign_id="hola"),
    ConversationPayload(
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
    ),
    SpellingPayload(
        word="NIÑO",
        letter_ids=["letra-n", "letra-i", "letra-n-tilde", "letra-o"],
        option_words=["NIÑO", "SOL", "LUNA", "OSO"],
    ),
]


def test_side_constants() -> None:
    assert (SIDE_WORD, SIDE_VIDEO, SIDE_SPELLING) == ("w", "v", "s")


# ---------- Payloads: ida y vuelta y discriminador --------------------------------------------


@pytest.mark.parametrize("payload", ALL_PAYLOADS, ids=lambda p: p.type.value)
def test_payload_round_trip_preserves_payload(payload: ExercisePayload) -> None:
    raw = dump_payload(payload)
    assert parse_payload(raw) == payload
    assert type(parse_payload(raw)) is type(payload)


def test_dump_payload_uses_camel_case_and_type() -> None:
    payload = VideoToMeaningPayload(sign_id="hola", option_ids=["hola", "adios"], correct_id="hola")
    assert dump_payload(payload) == {
        "type": "VIDEO_TO_MEANING",
        "signId": "hola",
        "optionIds": ["hola", "adios"],
        "correctId": "hola",
    }


def test_dump_conversation_and_spelling_camel_case() -> None:
    conv = dump_payload(ALL_PAYLOADS[6])
    assert conv["type"] == "CONVERSATION"
    turns = conv["turns"]
    assert isinstance(turns, list)
    assert set(turns[0]) == {"promptId", "optionIds", "correctId"}
    spelling = dump_payload(ALL_PAYLOADS[7])
    assert set(spelling) == {"type", "word", "letterIds", "optionWords"}
    produce = dump_payload(ALL_PAYLOADS[4])
    assert produce == {
        "type": "PRODUCE",
        "signId": "letra-a",
        "cameraLabel": "letra-a",
        "gestureLabel": None,
    }


def test_parse_payload_reads_camel_case_from_db() -> None:
    payload = parse_payload(
        {"type": "MEANING_TO_VIDEO", "signId": "yo", "optionIds": ["yo", "tu"], "correctId": "yo"}
    )
    assert isinstance(payload, MeaningToVideoPayload)
    assert payload.correct_id == "yo"


def test_parse_payload_unknown_type_is_validation_error() -> None:
    with pytest.raises(ValidationError):
        parse_payload({"type": "DRAW_THE_SIGN", "signId": "hola"})


def test_parse_payload_without_type_is_validation_error() -> None:
    with pytest.raises(ValidationError):
        parse_payload({"signId": "hola"})


@pytest.mark.parametrize("raw", [None, "OBSERVE", 3, ["OBSERVE"]])
def test_parse_payload_non_object_is_validation_error(raw: object) -> None:
    with pytest.raises(ValidationError):
        parse_payload(raw)


def test_parse_payload_extra_field_is_validation_error() -> None:
    with pytest.raises(ValidationError):
        parse_payload({"type": "OBSERVE", "signId": "hola", "correctId": "hola"})


def test_parse_payload_corrupt_options_is_validation_error() -> None:
    with pytest.raises(ValidationError):
        parse_payload(
            {
                "type": "VIDEO_TO_MEANING",
                "signId": "hola",
                "optionIds": ["adios", "gracias"],
                "correctId": "hola",
            }
        )


def test_payloads_are_frozen() -> None:
    payload = ObservePayload(sign_id="hola")
    with pytest.raises(ValidationError):
        payload.sign_id = "adios"  # type: ignore[misc]  # se prueba que el modelo es inmutable


# ---------- Validadores de opciones -----------------------------------------------------------


@pytest.mark.parametrize("model", [VideoToMeaningPayload, MeaningToVideoPayload])
def test_choice_payload_rejects_repeated_options(
    model: type[VideoToMeaningPayload] | type[MeaningToVideoPayload],
) -> None:
    with pytest.raises(ValidationError, match="Opciones repetidas"):
        model(sign_id="hola", option_ids=["hola", "adios", "hola"], correct_id="hola")


@pytest.mark.parametrize("model", [VideoToMeaningPayload, MeaningToVideoPayload])
def test_choice_payload_rejects_correct_outside_options(
    model: type[VideoToMeaningPayload] | type[MeaningToVideoPayload],
) -> None:
    with pytest.raises(ValidationError, match="no está entre las opciones"):
        model(sign_id="hola", option_ids=["adios", "gracias"], correct_id="hola")


@pytest.mark.parametrize(
    "options",
    [["hola"], ["hola", "adios", "gracias", "yo", "tu"]],
    ids=["una", "cinco"],
)
def test_choice_payload_requires_two_to_four_options(options: list[str]) -> None:
    with pytest.raises(ValidationError):
        VideoToMeaningPayload(sign_id="hola", option_ids=options, correct_id="hola")


def test_choice_payload_accepts_two_and_four_options() -> None:
    VideoToMeaningPayload(sign_id="hola", option_ids=["hola", "adios"], correct_id="hola")
    VideoToMeaningPayload(
        sign_id="hola", option_ids=["adios", "gracias", "yo", "hola"], correct_id="hola"
    )


def test_conversation_turn_rejects_repeated_options() -> None:
    with pytest.raises(ValidationError, match="Opciones repetidas"):
        ConversationTurn(prompt_id="hola", option_ids=["hola", "hola"], correct_id="hola")


def test_conversation_turn_rejects_correct_outside_options() -> None:
    with pytest.raises(ValidationError, match="no está entre las opciones"):
        ConversationTurn(prompt_id="hola", option_ids=["adios", "gracias"], correct_id="hola")


def test_conversation_turn_option_count_limits() -> None:
    with pytest.raises(ValidationError):
        ConversationTurn(prompt_id="hola", option_ids=["hola"], correct_id="hola")
    with pytest.raises(ValidationError):
        ConversationTurn(
            prompt_id="hola", option_ids=["hola", "a", "b", "c", "d"], correct_id="hola"
        )


def test_conversation_requires_at_least_one_turn() -> None:
    with pytest.raises(ValidationError):
        ConversationPayload(turns=[])


def test_spelling_rejects_repeated_words() -> None:
    with pytest.raises(ValidationError, match="Opciones repetidas"):
        SpellingPayload(
            word="SOL", letter_ids=["letra-s", "letra-o", "letra-l"], option_words=["SOL", "SOL"]
        )


def test_spelling_rejects_word_outside_options() -> None:
    with pytest.raises(ValidationError, match="no está entre las opciones"):
        SpellingPayload(
            word="SOL", letter_ids=["letra-s", "letra-o", "letra-l"], option_words=["OSO", "PAN"]
        )


def test_spelling_requires_letters_and_two_to_four_options() -> None:
    with pytest.raises(ValidationError):
        SpellingPayload(word="SOL", letter_ids=[], option_words=["SOL", "OSO"])
    with pytest.raises(ValidationError):
        SpellingPayload(word="SOL", letter_ids=["letra-s"], option_words=["SOL"])
    with pytest.raises(ValidationError):
        SpellingPayload(
            word="SOL",
            letter_ids=["letra-s"],
            option_words=["SOL", "OSO", "PAN", "NIDO", "VASO"],
        )


@pytest.mark.parametrize("ids", [["hola"], ["a", "b", "c", "d", "e", "f", "g"]])
def test_memory_match_requires_two_to_six_pairs(ids: list[str]) -> None:
    with pytest.raises(ValidationError):
        MemoryMatchPayload(sign_ids=ids)


def test_memory_match_accepts_two_and_six_pairs() -> None:
    MemoryMatchPayload(sign_ids=["a", "b"])
    MemoryMatchPayload(sign_ids=["a", "b", "c", "d", "e", "f"])


# ---------- Respuestas del cliente ------------------------------------------------------------


def test_observe_answer_requires_watched_true() -> None:
    assert ObserveAnswer.model_validate({"watched": True}).watched is True
    with pytest.raises(ValidationError):
        ObserveAnswer.model_validate({"watched": False})


def test_option_answer_accepts_camel_case() -> None:
    assert OptionAnswer.model_validate({"optionToken": "abc123"}).option_token == "abc123"


def test_option_answer_rejects_extra_fields() -> None:
    with pytest.raises(ValidationError):
        OptionAnswer.model_validate({"optionToken": "abc", "correct": True})


def test_memory_match_answer_camel_case() -> None:
    answer = MemoryMatchAnswer.model_validate(
        {"attempts": [{"videoToken": "v1", "wordToken": "w1"}]}
    )
    assert answer.attempts == [MatchAttempt(video_token="v1", word_token="w1")]


def test_produce_answer_limits() -> None:
    ok = ProduceAnswer.model_validate({"method": "camera", "ok": True, "confidence": 0.91})
    assert ok.confidence == pytest.approx(0.91)
    assert ProduceAnswer.model_validate({"method": "self", "ok": False}).confidence is None
    with pytest.raises(ValidationError):
        ProduceAnswer.model_validate({"method": "camera", "ok": True, "confidence": 1.5})
    with pytest.raises(ValidationError):
        ProduceAnswer.model_validate({"method": "camera", "ok": True, "confidence": -0.1})
    with pytest.raises(ValidationError):
        ProduceAnswer.model_validate({"method": "magic", "ok": True})


def test_conversation_answer() -> None:
    assert ConversationAnswer.model_validate({"choices": ["a", "b"]}).choices == ["a", "b"]
    with pytest.raises(ValidationError):
        ConversationAnswer.model_validate({"choices": "a"})


# ---------- Vistas públicas -------------------------------------------------------------------


def test_public_models_dump_in_camel_case() -> None:
    video = VideoRef(src="/media/v/abc.mp4", poster="/media/p/abc.jpg")
    observe = PublicObserve(video=video, word="Hola", how_to=None, usage_example="Hola, Ana.")
    assert observe.model_dump(mode="json", by_alias=True) == {
        "type": "OBSERVE",
        "video": {
            "src": "/media/v/abc.mp4",
            "poster": "/media/p/abc.jpg",
            "placeholder": False,
            "source": "video",
        },
        "word": "Hola",
        "howTo": None,
        "usageExample": "Hola, Ana.",
    }
    produce = PublicProduce(video=video, word="A", camera_label="letra-a")
    assert produce.model_dump(mode="json", by_alias=True)["cameraLabel"] == "letra-a"
    assert produce.type is ExerciseType.PRODUCE

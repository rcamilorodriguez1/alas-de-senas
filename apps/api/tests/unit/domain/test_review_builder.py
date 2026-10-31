"""Tarea 1.12: ejercicios de una sesión de repaso (D23, §8.5, R6.7)."""

from __future__ import annotations

from collections.abc import Sequence

import pytest

from app.domain.content.review_builder import ReviewItem, ReviewSign, build_review_items
from app.domain.enums import ExerciseType
from app.domain.exercises.models import MeaningToVideoPayload, VideoToMeaningPayload
from tests.unit.domain.content_fixture import NODE_SIGN_IDS, build_review_signs

T = ExerciseType
ALL_REVIEW_SIGNS = build_review_signs()
BY_ID = {s.id: s for s in ALL_REVIEW_SIGNS}


def signs(*ids: str) -> list[ReviewSign]:
    return [BY_ID[i] for i in ids]


def rs(sign_id: str, word: str, category: str, node_id: str | None, node_order: int) -> ReviewSign:
    return ReviewSign(
        id=sign_id, word=word, category=category, node_id=node_id, node_order=node_order
    )


SEEN_M1_N1 = signs(*NODE_SIGN_IDS["M1-N1"])
SEEN_WIDE = signs(*NODE_SIGN_IDS["M1-N1"], *NODE_SIGN_IDS["M1-N2"], *NODE_SIGN_IDS["M2-N1"])


def assert_item_rules(item: ReviewItem, seen: Sequence[ReviewSign]) -> None:
    payload = item.payload
    assert isinstance(payload, VideoToMeaningPayload | MeaningToVideoPayload)
    assert payload.type is item.type
    assert payload.sign_id == payload.correct_id == item.sign_id
    assert payload.option_ids[0] == item.sign_id
    distractors = payload.option_ids[1:]
    assert 1 <= len(distractors) <= 3
    assert item.sign_id not in distractors
    assert len(set(distractors)) == len(distractors)
    seen_by_id = {s.id: s for s in seen}
    assert set(distractors) <= set(seen_by_id), "los distractores salen solo de señas vistas"
    words = [seen_by_id[i].word for i in payload.option_ids]
    assert len(set(words)) == len(words)


def _options(item: ReviewItem) -> list[str]:
    payload = item.payload
    assert isinstance(payload, VideoToMeaningPayload | MeaningToVideoPayload)
    return payload.option_ids


def _distractors(item: ReviewItem) -> list[str]:
    return _options(item)[1:]


def test_one_item_per_due_sign_in_given_order() -> None:
    due = ["gracias", "hola", "yo", "mama", "adios"]
    items = build_review_items(due, SEEN_WIDE, "rev-1")
    assert [i.sign_id for i in items] == due
    assert [i.id for i in items] == ["R-01", "R-02", "R-03", "R-04", "R-05"]


def test_types_alternate_starting_with_video_to_meaning() -> None:
    due = ["gracias", "hola", "yo", "mama", "adios"]
    items = build_review_items(due, SEEN_WIDE, "rev-1")
    assert [i.type for i in items] == [
        T.VIDEO_TO_MEANING,
        T.MEANING_TO_VIDEO,
        T.VIDEO_TO_MEANING,
        T.MEANING_TO_VIDEO,
        T.VIDEO_TO_MEANING,
    ]
    assert isinstance(items[0].payload, VideoToMeaningPayload)
    assert isinstance(items[1].payload, MeaningToVideoPayload)


def test_ids_have_two_digits_beyond_nine() -> None:
    due = list(NODE_SIGN_IDS["M1-N1"]) + list(NODE_SIGN_IDS["M1-N2"])[:3]
    items = build_review_items(due, SEEN_WIDE, "rev-1")
    assert items[8].id == "R-09"
    assert items[9].id == "R-10"
    assert items[11].id == "R-12"


def test_items_follow_option_rules() -> None:
    due = ["gracias", "hola", "yo", "mama", "adios", "abuelo", "perdon"]
    for item in build_review_items(due, SEEN_WIDE, "rev-2"):
        assert_item_rules(item, SEEN_WIDE)
        assert len(_options(item)) == 4


def test_empty_due_list_gives_no_items() -> None:
    assert build_review_items([], SEEN_WIDE, "rev-1") == []


def test_due_sign_not_seen_raises_value_error() -> None:
    with pytest.raises(ValueError):
        build_review_items(["hola", "numero-1"], SEEN_M1_N1, "rev-1")


# ---------- Prioridad: mismo nodo → misma categoría → resto de las vistas ---------------------

PRIORITY_SEEN = [
    rs("gracias", "Gracias", "cortesia", "M1-N1", 1),
    rs("hola", "Hola", "saludos", "M1-N1", 1),
    rs("perdon", "Perdón", "cortesia", "M1-N2", 2),
    rs("yo", "Yo", "presentaciones", "M1-N2", 2),
    rs("con-permiso", "Con permiso", "cortesia", None, 0),
    rs("mama", "Mamá", "familia", "M2-N1", 5),
    rs("papa", "Papá", "familia", "M2-N1", 5),
    rs("numero-1", "Uno", "numeros", "M2-N3", 6),
]


def test_same_node_first_then_same_category() -> None:
    # perdon: mismo nodo → yo; misma categoría → gracias, con-permiso (2, completa 3).
    for session in ("a", "b", "c", "d"):
        [item] = build_review_items(["perdon"], PRIORITY_SEEN, session)
        assert set(_distractors(item)) == {"yo", "gracias", "con-permiso"}


def test_same_category_before_the_rest() -> None:
    # gracias: mismo nodo → hola; misma categoría → perdon, con-permiso.
    for session in ("a", "b", "c", "d"):
        [item] = build_review_items(["gracias"], PRIORITY_SEEN, session)
        assert set(_distractors(item)) == {"hola", "perdon", "con-permiso"}


def test_rest_of_seen_fills_after_node_and_category() -> None:
    # mama: mismo nodo → papa; sin misma categoría; el resto completa 2 más.
    for session in ("a", "b", "c", "d"):
        [item] = build_review_items(["mama"], PRIORITY_SEEN, session)
        distractors = _distractors(item)
        assert "papa" in distractors
        assert len(distractors) == 3
        assert set(distractors) <= {s.id for s in PRIORITY_SEEN} - {"mama"}


def test_same_node_signs_are_all_preferred_when_enough() -> None:
    for item in build_review_items(["hola", "adios"], SEEN_WIDE, "rev-3"):
        assert set(_distractors(item)) <= set(NODE_SIGN_IDS["M1-N1"])


def test_never_two_options_with_the_same_word() -> None:
    seen = [
        rs("hola", "Hola", "saludos", "M1-N1", 1),
        rs("hola-2", "Hola", "saludos", "M1-N1", 1),
        rs("adios", "Adiós", "saludos", "M1-N1", 1),
        rs("adios-2", "Adiós", "saludos", "M1-N1", 1),
        rs("gracias", "Gracias", "cortesia", "M1-N1", 1),
        rs("yo", "Yo", "presentaciones", "M1-N2", 2),
    ]
    for session in ("a", "b", "c", "d", "e", "f"):
        [item] = build_review_items(["hola"], seen, session)
        assert_item_rules(item, seen)
        assert "hola-2" not in _distractors(item)
        assert len(_options(item)) == 4


# ---------- Pocas señas vistas: se completa hasta 2 opciones con all_signs --------------------


def test_with_one_seen_distractor_all_signs_are_not_used() -> None:
    seen = signs("hola", "adios")
    [item] = build_review_items(["hola"], seen, "rev-1", all_signs=ALL_REVIEW_SIGNS)
    assert _options(item) == ["hola", "adios"]


def test_with_two_seen_distractors_all_signs_are_not_used() -> None:
    seen = signs("hola", "adios", "gracias")
    [item] = build_review_items(["hola"], seen, "rev-1", all_signs=ALL_REVIEW_SIGNS)
    payload = item.payload
    assert isinstance(payload, VideoToMeaningPayload)
    assert payload.option_ids[0] == "hola"
    assert set(payload.option_ids) == {"hola", "adios", "gracias"}


def test_only_one_seen_sign_completes_to_two_options_with_all_signs() -> None:
    seen = signs("hola")
    pool = [*signs("hola"), rs("hola-2", "Hola", "saludos", "M1-N1", 1), *signs("adios")]
    [item] = build_review_items(["hola"], seen, "rev-1", all_signs=pool)
    payload = item.payload
    assert isinstance(payload, VideoToMeaningPayload)
    assert payload.option_ids == ["hola", "adios"]  # nunca la correcta ni su misma palabra


def test_completion_with_all_signs_reaches_exactly_two_options() -> None:
    seen = signs("hola")
    [item] = build_review_items(["hola"], seen, "rev-1", all_signs=ALL_REVIEW_SIGNS)
    payload = item.payload
    assert isinstance(payload, VideoToMeaningPayload)
    assert len(payload.option_ids) == 2
    assert payload.option_ids[0] == "hola"
    assert payload.option_ids[1] in BY_ID
    assert BY_ID[payload.option_ids[1]].word != "Hola"


# ---------- Determinismo ----------------------------------------------------------------------


def test_same_input_and_session_same_result() -> None:
    due = ["hola", "gracias", "yo", "mama"]
    first = build_review_items(due, SEEN_WIDE, "rev-42")
    second = build_review_items(list(due), list(SEEN_WIDE), "rev-42")
    assert first == second


def test_other_sessions_can_change_the_choice_or_order() -> None:
    due = ["hola", "gracias", "yo", "mama"]
    results = {
        tuple(tuple(_distractors(item)) for item in build_review_items(due, SEEN_WIDE, f"rev-{k}"))
        for k in range(20)
    }
    assert len(results) > 1


def test_result_is_independent_from_other_sessions_calls() -> None:
    """La semilla es `review:{session_id}`: llamar con otra sesión entre medio no cambia nada."""
    due = ["hola", "yo"]
    first = build_review_items(due, SEEN_WIDE, "rev-7")
    build_review_items(due, SEEN_WIDE, "rev-8")
    assert build_review_items(due, SEEN_WIDE, "rev-7") == first

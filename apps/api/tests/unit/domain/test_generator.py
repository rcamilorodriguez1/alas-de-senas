"""Tarea 1.10: generador determinista de lecciones y ejercicios (§6.5, §6.7, R9.8-R9.11)."""

from __future__ import annotations

import math
import os
import subprocess
import sys
from collections import Counter
from collections.abc import Sequence
from dataclasses import replace
from functools import cache
from pathlib import Path

import pytest

from app.domain.content.generator import (
    LESSON_TITLES,
    generate_content,
    generate_exercises,
    split_counts,
    split_word_into_letters,
)
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
from app.domain.exercises.models import (
    ConversationPayload,
    ConversationTurn,
    MeaningToVideoPayload,
    MemoryMatchPayload,
    ObservePayload,
    ProducePayload,
    SpellingPayload,
    VideoToMeaningPayload,
)
from tests.unit.domain.content_fixture import (
    ALPHABET_NODE_IDS,
    DICTIONARY_SIGN_IDS,
    LETTERS_A_M,
    M1_N1_CONV_3,
    M1_N1_CONV_L2,
    M1_N1_CONV_L3_ONLY,
    M1_N2_CONV_3,
    M2_N1_CONV_L2,
    NODE_SIGN_IDS,
    PUBLISHED_NODE_IDS,
    SPELLING_M1_N3,
    SPELLING_M1_N4,
    build_conversations,
    build_modules,
    build_signs,
    conversation,
    letter_sign,
    letter_slug,
    serialize_content,
    turn,
)

T = ExerciseType
EN_DASH = chr(0x2013)
API_DIR = Path(__file__).resolve().parents[3]  # apps/api
REPO_ROOT = API_DIR.parents[1]

SCORED = {
    T.OBSERVE: False,
    T.PRODUCE: False,
    T.VIDEO_TO_MEANING: True,
    T.MEANING_TO_VIDEO: True,
    T.MEMORY_MATCH: True,
    T.CONVERSATION: True,
    T.SPELLING: True,
}
ACTIVITY = {
    T.OBSERVE: 1,
    T.VIDEO_TO_MEANING: 2,
    T.MEANING_TO_VIDEO: 2,
    T.MEMORY_MATCH: 2,
    T.PRODUCE: 3,
    T.CONVERSATION: 4,
    T.SPELLING: 4,
}
CHOICE_TYPES = (T.VIDEO_TO_MEANING, T.MEANING_TO_VIDEO)


@cache
def generated() -> GeneratedContent:
    return generate_content(build_modules(), build_signs(), build_conversations())


def lessons_by_id(content: GeneratedContent) -> dict[str, LessonSpec]:
    return {lesson.id: lesson for lesson in content.lessons}


def exercises_of(content: GeneratedContent, lesson_id: str) -> list[ExerciseSpec]:
    return [e for e in content.exercises if e.lesson_id == lesson_id]


def types_of(exercises: Sequence[ExerciseSpec]) -> list[ExerciseType]:
    return [e.type for e in exercises]


SIGNS = {s.id: s for s in build_signs()}


# ---------- split_counts ----------------------------------------------------------------------


@pytest.mark.parametrize(
    ("kind", "n", "expected"),
    [
        (NodeKind.STANDARD, 9, (3, 3, 3)),
        (NodeKind.STANDARD, 8, (3, 3, 2)),
        (NodeKind.STANDARD, 7, (3, 3, 1)),
        (NodeKind.STANDARD, 6, (2, 3, 1)),
        (NodeKind.STANDARD, 5, (2, 2, 1)),
        (NodeKind.STANDARD, 4, (2, 1, 1)),
        (NodeKind.NUMBERS, 10, (3, 3, 4)),
        (NodeKind.NUMBERS, 5, (2, 2, 1)),
        (NodeKind.ALPHABET, 12, (4, 4, 4)),
        (NodeKind.ALPHABET, 13, (5, 4, 4)),
        (NodeKind.ALPHABET, 14, (5, 5, 4)),
        (NodeKind.ALPHABET, 15, (5, 5, 5)),
        (NodeKind.ALPHABET, 16, (6, 5, 5)),
    ],
)
def test_split_counts(kind: NodeKind, n: int, expected: tuple[int, int, int]) -> None:
    assert split_counts(kind, n) == expected


@pytest.mark.parametrize("kind", list(NodeKind))
@pytest.mark.parametrize("n", range(4, 17))
def test_split_counts_always_sum_n_and_l3_not_empty(kind: NodeKind, n: int) -> None:
    a, b, c = split_counts(kind, n)
    assert a + b + c == n
    assert a >= 1 and b >= 1 and c >= 1


@pytest.mark.parametrize("n", range(12, 17))
def test_split_counts_alphabet_formula(n: int) -> None:
    a = math.ceil(n / 3)
    b = math.ceil((n - a) / 2)
    assert split_counts(NodeKind.ALPHABET, n) == (a, b, n - a - b)


# ---------- split_word_into_letters -----------------------------------------------------------

BASE_LETTERS = {c: letter_slug(c) for c in (*LETTERS_A_M, "N", "Ñ", *"OPQRSTUVWXYZ")}
WITH_DIGRAPHS = {**BASE_LETTERS, "CH": "letra-ch", "LL": "letra-ll", "RR": "letra-rr"}


def test_split_word_llave_with_ll() -> None:
    assert split_word_into_letters("LLAVE", WITH_DIGRAPHS) == [
        "letra-ll",
        "letra-a",
        "letra-v",
        "letra-e",
    ]


def test_split_word_llave_without_ll() -> None:
    assert split_word_into_letters("LLAVE", BASE_LETTERS) == [
        "letra-l",
        "letra-l",
        "letra-a",
        "letra-v",
        "letra-e",
    ]


def test_split_word_nino_uses_n_tilde() -> None:
    assert split_word_into_letters("NIÑO", BASE_LETTERS) == [
        "letra-n",
        "letra-i",
        "letra-n-tilde",
        "letra-o",
    ]


@pytest.mark.parametrize(
    ("word", "expected"),
    [
        ("CALLE", ["letra-c", "letra-a", "letra-ll", "letra-e"]),
        ("CHAPA", ["letra-ch", "letra-a", "letra-p", "letra-a"]),
        ("PERRO", ["letra-p", "letra-e", "letra-rr", "letra-o"]),
        ("CADA", ["letra-c", "letra-a", "letra-d", "letra-a"]),
        ("A", ["letra-a"]),
    ],
)
def test_split_word_longest_match_first(word: str, expected: list[str]) -> None:
    assert split_word_into_letters(word, WITH_DIGRAPHS) == expected


@pytest.mark.parametrize("word", ["LUZ1", "CAFÉ", "HOLA MUNDO", "sol"])
def test_split_word_impossible_raises_value_error(word: str) -> None:
    with pytest.raises(ValueError):
        split_word_into_letters(word, BASE_LETTERS)


def test_split_word_missing_letter_raises_value_error() -> None:
    letters = {"A": "letra-a", "C": "letra-c"}
    with pytest.raises(ValueError):
        split_word_into_letters("CADA", letters)


# ---------- Lecciones -------------------------------------------------------------------------


def test_lessons_only_for_published_nodes_in_order() -> None:
    expected = [f"{node}-L{i}" for node in PUBLISHED_NODE_IDS for i in range(1, 5)]
    assert [lesson.id for lesson in generated().lessons] == expected


def test_lesson_fields() -> None:
    types = [LessonType.LEARN, LessonType.RECOGNIZE, LessonType.PRACTICE, LessonType.CHALLENGE]
    for lesson in generated().lessons:
        order = int(lesson.id.rsplit("-L", 1)[1])
        assert lesson.node_id == lesson.id.rsplit("-L", 1)[0]
        assert lesson.order == order
        assert lesson.type is types[order - 1]
        assert lesson.title == LESSON_TITLES[lesson.type]


def test_lesson_titles() -> None:
    assert dict(LESSON_TITLES) == {
        LessonType.LEARN: "Aprende",
        LessonType.RECOGNIZE: "Reconoce",
        LessonType.PRACTICE: "Practica",
        LessonType.CHALLENGE: "Reto final",
    }


@pytest.mark.parametrize(
    ("node", "l1", "l2", "l3"),
    [
        (
            "M1-N1",
            ("hola", "buenos-dias", "buenas-tardes"),
            ("buenas-noches", "como-estas", "adios"),
            ("gracias", "por-favor", "de-nada"),
        ),
        (
            "M2-N1",
            ("familia", "mama", "papa"),
            ("hermano", "hermana", "hijo"),
            ("abuelo",),
        ),
        (
            "M2-N3",
            ("numero-1", "numero-2", "numero-3"),
            ("numero-4", "numero-5", "numero-6"),
            ("numero-7", "numero-8", "numero-9", "numero-10"),
        ),
        (
            "M1-N3",
            tuple(letter_slug(c) for c in "ABCDE"),
            tuple(letter_slug(c) for c in "FGHI"),
            tuple(letter_slug(c) for c in "JKLM"),
        ),
        (
            "M1-N4",
            ("letra-n", "letra-n-tilde", "letra-o", "letra-p", "letra-q"),
            tuple(letter_slug(c) for c in "RSTUV"),
            tuple(letter_slug(c) for c in "WXYZ"),
        ),
    ],
)
def test_lesson_sign_split(
    node: str, l1: tuple[str, ...], l2: tuple[str, ...], l3: tuple[str, ...]
) -> None:
    lessons = lessons_by_id(generated())
    assert lessons[f"{node}-L1"].sign_ids == l1
    assert lessons[f"{node}-L2"].sign_ids == l2
    assert lessons[f"{node}-L3"].sign_ids == l3
    assert lessons[f"{node}-L4"].sign_ids == NODE_SIGN_IDS[node]


def test_alphabet_split_by_position_supports_digraphs() -> None:
    """Con CH y LL, M1-N3 tiene 15 letras → 5·5·5 por posición (no por letra)."""
    order = ["A", "B", "C", "CH", "D", "E", "F", "G", "H", "I", "J", "K", "L", "LL", "M"]
    signs = [s for s in build_signs() if s.node_id != "M1-N3"]
    signs += [letter_sign(c, "M1-N3", i) for i, c in enumerate(order, start=1)]
    content = generate_content(build_modules(), signs, build_conversations())
    lessons = lessons_by_id(content)
    slugs = [letter_slug(c) for c in order]
    assert lessons["M1-N3-L1"].sign_ids == tuple(slugs[0:5])
    assert lessons["M1-N3-L2"].sign_ids == tuple(slugs[5:10])
    assert lessons["M1-N3-L3"].sign_ids == tuple(slugs[10:15])
    assert "letra-ch" in lessons["M1-N3-L1"].sign_ids
    assert "letra-ll" in lessons["M1-N3-L3"].sign_ids


def test_unpublished_module_generates_nothing() -> None:
    extra = SignSpec(id="pregunta", word="Pregunta", category="saludos", node_id="M4-N1", order=1)
    signs = (*build_signs(), extra)
    content = generate_content(build_modules(), signs, build_conversations())
    assert not [lesson for lesson in content.lessons if lesson.node_id == "M4-N1"]
    assert not [e for e in content.exercises if e.lesson_id.startswith("M4-")]
    assert "pregunta" not in serialize_content(content)


def test_dictionary_signs_never_used() -> None:
    dumped = serialize_content(generated())
    for slug in DICTIONARY_SIGN_IDS:
        assert f'"{slug}"' not in dumped


def test_input_order_does_not_change_structure() -> None:
    """Módulos, nodos y señas se ordenan por `order`, no por su posición en la entrada."""
    modules = [replace(m, nodes=tuple(reversed(m.nodes))) for m in reversed(build_modules())]
    signs = list(reversed(build_signs()))
    content = generate_content(modules, signs, build_conversations())
    assert content.lessons == generated().lessons
    shape = [(e.id, e.type, e.sign_id, e.activity, e.scored) for e in content.exercises]
    expected = [(e.id, e.type, e.sign_id, e.activity, e.scored) for e in generated().exercises]
    assert shape == expected


# ---------- Ejercicios: estructura común ------------------------------------------------------


def test_exercises_follow_lesson_order_with_sequential_ids() -> None:
    content = generated()
    lesson_ids = [lesson.id for lesson in content.lessons]
    seen_lessons = [e.lesson_id for e in content.exercises]
    assert sorted(set(seen_lessons), key=lesson_ids.index) == lesson_ids
    assert seen_lessons == sorted(seen_lessons, key=lesson_ids.index)
    for lesson_id in lesson_ids:
        exercises = exercises_of(content, lesson_id)
        assert [e.order for e in exercises] == list(range(1, len(exercises) + 1))
        assert [e.id for e in exercises] == [
            f"{lesson_id}-{i:02d}" for i in range(1, len(exercises) + 1)
        ]


def test_exercise_activity_scored_and_type_match_payload() -> None:
    for e in generated().exercises:
        assert e.payload.type is e.type, e.id
        assert e.activity == ACTIVITY[e.type], e.id
        assert e.scored is SCORED[e.type], e.id


def test_exercise_sign_id_matches_payload() -> None:
    for e in generated().exercises:
        payload = e.payload
        if isinstance(payload, MemoryMatchPayload | ConversationPayload | SpellingPayload):
            assert e.sign_id is None, e.id
        else:
            assert e.sign_id == payload.sign_id, e.id
        if isinstance(payload, VideoToMeaningPayload | MeaningToVideoPayload):
            assert payload.correct_id == payload.sign_id, e.id
            assert payload.option_ids[0] == payload.correct_id, e.id


def test_every_lesson_has_at_least_four_scored_exercises() -> None:
    content = generated()
    for lesson in content.lessons:
        scored = [e for e in exercises_of(content, lesson.id) if e.scored]
        assert len(scored) >= 4, f"{lesson.id} tiene {len(scored)} ejercicios con puntaje"


def _choice_for(
    content: GeneratedContent, lesson_id: str, kind: ExerciseType, sign: str
) -> ExerciseSpec:
    found = [
        e
        for e in exercises_of(content, lesson_id)
        if e.type is kind and getattr(e.payload, "correct_id", None) == sign
    ]
    assert len(found) == 1, (lesson_id, kind, sign)
    return found[0]


def _produce_for(content: GeneratedContent, lesson_id: str, sign: str) -> ExerciseSpec:
    found = [
        e
        for e in exercises_of(content, lesson_id)
        if isinstance(e.payload, ProducePayload) and e.payload.sign_id == sign
    ]
    assert len(found) == 1, (lesson_id, sign)
    return found[0]


def _assert_recall_block(
    block: list[ExerciseSpec], kind: ExerciseType, signs: tuple[str, ...]
) -> None:
    """Una pregunta por seña, en orden mezclado y sin empezar por la última que se mostró."""
    assert [e.type for e in block] == [kind] * len(signs)
    asked = [e.sign_id or "" for e in block]
    assert sorted(asked) == sorted(signs)
    if len(signs) > 1:
        assert asked[0] != signs[-1]


# ---------- L1 Aprende ------------------------------------------------------------------------


@pytest.mark.parametrize("node", PUBLISHED_NODE_IDS)
def test_l1_structure(node: str) -> None:
    content = generated()
    lesson = lessons_by_id(content)[f"{node}-L1"]
    exercises = exercises_of(content, lesson.id)
    signs = tuple(lesson.sign_ids)
    n = len(signs)
    assert len(exercises) == 4 * n
    assert types_of(exercises[:n]) == [T.OBSERVE] * n
    assert [e.sign_id for e in exercises[:n]] == list(signs)
    _assert_recall_block(exercises[n : 2 * n], T.VIDEO_TO_MEANING, signs)
    assert types_of(exercises[2 * n : 3 * n]) == [T.PRODUCE] * n
    assert [e.sign_id for e in exercises[2 * n : 3 * n]] == list(signs)
    _assert_recall_block(exercises[3 * n :], T.MEANING_TO_VIDEO, signs)


def test_m1_n1_l1_exact_shape() -> None:
    exercises = exercises_of(generated(), "M1-N1-L1")
    assert len(exercises) == 12
    assert [e.activity for e in exercises] == [1, 1, 1, 2, 2, 2, 3, 3, 3, 2, 2, 2]
    assert exercises[0].payload == ObservePayload(sign_id="hola")
    # «hola» tiene movimiento: sin modelo del alfabeto, pero sí con el de gestos (D-026).
    assert exercises[6].payload == ProducePayload(
        sign_id="hola", camera_label=None, gesture_label="hola"
    )


def test_first_sign_of_content_has_three_distractors() -> None:
    first_choice = _choice_for(generated(), "M1-N1-L1", T.VIDEO_TO_MEANING, "hola")
    payload = first_choice.payload
    assert isinstance(payload, VideoToMeaningPayload)
    assert payload.correct_id == "hola"
    assert len(payload.option_ids) == 4


# ---------- L2 Reconoce -----------------------------------------------------------------------


@pytest.mark.parametrize("node", PUBLISHED_NODE_IDS)
def test_l2_structure(node: str) -> None:
    content = generated()
    lesson = lessons_by_id(content)[f"{node}-L2"]
    exercises = exercises_of(content, lesson.id)
    signs = tuple(lesson.sign_ids)
    n = len(signs)
    assert len(exercises) == 3 * n + 1
    assert [e.sign_id for e in exercises[:n]] == list(signs)
    assert types_of(exercises[:n]) == [T.OBSERVE] * n
    _assert_recall_block(exercises[n : 2 * n], T.VIDEO_TO_MEANING, signs)
    _assert_recall_block(exercises[2 * n : 3 * n], T.MEANING_TO_VIDEO, signs)
    assert exercises[-1].type is (T.SPELLING if node in ALPHABET_NODE_IDS else T.CONVERSATION)


# ---------- L3 Practica -----------------------------------------------------------------------


@pytest.mark.parametrize("node", PUBLISHED_NODE_IDS)
def test_l3_structure(node: str) -> None:
    content = generated()
    lesson = lessons_by_id(content)[f"{node}-L3"]
    exercises = exercises_of(content, lesson.id)
    signs = tuple(lesson.sign_ids)
    n = len(signs)
    assert len(exercises) == 4 * n + 2
    assert [e.sign_id for e in exercises[:n]] == list(signs)
    assert types_of(exercises[:n]) == [T.OBSERVE] * n
    _assert_recall_block(exercises[n : 2 * n], T.VIDEO_TO_MEANING, signs)
    _assert_recall_block(exercises[2 * n : 3 * n], T.MEANING_TO_VIDEO, signs)
    assert types_of(exercises[3 * n : 4 * n]) == [T.PRODUCE] * n
    assert [e.sign_id for e in exercises[3 * n : 4 * n]] == list(signs)
    assert exercises[-2].type is T.MEMORY_MATCH
    assert exercises[-1].type is (T.SPELLING if node in ALPHABET_NODE_IDS else T.CONVERSATION)


# ---------- L4 Reto final ---------------------------------------------------------------------


@pytest.mark.parametrize("node", PUBLISHED_NODE_IDS)
def test_l4_structure(node: str) -> None:
    content = generated()
    lesson = lessons_by_id(content)[f"{node}-L4"]
    exercises = exercises_of(content, lesson.id)
    n = len(NODE_SIGN_IDS[node])
    q = min(10, max(8, 2 * n))
    expected = [T.VIDEO_TO_MEANING if i % 2 == 0 else T.MEANING_TO_VIDEO for i in range(q)]
    expected.append(T.MEMORY_MATCH)
    expected.append(T.SPELLING if node in ALPHABET_NODE_IDS else T.CONVERSATION)
    assert types_of(exercises) == expected


@pytest.mark.parametrize("node", PUBLISHED_NODE_IDS)
def test_l4_questions_cycle_over_a_shuffled_copy_of_the_node(node: str) -> None:
    exercises = exercises_of(generated(), f"{node}-L4")
    node_signs = NODE_SIGN_IDS[node]
    n = len(node_signs)
    questions = [e for e in exercises if e.type in CHOICE_TYPES]
    used = [e.sign_id for e in questions]
    first_round = used[: min(n, len(used))]
    assert len(set(first_round)) == len(first_round)  # sin repetir hasta agotar el nodo
    assert set(first_round) <= set(node_signs)
    for i, sign in enumerate(used):
        assert sign == used[i % n]  # recorre en ciclo


def test_l4_questions_are_shuffled_not_in_node_order() -> None:
    nodes_in_order = 0
    for node in PUBLISHED_NODE_IDS:
        questions = [
            e.sign_id for e in exercises_of(generated(), f"{node}-L4") if e.type in CHOICE_TYPES
        ]
        n = len(NODE_SIGN_IDS[node])
        if tuple(questions[: min(n, 10)]) == NODE_SIGN_IDS[node][: min(n, 10)]:
            nodes_in_order += 1
    assert nodes_in_order < len(PUBLISHED_NODE_IDS)


# ---------- MEMORY_MATCH ----------------------------------------------------------------------


@pytest.mark.parametrize("lesson_suffix", ["L3", "L4"])
@pytest.mark.parametrize("node", PUBLISHED_NODE_IDS)
def test_memory_match_pairs(node: str, lesson_suffix: str) -> None:
    exercises = exercises_of(generated(), f"{node}-{lesson_suffix}")
    matches = [e for e in exercises if e.type is T.MEMORY_MATCH]
    assert len(matches) == 1
    payload = matches[0].payload
    assert isinstance(payload, MemoryMatchPayload)
    node_signs = NODE_SIGN_IDS[node]
    assert len(payload.sign_ids) == min(6, len(node_signs))
    assert 2 <= len(payload.sign_ids) <= 6
    assert len(set(payload.sign_ids)) == len(payload.sign_ids)
    assert set(payload.sign_ids) <= set(node_signs)


def test_memory_match_chooses_six_with_rng_not_the_first_six() -> None:
    picks = []
    for node in PUBLISHED_NODE_IDS:
        for suffix in ("L3", "L4"):
            [mm] = [
                e for e in exercises_of(generated(), f"{node}-{suffix}") if e.type is T.MEMORY_MATCH
            ]
            assert isinstance(mm.payload, MemoryMatchPayload)
            picks.append(set(mm.payload.sign_ids) == set(NODE_SIGN_IDS[node][:6]))
    assert not all(picks)


# ---------- Distractores ----------------------------------------------------------------------


def _node_sequence(modules: Sequence[ModuleSpec]) -> list[str]:
    ordered: list[str] = []
    for module in sorted(modules, key=lambda m: m.order):
        if module.published:
            ordered += [n.id for n in sorted(module.nodes, key=lambda n: n.order)]
    return ordered


def assert_distractors_follow_priority(
    content: GeneratedContent, modules: Sequence[ModuleSpec], signs: Sequence[SignSpec]
) -> None:
    by_id = {s.id: s for s in signs}
    published_nodes = _node_sequence(modules)
    lessons = lessons_by_id(content)
    checked = 0
    for e in content.exercises:
        payload = e.payload
        if not isinstance(payload, VideoToMeaningPayload | MeaningToVideoPayload):
            continue
        checked += 1
        lesson = lessons[e.lesson_id]
        correct = by_id[payload.correct_id]
        distractors = payload.option_ids[1:]
        assert payload.option_ids[0] == correct.id
        assert len(payload.option_ids) == 4, e.id
        assert correct.id not in distractors
        assert len(set(distractors)) == len(distractors)
        words = [by_id[i].word for i in payload.option_ids]
        assert len(set(words)) == len(words), f"{e.id}: palabras repetidas {words}"

        node_index = published_nodes.index(lesson.node_id)
        tiers = [
            set(lesson.sign_ids),
            {s.id for s in signs if s.node_id == lesson.node_id},
            {
                s.id
                for s in signs
                if s.node_id in published_nodes and s.category == correct.category
            },
            {s.id for s in signs if s.node_id in published_nodes[:node_index]},
        ]
        cumulative: set[str] = set()
        for level, tier in enumerate(tiers, start=1):
            cumulative |= tier
            eligible_words = {by_id[i].word for i in cumulative} - {correct.word}
            taken = [d for d in distractors if d in cumulative]
            assert len(taken) == min(3, len(eligible_words)), (
                f"{e.id}: el nivel {level} de distractores no se agotó antes del siguiente"
            )
        assert set(distractors) <= cumulative, f"{e.id}: distractor fuera de los niveles"
    assert checked > 0


def test_distractors_priority_and_rules_on_fixture() -> None:
    assert_distractors_follow_priority(generated(), build_modules(), build_signs())


def test_m1_n1_l1_first_question_uses_lesson_then_node() -> None:
    payload = _choice_for(generated(), "M1-N1-L1", T.VIDEO_TO_MEANING, "hola").payload
    assert isinstance(payload, VideoToMeaningPayload)
    distractors = set(payload.option_ids[1:])
    assert {"buenos-dias", "buenas-tardes"} <= distractors
    assert distractors <= set(NODE_SIGN_IDS["M1-N1"])


# Contenido mínimo con palabras repetidas y un módulo no publicado de la misma categoría.
MINI_MODULES = (
    ModuleSpec(
        id="X1",
        order=1,
        title="Entorno",
        published=True,
        nodes=(
            NodeSpec(id="X1-N2", order=2, title="Lugares", kind=NodeKind.STANDARD),
            NodeSpec(id="X1-N1", order=1, title="Alimentos", kind=NodeKind.STANDARD),
        ),
    ),
    ModuleSpec(
        id="X2",
        order=2,
        title="Oculto",
        published=False,
        nodes=(NodeSpec(id="X2-N1", order=1, title="Más lugares", kind=NodeKind.STANDARD),),
    ),
)


def _mini_signs() -> tuple[SignSpec, ...]:
    rows = [
        ("agua", "Agua", "alimentos", "X1-N1"),
        ("pan", "Pan", "alimentos", "X1-N1"),
        ("arroz", "Arroz", "alimentos", "X1-N1"),
        ("fruta", "Fruta", "alimentos", "X1-N1"),
        ("carne", "Carne", "alimentos", "X1-N1"),
        ("casa", "Casa", "lugares", "X1-N2"),
        ("casa-2", "Casa", "lugares", "X1-N2"),
        ("parque", "Parque", "lugares", "X1-N2"),
        ("tienda", "Tienda", "lugares", "X1-N2"),
        ("bano", "Baño", "lugares", "X1-N2"),
        ("hospital", "Hospital", "lugares", "X2-N1"),
        ("colegio", "Colegio", "lugares", "X2-N1"),
    ]
    counters: Counter[str] = Counter()
    signs = []
    for slug, word, category, node in rows:
        counters[node] += 1
        signs.append(
            SignSpec(id=slug, word=word, category=category, node_id=node, order=counters[node])
        )
    return tuple(signs)


def _mini_conversations() -> dict[str, NodeConversations]:
    # Ningún estímulo aparece entre sus opciones (D-008).
    return {
        "X1-N1": NodeConversations(
            conversations=(
                conversation(
                    turn("agua", "pan", "arroz", "fruta"), turn("fruta", "agua", "pan", "arroz")
                ),
                conversation(
                    turn("agua", "pan", "arroz", "carne"),
                    turn("carne", "fruta", "pan", "agua"),
                    turn("pan", "agua", "arroz", "fruta"),
                ),
            )
        ),
        "X1-N2": NodeConversations(
            conversations=(
                conversation(
                    turn("casa", "parque", "tienda", "agua"), turn("tienda", "casa", "agua", "pan")
                ),
                conversation(
                    turn("casa", "parque", "tienda", "agua"),
                    turn("bano", "casa", "agua", "pan"),
                    turn("parque", "tienda", "carne", "fruta"),
                ),
            )
        ),
    }


def test_distractors_never_repeat_words_nor_use_unpublished_signs() -> None:
    signs = _mini_signs()
    content = generate_content(MINI_MODULES, signs, _mini_conversations())
    assert [lesson.node_id for lesson in content.lessons] == ["X1-N1"] * 4 + ["X1-N2"] * 4
    assert_distractors_follow_priority(content, MINI_MODULES, signs)
    dumped = serialize_content(content)
    assert '"hospital"' not in dumped
    assert '"colegio"' not in dumped


def test_distractor_with_duplicate_word_falls_back_to_previous_nodes() -> None:
    content = generate_content(MINI_MODULES, _mini_signs(), _mini_conversations())
    first = _choice_for(content, "X1-N2-L1", T.VIDEO_TO_MEANING, "casa").payload
    assert isinstance(first, VideoToMeaningPayload)
    assert first.correct_id == "casa"
    distractors = first.option_ids[1:]
    assert "casa-2" not in distractors
    assert len(distractors) == 3
    assert {"parque", "tienda", "bano"} & set(distractors)
    assert set(distractors) <= {
        "parque",
        "tienda",
        "bano",
        "agua",
        "pan",
        "arroz",
        "fruta",
        "carne",
    }


# ---------- Conversaciones --------------------------------------------------------------------


def _payload_of_conversation(spec: ConversationSpec) -> ConversationPayload:
    return ConversationPayload(
        turns=[
            ConversationTurn(
                prompt_id=t.prompt, option_ids=[t.answer, *t.distractors], correct_id=t.answer
            )
            for t in spec.turns
        ]
    )


def _last(content: GeneratedContent, lesson_id: str) -> ExerciseSpec:
    return exercises_of(content, lesson_id)[-1]


def test_l2_uses_first_conversation_with_only_l1_l2_or_previous_signs() -> None:
    last = _last(generated(), "M1-N1-L2")
    assert last.type is T.CONVERSATION
    assert last.payload == _payload_of_conversation(M1_N1_CONV_L2)


def test_l3_uses_first_two_turn_conversation_allowed_in_l3() -> None:
    last = _last(generated(), "M1-N1-L3")
    assert last.type is T.CONVERSATION
    assert last.payload == _payload_of_conversation(M1_N1_CONV_L3_ONLY)


def test_l4_uses_first_three_turn_conversation() -> None:
    assert _last(generated(), "M1-N1-L4").payload == _payload_of_conversation(M1_N1_CONV_3)
    assert _last(generated(), "M1-N2-L4").payload == _payload_of_conversation(M1_N2_CONV_3)


def test_conversation_may_use_previous_nodes() -> None:
    assert _last(generated(), "M2-N1-L2").payload == _payload_of_conversation(M2_N1_CONV_L2)


def test_conversation_payload_shape() -> None:
    for e in generated().exercises:
        if isinstance(e.payload, ConversationPayload):
            expected_turns = 3 if e.lesson_id.endswith("-L4") else 2
            assert len(e.payload.turns) == expected_turns, e.id
            for t in e.payload.turns:
                assert t.option_ids[0] == t.correct_id


def _conversations_with(node: str, value: NodeConversations) -> ConversationsByNode:
    return {**build_conversations(), node: value}


def test_l2_without_valid_conversation_raises_exact_message() -> None:
    # La única conversación de 2 turnos usa «si» (L3 de M1-N2).
    conversations = _conversations_with(
        "M1-N2",
        NodeConversations(
            conversations=(
                conversation(
                    turn("hola", "mucho-gusto", "adios", "tu"), turn("sordo", "si", "no", "yo")
                ),
                M1_N2_CONV_3,
            )
        ),
    )
    with pytest.raises(GenerationError) as info:
        generate_content(build_modules(), build_signs(), conversations)
    assert str(info.value) == (
        f"M1-N2 necesita una conversación que use solo señas de L1{EN_DASH}L2"
        " o de nodos anteriores."
    )


def test_missing_three_turn_conversation_raises() -> None:
    conversations = _conversations_with(
        "M1-N1", NodeConversations(conversations=(M1_N1_CONV_L3_ONLY, M1_N1_CONV_L2))
    )
    with pytest.raises(GenerationError):
        generate_content(build_modules(), build_signs(), conversations)


def test_standard_node_without_conversations_raises() -> None:
    conversations = {k: v for k, v in build_conversations().items() if k != "M2-N1"}
    with pytest.raises(GenerationError):
        generate_content(build_modules(), build_signs(), conversations)


def test_conversation_with_unlearned_sign_is_not_used_in_l2() -> None:
    """Una conversación con una seña de un nodo posterior no es válida: se usa la siguiente."""
    conversations = _conversations_with(
        "M1-N1",
        NodeConversations(
            conversations=(
                conversation(
                    turn("hola", "hola", "adios", "yo"), turn("hola", "hola", "adios", "tu")
                ),
                M1_N1_CONV_L2,
                M1_N1_CONV_3,
            )
        ),
    )
    content = generate_content(build_modules(), build_signs(), conversations)
    assert _last(content, "M1-N1-L2").payload == _payload_of_conversation(M1_N1_CONV_L2)


# ---------- Deletreo (ALPHABET) ---------------------------------------------------------------


def _spelling(content: GeneratedContent, lesson_id: str) -> SpellingPayload:
    last = _last(content, lesson_id)
    assert last.type is T.SPELLING
    assert isinstance(last.payload, SpellingPayload)
    return last.payload


@pytest.mark.parametrize(
    ("lesson_id", "word", "letters"),
    [
        ("M1-N3-L2", "CADA", ["letra-c", "letra-a", "letra-d", "letra-a"]),
        ("M1-N3-L3", "BEBE", ["letra-b", "letra-e", "letra-b", "letra-e"]),
        ("M1-N3-L4", "HADA", ["letra-h", "letra-a", "letra-d", "letra-a"]),
        ("M1-N4-L2", "SOL", ["letra-s", "letra-o", "letra-l"]),
        ("M1-N4-L3", "LUNA", ["letra-l", "letra-u", "letra-n", "letra-a"]),
        ("M1-N4-L4", "NIDO", ["letra-n", "letra-i", "letra-d", "letra-o"]),
    ],
)
def test_spelling_word_choice(lesson_id: str, word: str, letters: list[str]) -> None:
    payload = _spelling(generated(), lesson_id)
    assert payload.word == word
    assert payload.letter_ids == letters


@pytest.mark.parametrize(
    ("lesson_id", "words"),
    [
        ("M1-N3-L2", SPELLING_M1_N3),
        ("M1-N3-L3", SPELLING_M1_N3),
        ("M1-N3-L4", SPELLING_M1_N3),
        ("M1-N4-L2", SPELLING_M1_N4),
        ("M1-N4-L3", SPELLING_M1_N4),
        ("M1-N4-L4", SPELLING_M1_N4),
    ],
)
def test_spelling_options(lesson_id: str, words: tuple[str, ...]) -> None:
    payload = _spelling(generated(), lesson_id)
    assert payload.option_words[0] == payload.word
    assert len(payload.option_words) == 4
    assert len(set(payload.option_words)) == 4
    assert set(payload.option_words) <= set(words)


def test_m1_n3_l2_spelling_uses_only_letters_a_to_i() -> None:
    allowed = {letter_slug(c) for c in "ABCDEFGHI"}
    payload = _spelling(generated(), "M1-N3-L2")
    assert set(payload.letter_ids) <= allowed


def test_spelling_letters_already_taught() -> None:
    content = generated()
    taught: set[str] = set()
    for node in ("M1-N3", "M1-N4"):
        for i in (1, 2, 3, 4):
            lesson = lessons_by_id(content)[f"{node}-L{i}"]
            taught |= set(lesson.sign_ids)
            if i >= 2:
                assert set(_spelling(content, lesson.id).letter_ids) <= taught, lesson.id


def test_spelling_falls_back_to_first_valid_word_when_all_used() -> None:
    conversations = _conversations_with(
        "M1-N3", NodeConversations(spelling=("CADA", "DAME", "LIMA"))
    )
    content = generate_content(build_modules(), build_signs(), conversations)
    assert _spelling(content, "M1-N3-L2").word == "CADA"
    assert _spelling(content, "M1-N3-L3").word == "DAME"
    assert _spelling(content, "M1-N3-L4").word == "LIMA"
    only_one = _conversations_with("M1-N3", NodeConversations(spelling=("CADA", "LIMA")))
    content = generate_content(build_modules(), build_signs(), only_one)
    assert _spelling(content, "M1-N3-L3").word == "LIMA"
    assert _spelling(content, "M1-N3-L4").word == "CADA"  # ninguna nueva: la primera válida


def test_spelling_with_digraph_uses_longest_match() -> None:
    order = ["A", "B", "C", "CH", "D", "E", "F", "G", "H", "I", "J", "K", "L", "LL", "M"]
    signs = [s for s in build_signs() if s.node_id != "M1-N3"]
    signs += [letter_sign(c, "M1-N3", i) for i, c in enumerate(order, start=1)]
    conversations = _conversations_with(
        "M1-N3", NodeConversations(spelling=("CHICA", "CADA", "CALLE"))
    )
    content = generate_content(build_modules(), signs, conversations)
    assert _spelling(content, "M1-N3-L2").letter_ids == [
        "letra-ch", "letra-i", "letra-c", "letra-a",
    ]  # fmt: skip
    assert _spelling(content, "M1-N3-L4").letter_ids == [
        "letra-c", "letra-a", "letra-ll", "letra-e",
    ]  # fmt: skip


def test_spelling_without_valid_word_raises() -> None:
    conversations = _conversations_with(
        "M1-N3", NodeConversations(spelling=("CAMA", "LIMA", "MALA", "DAME"))
    )
    with pytest.raises(GenerationError):
        generate_content(build_modules(), build_signs(), conversations)


# ---------- PRODUCE y la cámara ---------------------------------------------------------------


def test_camera_label_only_for_static_letters() -> None:
    produces = [e for e in generated().exercises if isinstance(e.payload, ProducePayload)]
    assert produces
    for e in produces:
        assert isinstance(e.payload, ProducePayload)
        sign = SIGNS[e.payload.sign_id]
        lesson_node = e.lesson_id.rsplit("-L", 1)[0]
        if lesson_node in ALPHABET_NODE_IDS and sign.motion is Motion.STATIC:
            assert e.payload.camera_label == sign.id, e.id
        else:
            assert e.payload.camera_label is None, e.id


@pytest.mark.parametrize("slug", ["letra-j", "letra-n-tilde", "letra-z"])
def test_dynamic_letters_use_self_evaluation(slug: str) -> None:
    produces = [
        e.payload
        for e in generated().exercises
        if isinstance(e.payload, ProducePayload) and e.payload.sign_id == slug
    ]
    assert produces
    assert all(p.camera_label is None for p in produces)


def test_static_letter_has_camera_label() -> None:
    produce = _produce_for(generated(), "M1-N3-L1", "letra-a").payload
    assert produce == ProducePayload(sign_id="letra-a", camera_label="letra-a")


# ---------- Determinismo ----------------------------------------------------------------------


def test_generation_is_deterministic_in_process() -> None:
    first = generate_content(build_modules(), build_signs(), build_conversations())
    second = generate_content(build_modules(), build_signs(), build_conversations())
    assert first == second
    assert serialize_content(first) == serialize_content(second)


def test_generate_exercises_matches_generate_content() -> None:
    assert generate_exercises(build_modules(), build_signs(), build_conversations()) == list(
        generated().exercises
    )


_SUBPROCESS_SCRIPT = """
import sys
sys.path.insert(0, sys.argv[1])
from app.domain.content.generator import generate_content
from tests.unit.domain.content_fixture import (
    build_conversations, build_modules, build_signs, serialize_content,
)
content = generate_content(build_modules(), build_signs(), build_conversations())
sys.stdout.write(serialize_content(content))
"""


def _run_in_subprocess(hash_seed: str) -> str:
    env = {**os.environ, "PYTHONHASHSEED": hash_seed, "PYTHONPATH": str(API_DIR)}
    result = subprocess.run(  # noqa: S603  # lista fija de argumentos, sin shell
        [sys.executable, "-c", _SUBPROCESS_SCRIPT, str(API_DIR)],
        cwd=REPO_ROOT,
        env=env,
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    return result.stdout


def test_generation_is_identical_across_processes() -> None:
    """PRUEBA OBLIGATORIA (§6.7): misma salida en procesos con distinto PYTHONHASHSEED."""
    first = _run_in_subprocess("1")
    second = _run_in_subprocess("4242")
    assert first
    assert first == second
    assert first == serialize_content(
        generate_content(build_modules(), build_signs(), build_conversations())
    )


# ---------- Validaciones de contenido mal escrito (revisión del Grupo 1, D-008) ----------------


@pytest.mark.parametrize(
    "bad_turn",
    [
        ("hola", "hola", "adios", "buenas-noches"),  # se responde con la misma seña
        ("hola", "buenos-dias", "hola", "adios"),  # el estímulo aparece como distractor
    ],
)
def test_prompt_among_its_own_options_raises(bad_turn: tuple[str, str, str, str]) -> None:
    conversations = _conversations_with(
        "M1-N1",
        NodeConversations(
            conversations=(conversation(turn(*bad_turn), M1_N1_CONV_L2.turns[1]), M1_N1_CONV_3)
        ),
    )
    with pytest.raises(GenerationError, match="no puede aparecer entre sus propias opciones"):
        generate_content(build_modules(), build_signs(), conversations)


def test_turn_with_repeated_options_raises_generation_error() -> None:
    conversations = _conversations_with(
        "M1-N1",
        NodeConversations(
            conversations=(
                conversation(turn("hola", "buenos-dias", "adios", "adios"), M1_N1_CONV_L2.turns[1]),
                M1_N1_CONV_3,
            )
        ),
    )
    with pytest.raises(GenerationError, match="opciones repetidas"):
        generate_content(build_modules(), build_signs(), conversations)


def test_lowercase_spelling_word_raises() -> None:
    conversations = _conversations_with(
        "M1-N3", NodeConversations(spelling=(*SPELLING_M1_N3, "cada"))
    )
    with pytest.raises(GenerationError, match="debe ir en mayúsculas"):
        generate_content(build_modules(), build_signs(), conversations)


def test_single_spelling_word_raises() -> None:
    conversations = _conversations_with("M1-N3", NodeConversations(spelling=("CADA",)))
    with pytest.raises(GenerationError, match="al menos 2 palabras"):
        generate_content(build_modules(), build_signs(), conversations)


def test_node_with_too_few_signs_raises() -> None:
    signs = [s for s in build_signs() if s.node_id != "M1-N1" or s.order <= 3]
    with pytest.raises(GenerationError, match="no alcanzan para repartirlas"):
        generate_content(build_modules(), signs, build_conversations())


# ---------- Recordar, no repetir (D-021) -------------------------------------------------------


@pytest.mark.parametrize("suffix", ["L1", "L2", "L3"])
def test_first_question_is_never_the_sign_just_shown(suffix: str) -> None:
    content = generated()
    for lesson in content.lessons:
        if not lesson.id.endswith(suffix) or len(lesson.sign_ids) < 2:
            continue
        exercises = exercises_of(content, lesson.id)
        first_question = next(e for e in exercises if e.type is T.VIDEO_TO_MEANING)
        assert first_question.sign_id != lesson.sign_ids[-1], lesson.id


def test_questions_are_not_in_the_observed_order() -> None:
    """El orden de las preguntas es mezclado: en el contenido real casi nunca coincide."""
    content = generated()
    same = total = 0
    for lesson in content.lessons:
        if lesson.id.endswith(("L1", "L2", "L3")) and len(lesson.sign_ids) >= 3:
            questions = [
                e.sign_id for e in exercises_of(content, lesson.id) if e.type is T.VIDEO_TO_MEANING
            ]
            total += 1
            same += questions == list(lesson.sign_ids)
    assert total > 0
    assert same < total / 2

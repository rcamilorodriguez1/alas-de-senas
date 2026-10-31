"""Tarea 1.3 — puntaje de sesión con redondeo entero (§7.2, R3.4)."""

from __future__ import annotations

import pytest

from app.domain.enums import LessonType
from app.domain.policies.scoring import (
    CHALLENGE_PASSING_SCORE,
    PASSING_SCORE,
    SessionScore,
    round_half_up,
    score_session,
)

NON_CHALLENGE = (LessonType.LEARN, LessonType.RECOGNIZE, LessonType.PRACTICE)


# --- round_half_up -----------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("a", "b", "expected"),
    [
        (300, 5, 60),  # 3/5
        (700, 10, 70),  # 7/10
        (600, 10, 60),  # 6/10
        (200, 3, 67),  # 2/3
        (100, 8, 13),  # 1/8 = 12,5 → 13 (round() daría 12)
        (5, 2, 3),  # 2,5 → 3 (round(2.5) == 2)
        (1, 2, 1),  # 0,5 → 1 (round(0.5) == 0)
        (3, 2, 2),  # 1,5 → 2
        (0, 7, 0),
        (10, 5, 2),
        (100, 3, 33),
        (250, 100, 3),  # 2,5 → 3
        (249, 100, 2),
    ],
)
def test_round_half_up(a: int, b: int, expected: int) -> None:
    assert round_half_up(a, b) == expected


def test_round_half_up_coincide_con_la_formula_entera() -> None:
    for a in range(0, 1001, 7):
        for b in range(1, 21):
            assert round_half_up(a, b) == (2 * a + b) // (2 * b)


def test_round_half_up_devuelve_int() -> None:
    assert type(round_half_up(200, 3)) is int


# --- constantes --------------------------------------------------------------------------------


def test_umbrales_de_aprobacion() -> None:
    assert PASSING_SCORE == 60
    assert CHALLENGE_PASSING_SCORE == 70


# --- score_session: casos obligatorios de §7.2 -------------------------------------------------


@pytest.mark.parametrize("lesson_type", NON_CHALLENGE)
def test_3_de_5_da_60_y_aprueba_l1_a_l3(lesson_type: LessonType) -> None:
    assert score_session(3, 5, lesson_type) == SessionScore(3, 5, 60, True)


def test_3_de_5_no_aprueba_el_reto() -> None:
    assert score_session(3, 5, LessonType.CHALLENGE) == SessionScore(3, 5, 60, False)


def test_7_de_10_aprueba_el_reto() -> None:
    assert score_session(7, 10, LessonType.CHALLENGE) == SessionScore(7, 10, 70, True)


def test_6_de_10_no_aprueba_el_reto() -> None:
    assert score_session(6, 10, LessonType.CHALLENGE) == SessionScore(6, 10, 60, False)


def test_2_de_3_da_67() -> None:
    assert score_session(2, 3, LessonType.RECOGNIZE) == SessionScore(2, 3, 67, True)


def test_1_de_8_da_13() -> None:
    assert score_session(1, 8, LessonType.PRACTICE) == SessionScore(1, 8, 13, False)


@pytest.mark.parametrize("lesson_type", list(LessonType))
def test_total_0_da_100_y_aprueba(lesson_type: LessonType) -> None:
    assert score_session(0, 0, lesson_type) == SessionScore(0, 0, 100, True)


# --- score_session: umbrales y límites ----------------------------------------------------------


@pytest.mark.parametrize("lesson_type", NON_CHALLENGE)
def test_6_de_10_aprueba_l1_a_l3(lesson_type: LessonType) -> None:
    assert score_session(6, 10, lesson_type).passed is True


@pytest.mark.parametrize("lesson_type", NON_CHALLENGE)
def test_59_de_100_no_aprueba_l1_a_l3(lesson_type: LessonType) -> None:
    assert score_session(59, 100, lesson_type) == SessionScore(59, 100, 59, False)


def test_aprobacion_del_reto_usa_el_porcentaje_exacto_no_el_redondeado() -> None:
    # 139/200 = 69,5 %: el puntaje se muestra como 70, pero no alcanza el 70 % exacto.
    assert score_session(139, 200, LessonType.CHALLENGE) == SessionScore(139, 200, 70, False)


def test_aprobacion_de_l1_usa_el_porcentaje_exacto_no_el_redondeado() -> None:
    # 119/200 = 59,5 %: puntaje 60, pero no aprueba.
    assert score_session(119, 200, LessonType.LEARN) == SessionScore(119, 200, 60, False)


def test_todo_correcto_da_100() -> None:
    assert score_session(10, 10, LessonType.CHALLENGE) == SessionScore(10, 10, 100, True)


def test_nada_correcto_da_0() -> None:
    assert score_session(0, 10, LessonType.LEARN) == SessionScore(0, 10, 0, False)


def test_score_es_int() -> None:
    assert type(score_session(2, 3, LessonType.LEARN).score) is int

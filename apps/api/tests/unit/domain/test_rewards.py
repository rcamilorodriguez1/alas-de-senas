"""Tarea 1.4 — XP y néctar al completar una lección (§7.3, R5.1-5.4)."""

from __future__ import annotations

import pytest

from app.domain.enums import LessonType
from app.domain.policies.rewards import Reward, RewardPolicy
from app.domain.policies.scoring import SessionScore

NON_CHALLENGE = (LessonType.LEARN, LessonType.RECOGNIZE, LessonType.PRACTICE)


def _score(score: int, passed: bool = True) -> SessionScore:
    return SessionScore(correct=score, total=100, score=score, passed=passed)


def _calc(lesson_type: LessonType, score: SessionScore, previously_passed: bool) -> Reward:
    return RewardPolicy().calculate(lesson_type, score, previously_passed)


# --- casos obligatorios de §7.3 ----------------------------------------------------------------


def test_l1_100_primera_vez_da_20_xp_y_5_nectar() -> None:
    assert _calc(LessonType.LEARN, _score(100), previously_passed=False) == Reward(20, 5)


def test_l1_100_repetida_da_10_xp() -> None:
    assert _calc(LessonType.LEARN, _score(100), previously_passed=True) == Reward(10, 5)


def test_reto_70_primera_vez_da_24_xp_y_15_nectar() -> None:
    assert _calc(LessonType.CHALLENGE, _score(70), previously_passed=False) == Reward(24, 15)


def test_reto_70_repetido_da_12_xp_y_5_nectar() -> None:
    assert _calc(LessonType.CHALLENGE, _score(70), previously_passed=True) == Reward(12, 5)


@pytest.mark.parametrize("lesson_type", list(LessonType))
@pytest.mark.parametrize("previously_passed", [False, True])
def test_no_aprobada_da_0_xp_y_0_nectar(lesson_type: LessonType, previously_passed: bool) -> None:
    assert _calc(lesson_type, _score(50, passed=False), previously_passed) == Reward(0, 0)


def test_reto_60_no_aprobado_da_0() -> None:
    assert _calc(LessonType.CHALLENGE, _score(60, passed=False), False) == Reward(0, 0)


# --- fórmula -----------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("score", "expected_xp"),
    [
        (60, 13),  # 10 + round_half_up(300, 100) = 10 + 3
        (67, 13),  # 3,35 → 3
        (70, 14),  # 3,5 → 4 (redondeo hacia arriba en .5)
        (90, 15),  # 4,5 → 5
        (99, 15),  # 4,95 → 5, sin bono perfecto
        (100, 20),  # 10 + 5 + 5 (perfecto)
    ],
)
@pytest.mark.parametrize("lesson_type", NON_CHALLENGE)
def test_xp_lecciones_normales_primera_vez(
    lesson_type: LessonType, score: int, expected_xp: int
) -> None:
    assert _calc(lesson_type, _score(score), previously_passed=False) == Reward(expected_xp, 5)


@pytest.mark.parametrize(
    ("score", "expected_xp"),
    [
        (70, 24),
        (90, 25),
        (99, 25),
        (100, 30),
    ],
)
def test_xp_reto_primera_vez(score: int, expected_xp: int) -> None:
    assert _calc(LessonType.CHALLENGE, _score(score), previously_passed=False) == Reward(
        expected_xp, 15
    )


def test_repetida_redondea_la_mitad_hacia_arriba() -> None:
    # 13 XP / 2 = 6,5 → 7.
    assert _calc(LessonType.RECOGNIZE, _score(60), previously_passed=True) == Reward(7, 5)


def test_reto_100_repetido() -> None:
    assert _calc(LessonType.CHALLENGE, _score(100), previously_passed=True) == Reward(15, 5)


def test_reto_90_repetido_redondea_hacia_arriba() -> None:
    # 25 XP / 2 = 12,5 → 13.
    assert _calc(LessonType.CHALLENGE, _score(90), previously_passed=True) == Reward(13, 5)


@pytest.mark.parametrize("lesson_type", NON_CHALLENGE)
@pytest.mark.parametrize("previously_passed", [False, True])
def test_bono_de_nectar_solo_en_retos(lesson_type: LessonType, previously_passed: bool) -> None:
    assert _calc(lesson_type, _score(100), previously_passed).nectar == 5


def test_sesion_sin_ejercicios_con_puntaje_recibe_bono_perfecto() -> None:
    score = SessionScore(correct=0, total=0, score=100, passed=True)
    assert _calc(LessonType.LEARN, score, previously_passed=False) == Reward(20, 5)


def test_calculate_devuelve_enteros() -> None:
    reward = _calc(LessonType.RECOGNIZE, _score(67), previously_passed=True)
    assert type(reward.xp) is int
    assert type(reward.nectar) is int


# ---------- XP estimada en la ruta (revisión del Grupo 4) -------------------------------------


@pytest.mark.parametrize(
    ("lesson_type", "previously_passed", "expected"),
    [
        (LessonType.LEARN, False, 20),
        (LessonType.PRACTICE, False, 20),
        (LessonType.CHALLENGE, False, 30),
        (LessonType.LEARN, True, 10),
        (LessonType.CHALLENGE, True, 15),
    ],
)
def test_max_xp_es_el_de_aprobar_con_100(
    lesson_type: LessonType, previously_passed: bool, expected: int
) -> None:
    assert RewardPolicy().max_xp(lesson_type, previously_passed) == expected

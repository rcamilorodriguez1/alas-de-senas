"""Tarea 1.9 — los 9 logros y `evaluate_achievements` (§7.9, R5.10)."""

from __future__ import annotations

from collections.abc import Callable

import pytest

from app.domain.policies.achievements import (
    ACHIEVEMENTS,
    AchievementRule,
    AchievementStats,
    evaluate_achievements,
)

EXPECTED_TABLE: list[tuple[str, str, int]] = [
    ("FIRST_FLAP", "Primer aleteo", 10),
    ("FIRST_LESSON", "Primeras alas", 10),
    ("STREAK_3", "Aleteo constante", 15),
    ("STREAK_7", "Vuelo de una semana", 30),
    ("NODE_DONE", "Nodo superado", 15),
    ("GOLDEN_NODE", "Nodo dorado", 20),
    ("MODULE_1", "Fundamentos dominados", 40),
    ("SIGNS_50", "Manos que hablan", 40),
    ("HUMMINGBIRD_EYE", "Ojo de colibrí", 30),
]

ALL_IDS = [row[0] for row in EXPECTED_TABLE]

EVERYTHING = AchievementStats(
    intro_completed=True,
    lessons_passed=40,
    current_streak=10,
    challenges_passed=10,
    golden_challenges=3,
    module1_completed=True,
    distinct_signs_correct=80,
    camera_correct=25,
)


def rule(achievement_id: str) -> AchievementRule:
    matches = [r for r in ACHIEVEMENTS if r.id == achievement_id]
    assert len(matches) == 1, achievement_id
    return matches[0]


# --- catálogo ----------------------------------------------------------------------------------


def test_hay_9_logros_en_el_orden_de_la_tabla_con_titulo_y_nectar_exactos() -> None:
    assert [(r.id, r.title, r.nectar_reward) for r in ACHIEVEMENTS] == EXPECTED_TABLE


def test_cada_logro_implementa_achievement_rule() -> None:
    assert all(isinstance(r, AchievementRule) for r in ACHIEVEMENTS)


def test_ids_unicos() -> None:
    assert len({r.id for r in ACHIEVEMENTS}) == len(ACHIEVEMENTS)


def test_ninguno_se_cumple_con_estadisticas_vacias() -> None:
    assert [r.id for r in ACHIEVEMENTS if r.is_satisfied(AchievementStats())] == []


# --- condiciones: umbral exacto y uno menos ----------------------------------------------------


def test_first_flap_requiere_intro_completado() -> None:
    assert rule("FIRST_FLAP").is_satisfied(AchievementStats(intro_completed=True))
    assert not rule("FIRST_FLAP").is_satisfied(AchievementStats(intro_completed=False))


def test_module_1_requiere_m1_completo() -> None:
    assert rule("MODULE_1").is_satisfied(AchievementStats(module1_completed=True))
    assert not rule("MODULE_1").is_satisfied(AchievementStats(module1_completed=False))


def _lessons(n: int) -> AchievementStats:
    return AchievementStats(lessons_passed=n)


def _streak(n: int) -> AchievementStats:
    return AchievementStats(current_streak=n)


def _challenges(n: int) -> AchievementStats:
    return AchievementStats(challenges_passed=n)


def _golden(n: int) -> AchievementStats:
    return AchievementStats(golden_challenges=n)


def _signs(n: int) -> AchievementStats:
    return AchievementStats(distinct_signs_correct=n)


def _camera(n: int) -> AchievementStats:
    return AchievementStats(camera_correct=n)


@pytest.mark.parametrize(
    ("achievement_id", "build", "threshold"),
    [
        ("FIRST_LESSON", _lessons, 1),
        ("STREAK_3", _streak, 3),
        ("STREAK_7", _streak, 7),
        ("NODE_DONE", _challenges, 1),
        ("GOLDEN_NODE", _golden, 1),
        ("SIGNS_50", _signs, 50),
        ("HUMMINGBIRD_EYE", _camera, 20),
    ],
)
def test_umbral_exacto_cumple_y_uno_menos_no(
    achievement_id: str, build: Callable[[int], AchievementStats], threshold: int
) -> None:
    achievement = rule(achievement_id)
    at = build(threshold)
    below = build(threshold - 1)
    above = build(threshold + 5)

    assert achievement.is_satisfied(at)
    assert achievement.is_satisfied(above)
    assert not achievement.is_satisfied(below)


def test_cada_condicion_depende_solo_de_su_campo() -> None:
    # Una racha de 7 no da logros de lecciones, cámara ni señas.
    stats = AchievementStats(current_streak=7)
    assert [r.id for r in ACHIEVEMENTS if r.is_satisfied(stats)] == ["STREAK_3", "STREAK_7"]


# --- evaluate_achievements ---------------------------------------------------------------------


def test_evaluate_devuelve_todos_en_orden_si_no_hay_desbloqueados() -> None:
    assert evaluate_achievements(EVERYTHING, set()) == ALL_IDS


def test_evaluate_excluye_los_ya_desbloqueados() -> None:
    already = {"FIRST_FLAP", "STREAK_3", "HUMMINGBIRD_EYE"}
    expected = [i for i in ALL_IDS if i not in already]
    assert evaluate_achievements(EVERYTHING, already) == expected


def test_evaluate_todo_desbloqueado_devuelve_vacio() -> None:
    assert evaluate_achievements(EVERYTHING, ALL_IDS) == []


def test_evaluate_sin_condiciones_cumplidas_devuelve_vacio() -> None:
    assert evaluate_achievements(AchievementStats(), set()) == []


def test_evaluate_respeta_el_orden_de_achievements_no_el_de_la_entrada() -> None:
    stats = AchievementStats(intro_completed=True, lessons_passed=1, camera_correct=20)
    assert evaluate_achievements(stats, []) == ["FIRST_FLAP", "FIRST_LESSON", "HUMMINGBIRD_EYE"]


def test_evaluate_primera_leccion_tras_el_intro() -> None:
    stats = AchievementStats(intro_completed=True, lessons_passed=1, current_streak=1)
    assert evaluate_achievements(stats, {"FIRST_FLAP"}) == ["FIRST_LESSON"]


def test_evaluate_reto_dorado_da_nodo_superado_y_nodo_dorado() -> None:
    stats = AchievementStats(lessons_passed=4, challenges_passed=1, golden_challenges=1)
    assert evaluate_achievements(stats, ["FIRST_LESSON"]) == ["NODE_DONE", "GOLDEN_NODE"]


def test_evaluate_ignora_ids_desconocidos_en_already_unlocked() -> None:
    stats = AchievementStats(intro_completed=True)
    assert evaluate_achievements(stats, {"NO_EXISTE"}) == ["FIRST_FLAP"]


def test_evaluate_es_pura() -> None:
    already = frozenset({"FIRST_FLAP"})
    first = evaluate_achievements(EVERYTHING, already)
    second = evaluate_achievements(EVERYTHING, already)

    assert first == second
    assert already == frozenset({"FIRST_FLAP"})


def test_evaluate_acepta_tupla_y_lista() -> None:
    stats = AchievementStats(intro_completed=True, lessons_passed=1)
    assert evaluate_achievements(stats, ("FIRST_FLAP",)) == ["FIRST_LESSON"]
    assert evaluate_achievements(stats, ["FIRST_FLAP"]) == ["FIRST_LESSON"]

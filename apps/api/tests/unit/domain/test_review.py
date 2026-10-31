"""Tarea 1.7 — repaso espaciado (§7.7, R6.4-6.5)."""

from __future__ import annotations

import pytest

from app.domain.dates import add_days
from app.domain.policies.review import (
    INTERVALS,
    MAX_STRENGTH,
    QUEUE_LIMIT,
    ReviewScheduler,
    SignReview,
)

scheduler = ReviewScheduler()

TODAY = "2026-11-10"


# --- constantes --------------------------------------------------------------------------------


def test_constantes() -> None:
    assert INTERVALS == (1, 2, 4, 7, 15, 30)
    assert MAX_STRENGTH == 5
    assert QUEUE_LIMIT == 15


# --- schedule ----------------------------------------------------------------------------------


def test_primera_vez_con_acierto_queda_en_fuerza_1_y_vuelve_en_2_dias() -> None:
    assert scheduler.schedule(None, "hola", True, TODAY) == SignReview("hola", 1, "2026-11-12")


def test_primera_vez_con_error_queda_en_fuerza_0_y_vuelve_manana() -> None:
    assert scheduler.schedule(None, "hola", False, TODAY) == SignReview("hola", 0, "2026-11-11")


@pytest.mark.parametrize(
    ("strength", "expected_strength", "expected_day"),
    [
        (0, 1, "2026-11-12"),  # +2
        (1, 2, "2026-11-14"),  # +4
        (2, 3, "2026-11-17"),  # +7
        (3, 4, "2026-11-25"),  # +15
        (4, 5, "2026-12-10"),  # +30
        (5, 5, "2026-12-10"),  # tope en 5
    ],
)
def test_acierto_sube_la_fuerza_y_usa_el_intervalo(
    strength: int, expected_strength: int, expected_day: str
) -> None:
    review = SignReview("gracias", strength, "2026-11-01")
    assert scheduler.schedule(review, "gracias", True, TODAY) == SignReview(
        "gracias", expected_strength, expected_day
    )


@pytest.mark.parametrize("strength", [0, 1, 3, 5])
def test_error_o_necesito_repasar_reinicia_a_0(strength: int) -> None:
    review = SignReview("gracias", strength, "2026-11-01")
    assert scheduler.schedule(review, "gracias", False, TODAY) == SignReview(
        "gracias", 0, "2026-11-11"
    )


def test_next_review_day_es_add_days_del_intervalo() -> None:
    for strength in range(MAX_STRENGTH):
        review = SignReview("a", strength, TODAY)
        result = scheduler.schedule(review, "a", True, TODAY)
        assert result.next_review_day == add_days(TODAY, INTERVALS[result.strength])


def test_programacion_siempre_es_posterior_a_hoy() -> None:
    # Así el repaso no se puede repetir el mismo día para inflar la racha (§7.5).
    for strength in range(MAX_STRENGTH + 1):
        for correct in (True, False):
            review = SignReview("a", strength, TODAY)
            assert scheduler.schedule(review, "a", correct, TODAY).next_review_day > TODAY


def test_schedule_cruza_el_anio() -> None:
    review = SignReview("a", 4, "2026-12-01")
    assert scheduler.schedule(review, "a", True, "2026-12-15") == SignReview("a", 5, "2027-01-14")


def test_schedule_no_modifica_la_entrada() -> None:
    review = SignReview("a", 2, "2026-11-01")
    scheduler.schedule(review, "a", True, TODAY)
    assert review == SignReview("a", 2, "2026-11-01")


# --- due ---------------------------------------------------------------------------------------


def test_due_solo_incluye_vencidas_hasta_hoy() -> None:
    reviews = [
        SignReview("ayer", 2, "2026-11-09"),
        SignReview("hoy", 2, TODAY),
        SignReview("manana", 0, "2026-11-11"),
    ]
    assert [r.sign_id for r in scheduler.due(reviews, TODAY)] == ["ayer", "hoy"]


def test_due_menor_fuerza_primero() -> None:
    reviews = [
        SignReview("fuerte", 4, "2026-11-01"),
        SignReview("debil", 0, "2026-11-09"),
        SignReview("media", 2, "2026-11-05"),
    ]
    assert [r.sign_id for r in scheduler.due(reviews, TODAY)] == ["debil", "media", "fuerte"]


def test_due_empate_de_fuerza_por_dia_y_luego_sign_id() -> None:
    reviews = [
        SignReview("c", 1, "2026-11-08"),
        SignReview("b", 1, "2026-11-09"),
        SignReview("a", 1, "2026-11-09"),
        SignReview("z", 1, "2026-11-07"),
    ]
    assert [r.sign_id for r in scheduler.due(reviews, TODAY)] == ["z", "c", "a", "b"]


def test_due_maximo_15_por_defecto() -> None:
    reviews = [SignReview(f"s{i:02d}", 0, TODAY) for i in range(20)]
    result = scheduler.due(reviews, TODAY)
    assert len(result) == 15
    assert [r.sign_id for r in result] == [f"s{i:02d}" for i in range(15)]


def test_due_limite_se_aplica_despues_de_ordenar() -> None:
    reviews = [SignReview(f"fuerte{i:02d}", 5, TODAY) for i in range(15)]
    reviews.append(SignReview("debil", 0, TODAY))
    result = scheduler.due(reviews, TODAY)
    assert len(result) == 15
    assert result[0].sign_id == "debil"
    assert "fuerte14" not in [r.sign_id for r in result]


def test_due_limite_personalizado() -> None:
    reviews = [SignReview(f"s{i}", 0, TODAY) for i in range(5)]
    assert len(scheduler.due(reviews, TODAY, limit=3)) == 3


def test_due_sin_vencidas_devuelve_lista_vacia() -> None:
    assert scheduler.due([SignReview("a", 0, "2026-11-11")], TODAY) == []
    assert scheduler.due([], TODAY) == []


def test_due_acepta_un_iterable_cualquiera() -> None:
    reviews = (r for r in [SignReview("b", 1, TODAY), SignReview("a", 0, TODAY)])
    assert [r.sign_id for r in scheduler.due(reviews, TODAY)] == ["a", "b"]


def test_due_compara_fechas_cruzando_el_anio() -> None:
    reviews = [SignReview("viejo", 0, "2026-12-31"), SignReview("nuevo", 0, "2027-01-02")]
    assert [r.sign_id for r in scheduler.due(reviews, "2027-01-01")] == ["viejo"]

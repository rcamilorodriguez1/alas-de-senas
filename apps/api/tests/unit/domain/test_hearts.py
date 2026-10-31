"""Tarea 1.11 — vidas derivadas de `hearts_updated_at` (§7.10, D24, R5.13-5.16)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from app.domain.policies.hearts import (
    MAX_HEARTS,
    REFILL_COST,
    REFILL_EVERY,
    HeartsPolicy,
    HeartsState,
)
from tests.fakes import FakeClock

policy = HeartsPolicy()

T0 = datetime(2026, 11, 4, 15, 0, tzinfo=UTC)
H = timedelta(hours=1)


# --- constantes --------------------------------------------------------------------------------


def test_constantes() -> None:
    assert MAX_HEARTS == 5
    assert timedelta(hours=4) == REFILL_EVERY
    assert REFILL_COST == 30


# --- casos obligatorios de §7.10 ---------------------------------------------------------------


def test_5_vidas_un_error_deja_4_y_la_proxima_llega_en_4_horas() -> None:
    clock = FakeClock(T0)
    state = policy.lose_one(HeartsState(5, None), clock.now())

    assert state == HeartsState(4, T0)
    assert policy.current(state, clock.now()) == (4, T0 + 4 * H)


def test_a_las_3h59_sigue_en_4_y_a_las_4h_vuelve_a_5() -> None:
    clock = FakeClock(T0)
    state = policy.lose_one(HeartsState(5, None), clock.now())

    clock.advance(hours=3, minutes=59)
    assert policy.current(state, clock.now()) == (4, T0 + 4 * H)

    clock.advance(minutes=1)
    assert policy.current(state, clock.now()) == (5, None)


def test_con_3_vidas_y_5h_perder_una_deja_3_y_conserva_1h_de_avance() -> None:
    state = HeartsState(3, T0)
    now = T0 + 5 * H
    assert policy.current(state, now) == (4, T0 + 8 * H)

    after = policy.lose_one(state, now)

    assert after == HeartsState(3, T0 + 4 * H)
    # Lleva 1 h de avance: la próxima vida llega en 3 h, no en 4.
    assert policy.current(after, now) == (3, now + 3 * H)


def test_con_0_vidas_no_baja_de_0() -> None:
    state = HeartsState(0, T0)
    now = T0 + 1 * H

    after = policy.lose_one(state, now)

    assert after == HeartsState(0, T0)
    assert policy.current(after, now) == (0, T0 + 4 * H)


def test_updated_at_en_el_futuro_no_suma_vidas() -> None:
    # Reloj atrasado: la última actualización quedó 2 h "en el futuro".
    future = T0 + 2 * H
    state = HeartsState(2, future)

    assert policy.current(state, T0) == (2, future + 4 * H)
    assert policy.lose_one(state, T0) == HeartsState(1, future)


def test_gain_one_con_5_no_pasa_de_5() -> None:
    assert policy.gain_one(HeartsState(5, None), T0) == HeartsState(5, None)
    assert policy.current(policy.gain_one(HeartsState(5, None), T0), T0) == (5, None)


# --- current -----------------------------------------------------------------------------------


def test_current_updated_at_none_es_lleno() -> None:
    assert policy.current(HeartsState(5, None), T0) == (5, None)
    assert policy.current(HeartsState(2, None), T0) == (5, None)


def test_current_con_5_y_fecha_es_lleno() -> None:
    assert policy.current(HeartsState(5, T0), T0 + 1 * H) == (5, None)


def test_current_recupera_varias_vidas() -> None:
    # 1 vida + 9 h → +2 → 3; la próxima a las 12 h.
    assert policy.current(HeartsState(1, T0), T0 + 9 * H) == (3, T0 + 12 * H)


def test_current_tope_en_5_tras_mucho_tiempo() -> None:
    assert policy.current(HeartsState(0, T0), T0 + 30 * H) == (5, None)


def test_current_justo_al_completar_la_ultima_vida() -> None:
    assert policy.current(HeartsState(3, T0), T0 + 8 * H) == (5, None)
    assert policy.current(HeartsState(3, T0), T0 + 8 * H - timedelta(seconds=1)) == (
        4,
        T0 + 8 * H,
    )


def test_current_desde_0_tras_4_horas_tiene_1() -> None:
    assert policy.current(HeartsState(0, T0), T0 + 4 * H) == (1, T0 + 8 * H)


def test_current_no_modifica_el_estado() -> None:
    state = HeartsState(3, T0)
    policy.current(state, T0 + 5 * H)
    assert state == HeartsState(3, T0)


# --- lose_one ----------------------------------------------------------------------------------


def test_lose_one_lleno_con_fecha_empieza_a_contar_desde_now() -> None:
    now = T0 + 10 * H
    assert policy.lose_one(HeartsState(5, T0), now) == HeartsState(4, now)


def test_lose_one_tras_recuperar_todo_empieza_desde_now() -> None:
    # 4 vidas + 6 h → 5 (lleno): perder una reinicia la cuenta en `now`.
    now = T0 + 6 * H
    assert policy.lose_one(HeartsState(4, T0), now) == HeartsState(4, now)


def test_lose_one_sin_tiempo_transcurrido() -> None:
    assert policy.lose_one(HeartsState(3, T0), T0) == HeartsState(2, T0)


def test_lose_one_de_1_a_0() -> None:
    now = T0 + 1 * H
    after = policy.lose_one(HeartsState(1, T0), now)
    assert after == HeartsState(0, T0)
    assert policy.current(after, T0 + 4 * H) == (1, T0 + 8 * H)


def test_lose_one_materializa_varias_vidas_recuperadas() -> None:
    # 1 vida + 9 h → 3 vidas (2 recuperadas); perder una deja 2 con 1 h de avance.
    now = T0 + 9 * H
    assert policy.lose_one(HeartsState(1, T0), now) == HeartsState(2, T0 + 8 * H)


def test_cinco_errores_seguidos_dejan_0_y_un_sexto_no_baja_mas() -> None:
    clock = FakeClock(T0)
    state = HeartsState(5, None)
    for _ in range(5):
        state = policy.lose_one(state, clock.now())
        clock.advance(minutes=1)
    assert policy.current(state, clock.now())[0] == 0

    again = policy.lose_one(state, clock.now())
    assert policy.current(again, clock.now())[0] == 0


# --- gain_one ----------------------------------------------------------------------------------


def test_gain_one_suma_1_y_conserva_el_avance() -> None:
    assert policy.gain_one(HeartsState(3, T0), T0 + 1 * H) == HeartsState(4, T0)


def test_gain_one_materializa_antes_de_sumar() -> None:
    # 2 vidas + 5 h → 3 (1 recuperada) → +1 → 4, con 1 h de avance.
    assert policy.gain_one(HeartsState(2, T0), T0 + 5 * H) == HeartsState(4, T0 + 4 * H)


def test_gain_one_que_llega_a_5_queda_lleno() -> None:
    assert policy.gain_one(HeartsState(4, T0), T0 + 1 * H) == HeartsState(5, None)
    # 3 vidas + 5 h → 4 → +1 → 5.
    assert policy.gain_one(HeartsState(3, T0), T0 + 5 * H) == HeartsState(5, None)


def test_gain_one_con_5_y_fecha_queda_lleno() -> None:
    assert policy.gain_one(HeartsState(5, T0), T0) == HeartsState(5, None)


def test_gain_one_desde_0() -> None:
    assert policy.gain_one(HeartsState(0, T0), T0 + 1 * H) == HeartsState(1, T0)


# --- refill ------------------------------------------------------------------------------------


def test_refill_llena_todo() -> None:
    assert policy.refill(T0) == HeartsState(5, None)
    assert policy.current(policy.refill(T0), T0) == (5, None)

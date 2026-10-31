"""Tarea 1.6 — racha diaria con protectores (§7.5, R5.5-5.8)."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from app.domain.dates import to_local_day
from app.domain.policies.streak import FREEZE_COST, MAX_FREEZES, Streak, StreakPolicy
from tests.fakes import FakeClock

policy = StreakPolicy()

TODAY = "2026-11-10"
YESTERDAY = "2026-11-09"


# --- constantes --------------------------------------------------------------------------------


def test_constantes_del_protector() -> None:
    assert FREEZE_COST == 50
    assert MAX_FREEZES == 2


# --- casos obligatorios de §7.5 ----------------------------------------------------------------


def test_actividad_a_las_2359_y_a_las_0001_de_bogota_cuenta_como_dos_dias() -> None:
    # 23:59 en Bogotá del 3 de noviembre = 04:59Z del 4; 00:01 del 4 en Bogotá = 05:01Z del 4.
    clock = FakeClock(datetime(2026, 11, 4, 4, 59, tzinfo=UTC))
    first_day = to_local_day(clock.now())
    streak = policy.apply_activity(Streak(), first_day)

    clock.advance(minutes=2)
    second_day = to_local_day(clock.now())
    streak = policy.apply_activity(streak, second_day)

    assert (first_day, second_day) == ("2026-11-03", "2026-11-04")
    assert streak.current == 2
    assert streak.longest == 2
    assert streak.last_active_day == "2026-11-04"


def test_dos_actividades_en_utc_del_mismo_dia_bogota_cuentan_como_una() -> None:
    # 00:30Z y 04:30Z del 4 de noviembre son, en Bogotá, el 3 de noviembre.
    morning = to_local_day(datetime(2026, 11, 4, 0, 30, tzinfo=UTC))
    later = to_local_day(datetime(2026, 11, 4, 4, 30, tzinfo=UTC))
    streak = policy.apply_activity(
        Streak(current=4, longest=4, last_active_day="2026-11-02"), morning
    )
    streak = policy.apply_activity(streak, later)

    assert streak == Streak(current=5, longest=5, freezes_available=0, last_active_day="2026-11-03")


def test_dos_lecciones_el_mismo_dia_no_suben_la_racha_dos_veces() -> None:
    start = Streak(current=3, longest=5, freezes_available=1, last_active_day=YESTERDAY)
    after_first = policy.apply_activity(start, TODAY)
    after_second = policy.apply_activity(after_first, TODAY)

    assert after_first.current == 4
    assert after_second == after_first


def test_una_leccion_y_un_repaso_el_mismo_dia_suben_solo_1() -> None:
    # La misma función se usa para lecciones y repasos (GamificationService.register_activity).
    start = Streak(current=3, longest=3, last_active_day=YESTERDAY)
    after_lesson = policy.apply_activity(start, TODAY)
    after_review = policy.apply_activity(after_lesson, TODAY)

    assert after_review == Streak(current=4, longest=4, freezes_available=0, last_active_day=TODAY)


def test_un_dia_perdido_con_1_protector_conserva_la_racha_y_consume_1() -> None:
    start = Streak(current=6, longest=6, freezes_available=1, last_active_day="2026-11-08")
    result = policy.apply_activity(start, TODAY)

    assert result == Streak(current=7, longest=7, freezes_available=0, last_active_day=TODAY)


def test_dos_dias_perdidos_con_1_protector_reinicia_a_1() -> None:
    start = Streak(current=6, longest=6, freezes_available=1, last_active_day="2026-11-07")
    result = policy.apply_activity(start, TODAY)

    assert result.current == 1
    assert result.longest == 6
    assert result.last_active_day == TODAY


# --- apply_activity: resto de reglas -----------------------------------------------------------


def test_primera_actividad_inicia_en_1() -> None:
    assert policy.apply_activity(Streak(), TODAY) == Streak(
        current=1, longest=1, freezes_available=0, last_active_day=TODAY
    )


def test_primera_actividad_conserva_protectores() -> None:
    result = policy.apply_activity(Streak(freezes_available=2), TODAY)
    assert result == Streak(current=1, longest=1, freezes_available=2, last_active_day=TODAY)


def test_dia_consecutivo_suma_1_sin_consumir_protectores() -> None:
    start = Streak(current=2, longest=2, freezes_available=2, last_active_day=YESTERDAY)
    assert policy.apply_activity(start, TODAY) == Streak(
        current=3, longest=3, freezes_available=2, last_active_day=TODAY
    )


def test_dos_dias_perdidos_con_2_protectores_consume_2_y_conserva() -> None:
    start = Streak(current=6, longest=8, freezes_available=2, last_active_day="2026-11-07")
    assert policy.apply_activity(start, TODAY) == Streak(
        current=7, longest=8, freezes_available=0, last_active_day=TODAY
    )


def test_un_dia_perdido_con_2_protectores_consume_solo_1() -> None:
    start = Streak(current=6, longest=6, freezes_available=2, last_active_day="2026-11-08")
    assert policy.apply_activity(start, TODAY) == Streak(
        current=7, longest=7, freezes_available=1, last_active_day=TODAY
    )


def test_tres_dias_perdidos_con_2_protectores_reinicia_sin_consumirlos() -> None:
    start = Streak(current=6, longest=6, freezes_available=2, last_active_day="2026-11-06")
    assert policy.apply_activity(start, TODAY) == Streak(
        current=1, longest=6, freezes_available=2, last_active_day=TODAY
    )


def test_un_dia_perdido_sin_protectores_reinicia_a_1() -> None:
    start = Streak(current=10, longest=12, freezes_available=0, last_active_day="2026-11-08")
    assert policy.apply_activity(start, TODAY) == Streak(
        current=1, longest=12, freezes_available=0, last_active_day=TODAY
    )


def test_fecha_anterior_a_la_ultima_actividad_no_cambia_nada() -> None:
    start = Streak(current=5, longest=7, freezes_available=1, last_active_day=TODAY)
    assert policy.apply_activity(start, YESTERDAY) == start


def test_longest_es_el_maximo_historico() -> None:
    start = Streak(current=9, longest=9, last_active_day=YESTERDAY)
    assert policy.apply_activity(start, TODAY).longest == 10

    lower = Streak(current=2, longest=9, last_active_day=YESTERDAY)
    assert policy.apply_activity(lower, TODAY).longest == 9


def test_cruza_el_cambio_de_anio() -> None:
    start = Streak(current=3, longest=3, last_active_day="2026-12-31")
    assert policy.apply_activity(start, "2027-01-01").current == 4


def test_cruza_el_29_de_febrero() -> None:
    start = Streak(current=3, longest=3, last_active_day="2028-02-28")
    assert policy.apply_activity(start, "2028-02-29").current == 4
    # 28 feb → 1 mar en bisiesto son 2 días: falta el 29.
    assert policy.apply_activity(start, "2028-03-01").current == 1


def test_apply_activity_no_modifica_la_entrada() -> None:
    start = Streak(current=3, longest=3, freezes_available=1, last_active_day="2026-11-08")
    policy.apply_activity(start, TODAY)
    assert start == Streak(current=3, longest=3, freezes_available=1, last_active_day="2026-11-08")


# --- display -----------------------------------------------------------------------------------


def test_display_sin_actividad_es_0() -> None:
    assert policy.display(Streak(), TODAY) == 0


def test_display_actividad_hoy_muestra_current() -> None:
    assert policy.display(Streak(current=4, longest=4, last_active_day=TODAY), TODAY) == 4


def test_display_actividad_ayer_muestra_current() -> None:
    assert policy.display(Streak(current=4, longest=4, last_active_day=YESTERDAY), TODAY) == 4


@pytest.mark.parametrize(
    ("last_active_day", "freezes", "expected"),
    [
        ("2026-11-08", 1, 4),  # 1 día perdido, 1 protector → protegida
        ("2026-11-08", 0, 0),  # 1 día perdido, sin protector → 0
        ("2026-11-07", 1, 0),  # 2 días perdidos, 1 protector → 0
        ("2026-11-07", 2, 4),  # 2 días perdidos, 2 protectores → protegida
        ("2026-11-06", 2, 0),  # 3 días perdidos, 2 protectores → 0
    ],
)
def test_display_con_protectores(last_active_day: str, freezes: int, expected: int) -> None:
    streak = Streak(
        current=4, longest=4, freezes_available=freezes, last_active_day=last_active_day
    )
    assert policy.display(streak, TODAY) == expected


def test_display_no_modifica_la_racha() -> None:
    streak = Streak(current=4, longest=4, freezes_available=1, last_active_day="2026-11-08")
    policy.display(streak, TODAY)
    assert streak == Streak(current=4, longest=4, freezes_available=1, last_active_day="2026-11-08")


def test_display_medianoche_bogota() -> None:
    # Activo el 3 (Bogotá). A las 04:59Z del 5 aún es el 4 en Bogotá → ayer → se muestra.
    streak = Streak(current=2, longest=2, last_active_day="2026-11-03")
    assert policy.display(streak, to_local_day(datetime(2026, 11, 5, 4, 59, tzinfo=UTC))) == 2
    # A las 05:00Z del 5 ya es el 5 en Bogotá → se perdió un día sin protector → 0.
    assert policy.display(streak, to_local_day(datetime(2026, 11, 5, 5, 0, tzinfo=UTC))) == 0


# --- is_at_risk --------------------------------------------------------------------------------


def test_en_riesgo_si_la_ultima_actividad_fue_ayer() -> None:
    assert policy.is_at_risk(Streak(current=3, longest=3, last_active_day=YESTERDAY), TODAY)


def test_no_en_riesgo_si_ya_practico_hoy() -> None:
    assert not policy.is_at_risk(Streak(current=3, longest=3, last_active_day=TODAY), TODAY)


def test_no_en_riesgo_sin_actividad() -> None:
    assert not policy.is_at_risk(Streak(), TODAY)


def test_no_en_riesgo_si_la_ultima_actividad_fue_hace_dos_dias() -> None:
    streak = Streak(current=3, longest=3, freezes_available=1, last_active_day="2026-11-08")
    assert not policy.is_at_risk(streak, TODAY)

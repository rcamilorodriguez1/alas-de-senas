"""Tarea 1.1 — fechas de negocio en hora de Bogotá (§7.1, R5.5)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import pytest

from app.domain.dates import TZ, Clock, add_days, diff_days, to_local_day
from tests.fakes import FakeClock

UTC_ZONE = ZoneInfo("UTC")

# --- to_local_day -----------------------------------------------------------------------------


def test_to_local_day_0459z_es_el_dia_anterior_en_bogota() -> None:
    assert to_local_day(datetime(2026, 11, 4, 4, 59, tzinfo=UTC)) == "2026-11-03"


def test_to_local_day_0500z_es_medianoche_en_bogota() -> None:
    assert to_local_day(datetime(2026, 11, 4, 5, 0, tzinfo=UTC)) == "2026-11-04"


def test_to_local_day_sin_zona_horaria_lanza_value_error() -> None:
    naive = datetime(2026, 11, 4, 12, 0)  # noqa: DTZ001 — se prueba justamente el caso sin tz
    with pytest.raises(ValueError):
        to_local_day(naive)


def test_to_local_day_respeta_la_zona_del_instante_de_entrada() -> None:
    # 23:30 en UTC-05:00 explícito sigue siendo el mismo día en Bogotá.
    moment = datetime(2026, 11, 3, 23, 30, tzinfo=timezone(timedelta(hours=-5)))
    assert to_local_day(moment) == "2026-11-03"


def test_to_local_day_acepta_otra_zona() -> None:
    moment = datetime(2026, 11, 4, 4, 59, tzinfo=UTC)
    assert to_local_day(moment, UTC_ZONE) == "2026-11-04"


def test_to_local_day_formato_iso_con_ceros() -> None:
    assert to_local_day(datetime(2026, 1, 2, 12, 0, tzinfo=UTC)) == "2026-01-02"


def test_to_local_day_cambio_de_anio_en_bogota() -> None:
    # 1 de enero 04:59Z = 31 de diciembre 23:59 en Bogotá.
    assert to_local_day(datetime(2027, 1, 1, 4, 59, tzinfo=UTC)) == "2026-12-31"
    assert to_local_day(datetime(2027, 1, 1, 5, 0, tzinfo=UTC)) == "2027-01-01"


def test_to_local_day_con_fake_clock() -> None:
    clock: Clock = FakeClock(datetime(2026, 11, 4, 4, 59, tzinfo=UTC))
    assert to_local_day(clock.now()) == "2026-11-03"


def test_tz_es_america_bogota() -> None:
    assert str(TZ) == "America/Bogota"


# --- add_days ---------------------------------------------------------------------------------


def test_add_days_cambio_de_anio() -> None:
    assert add_days("2026-12-31", 1) == "2027-01-01"


def test_add_days_cero_no_cambia() -> None:
    assert add_days("2026-11-04", 0) == "2026-11-04"


def test_add_days_negativo() -> None:
    assert add_days("2026-03-01", -1) == "2026-02-28"


def test_add_days_bisiesto() -> None:
    assert add_days("2028-02-28", 1) == "2028-02-29"
    assert add_days("2028-02-29", 1) == "2028-03-01"


def test_add_days_intervalo_largo() -> None:
    assert add_days("2026-11-04", 30) == "2026-12-04"


# --- diff_days --------------------------------------------------------------------------------


def test_diff_days_fin_de_febrero_a_marzo_en_bisiesto() -> None:
    assert diff_days("2028-02-28", "2028-03-01") == 2


def test_diff_days_fin_de_febrero_a_marzo_en_anio_no_bisiesto() -> None:
    assert diff_days("2027-02-28", "2027-03-01") == 1


def test_diff_days_es_positivo_si_b_es_posterior() -> None:
    assert diff_days("2026-11-03", "2026-11-04") == 1


def test_diff_days_es_negativo_si_b_es_anterior() -> None:
    assert diff_days("2026-11-04", "2026-11-03") == -1


def test_diff_days_mismo_dia_es_cero() -> None:
    assert diff_days("2026-11-04", "2026-11-04") == 0


def test_diff_days_cruza_el_anio() -> None:
    assert diff_days("2026-12-31", "2027-01-01") == 1


def test_add_days_y_diff_days_son_inversas() -> None:
    for n in (-40, -1, 0, 1, 7, 366):
        assert diff_days("2026-11-04", add_days("2026-11-04", n)) == n

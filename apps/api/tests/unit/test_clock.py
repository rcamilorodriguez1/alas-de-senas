"""Tarea 0.7 — reloj del sistema y dependencia `get_clock` sustituible (D22, §15)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta, timezone
from typing import Annotated

import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from app.core.clock import SystemClock, get_clock
from app.domain.dates import Clock
from tests.fakes import FakeClock

START = datetime(2026, 11, 4, 4, 59, tzinfo=UTC)


# --- SystemClock ------------------------------------------------------------------------------


def test_system_clock_devuelve_utc_con_zona_horaria() -> None:
    moment = SystemClock().now()

    assert moment.tzinfo is not None
    assert moment.utcoffset() == timedelta(0)


def test_system_clock_da_la_hora_actual() -> None:
    before = datetime.now(UTC)
    moment = SystemClock().now()
    after = datetime.now(UTC)

    assert before <= moment <= after


def test_get_clock_devuelve_un_reloj_con_now() -> None:
    clock: Clock = get_clock()
    moment = clock.now()
    assert moment.tzinfo is not None
    assert moment.utcoffset() == timedelta(0)


# --- FakeClock (doble reutilizable) -----------------------------------------------------------


def test_fake_clock_cumple_el_protocolo_clock() -> None:
    clock: Clock = FakeClock(START)
    assert clock.now() == START


def test_fake_clock_avanza_horas_minutos_y_dias() -> None:
    clock = FakeClock(START)

    clock.advance(minutes=1)
    assert clock.now() == datetime(2026, 11, 4, 5, 0, tzinfo=UTC)

    clock.advance(hours=4)
    assert clock.now() == datetime(2026, 11, 4, 9, 0, tzinfo=UTC)

    clock.advance(days=1, hours=1, minutes=30)
    assert clock.now() == datetime(2026, 11, 5, 10, 30, tzinfo=UTC)


def test_fake_clock_no_avanza_solo() -> None:
    clock = FakeClock(START)
    assert clock.now() == clock.now() == START


def test_fake_clock_rechaza_datetime_sin_zona_horaria() -> None:
    with pytest.raises(ValueError):
        FakeClock(datetime(2026, 11, 4, 4, 59))  # noqa: DTZ001 — se prueba el rechazo


def test_fake_clock_acepta_otras_zonas() -> None:
    bogota = timezone(timedelta(hours=-5))
    clock = FakeClock(datetime(2026, 11, 3, 23, 59, tzinfo=bogota))
    assert clock.now() == datetime(2026, 11, 4, 4, 59, tzinfo=UTC)


# --- get_clock se sustituye con dependency_overrides (D22) ------------------------------------


def _build_app() -> FastAPI:
    app = FastAPI()

    @app.get("/now")
    def now(clock: Annotated[Clock, Depends(get_clock)]) -> dict[str, str]:
        return {"now": clock.now().isoformat()}

    return app


def test_sin_sustitucion_la_ruta_usa_el_reloj_del_sistema() -> None:
    client = TestClient(_build_app())
    before = datetime.now(UTC)
    value = datetime.fromisoformat(client.get("/now").json()["now"])
    after = datetime.now(UTC)

    assert value.utcoffset() == timedelta(0)
    assert before <= value <= after


def test_get_clock_se_sustituye_con_un_fake_clock() -> None:
    app = _build_app()
    fake = FakeClock(START)
    app.dependency_overrides[get_clock] = lambda: fake
    client = TestClient(app)

    assert client.get("/now").json() == {"now": START.isoformat()}

    fake.advance(hours=4)
    assert client.get("/now").json() == {"now": (START + timedelta(hours=4)).isoformat()}

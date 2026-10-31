"""Reloj del sistema y dependencia `get_clock`, sustituible en las pruebas (D22)."""

from __future__ import annotations

from datetime import UTC, datetime

from app.domain.dates import Clock


class SystemClock:
    def now(self) -> datetime:
        return datetime.now(UTC)


_SYSTEM_CLOCK = SystemClock()


def get_clock() -> Clock:
    return _SYSTEM_CLOCK

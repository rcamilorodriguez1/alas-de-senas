"""Dobles de prueba reutilizables en todas las fases."""

from __future__ import annotations

from datetime import datetime, timedelta


class FakeClock:
    """Reloj simulado que cumple el Protocol `app.domain.dates.Clock` (D22).

    Siempre devuelve un `datetime` con zona horaria y solo avanza cuando la prueba lo pide.
    """

    def __init__(self, start: datetime) -> None:
        if start.tzinfo is None or start.utcoffset() is None:
            raise ValueError("FakeClock requiere un datetime con zona horaria")
        self._now = start

    def now(self) -> datetime:
        return self._now

    def advance(
        self, *, days: float = 0, hours: float = 0, minutes: float = 0, seconds: float = 0
    ) -> None:
        delta = timedelta(days=days, hours=hours, minutes=minutes, seconds=seconds)
        if delta < timedelta(0):
            raise ValueError("FakeClock no retrocede: usa set() para fijar otra hora")
        self._now = self._now + delta

    def set(self, moment: datetime) -> None:
        if moment.tzinfo is None or moment.utcoffset() is None:
            raise ValueError("FakeClock requiere un datetime con zona horaria")
        self._now = moment

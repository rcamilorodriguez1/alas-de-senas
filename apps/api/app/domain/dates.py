"""Reloj y fechas de negocio en hora de Bogotá (§7.1)."""

from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Protocol
from zoneinfo import ZoneInfo

TZ = ZoneInfo("America/Bogota")  # requiere el paquete tzdata en Windows (B45)


class Clock(Protocol):
    def now(self) -> datetime: ...  # siempre con zona horaria (UTC)


def to_local_day(moment: datetime, tz: ZoneInfo = TZ) -> str:
    """Día local «YYYY-MM-DD» de un instante; lanza ValueError si no tiene zona horaria."""
    if moment.tzinfo is None or moment.utcoffset() is None:
        raise ValueError("Se requiere un datetime con zona horaria")
    return moment.astimezone(tz).date().isoformat()


def add_days(day: str, n: int) -> str:
    return (date.fromisoformat(day) + timedelta(days=n)).isoformat()


def diff_days(a: str, b: str) -> int:
    """Días desde `a` hasta `b` (positivo si `b` es posterior)."""
    return (date.fromisoformat(b) - date.fromisoformat(a)).days

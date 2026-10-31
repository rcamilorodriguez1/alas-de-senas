"""Reloj y fechas del dominio (§7.1). `to_local_day`, `add_days` y `diff_days`: tarea 1.1."""

from __future__ import annotations

from datetime import datetime
from typing import Protocol


class Clock(Protocol):
    def now(self) -> datetime: ...  # siempre con zona horaria (UTC)

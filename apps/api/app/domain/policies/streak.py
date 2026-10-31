"""Racha diaria con protectores (§7.5). Días como texto «YYYY-MM-DD» en hora de Bogotá."""

from __future__ import annotations

from dataclasses import dataclass, replace

from app.domain.dates import add_days, diff_days

FREEZE_COST = 50
MAX_FREEZES = 2


@dataclass(frozen=True, slots=True)
class Streak:
    current: int = 0
    longest: int = 0
    freezes_available: int = 0
    last_active_day: str | None = None


class StreakPolicy:
    def apply_activity(self, streak: Streak, today: str) -> Streak:
        last = streak.last_active_day
        if last == today:
            return streak
        gap = None if last is None else diff_days(last, today)
        if gap is not None and gap < 0:
            # Fecha anterior a la última actividad: reloj o zona horaria inconsistentes.
            return streak
        current = streak.current
        freezes = streak.freezes_available
        if gap is None or gap > 1 + freezes:
            current = 1
        else:
            freezes -= gap - 1  # gap == 1 no consume protectores
            current += 1
        return replace(
            streak,
            current=current,
            longest=max(streak.longest, current),
            freezes_available=freezes,
            last_active_day=today,
        )

    def display(self, streak: Streak, today: str) -> int:
        """Racha que se muestra hoy (solo lectura)."""
        if streak.last_active_day is None:
            return 0
        gap = diff_days(streak.last_active_day, today)
        if gap <= 1 or gap - 1 <= streak.freezes_available:
            return streak.current
        return 0

    def is_at_risk(self, streak: Streak, today: str) -> bool:
        """La última actividad fue ayer: aún no ha practicado hoy."""
        return streak.last_active_day == add_days(today, -1)

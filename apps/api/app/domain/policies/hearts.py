"""Vidas derivadas de la fecha de la última actualización (D24, §7.10)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

MAX_HEARTS = 5
REFILL_EVERY = timedelta(hours=4)
REFILL_COST = 30


@dataclass(frozen=True, slots=True)
class HeartsState:
    hearts: int
    updated_at: datetime | None  # None ⇒ lleno


class HeartsPolicy:
    def current(self, state: HeartsState, now: datetime) -> tuple[int, datetime | None]:
        """(vidas, cuándo llega la próxima); nunca escribe."""
        if state.hearts >= MAX_HEARTS or state.updated_at is None:
            return MAX_HEARTS, None
        gained = self._gained(state.updated_at, now)
        hearts = min(MAX_HEARTS, state.hearts + gained)
        if hearts == MAX_HEARTS:
            return hearts, None
        return hearts, state.updated_at + (gained + 1) * REFILL_EVERY

    def lose_one(self, state: HeartsState, now: datetime) -> HeartsState:
        hearts, _ = self.current(state, now)
        if hearts == MAX_HEARTS:
            return HeartsState(MAX_HEARTS - 1, now)  # empieza a contar la recarga
        return HeartsState(max(0, hearts - 1), self._anchor(state, now))

    def gain_one(self, state: HeartsState, now: datetime) -> HeartsState:
        """+1 (tope MAX_HEARTS), conservando el avance de la recarga en curso."""
        hearts, _ = self.current(state, now)
        if hearts + 1 >= MAX_HEARTS:
            return HeartsState(MAX_HEARTS, None)
        return HeartsState(hearts + 1, self._anchor(state, now))

    def refill(self, now: datetime) -> HeartsState:
        return HeartsState(MAX_HEARTS, None)

    @staticmethod
    def _gained(updated_at: datetime, now: datetime) -> int:
        # Un reloj atrasado (updated_at en el futuro) no suma vidas.
        return max(timedelta(0), now - updated_at) // REFILL_EVERY

    def _anchor(self, state: HeartsState, now: datetime) -> datetime:
        """`updated_at` tras sumar las vidas ya ganadas: conserva el avance de la recarga."""
        if state.updated_at is None:
            return now
        return state.updated_at + self._gained(state.updated_at, now) * REFILL_EVERY

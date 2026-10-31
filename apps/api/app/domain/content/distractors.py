"""Elección de opciones incorrectas por niveles de prioridad (§6.7), compartida con el repaso."""

from __future__ import annotations

import random
from collections.abc import Sequence
from typing import Protocol


class NamedSign(Protocol):
    @property
    def id(self) -> str: ...

    @property
    def word(self) -> str: ...


def pick_distractors[S: NamedSign](
    sign: S, tiers: Sequence[Sequence[S]], rng: random.Random, count: int
) -> list[S]:
    """Hasta `count` opciones incorrectas, recorriendo los niveles en orden.

    Nunca la correcta, nunca repetidas, nunca dos con el mismo `word`. Dentro de cada nivel el
    orden lo decide el rng (barajado estable con semilla de texto).
    """
    chosen: list[S] = []
    seen_ids = {sign.id}
    words = {sign.word.casefold()}
    for tier in tiers:
        candidates = list(tier)
        rng.shuffle(candidates)
        for candidate in candidates:
            if len(chosen) == count:
                return chosen
            if candidate.id in seen_ids or candidate.word.casefold() in words:
                continue
            chosen.append(candidate)
            seen_ids.add(candidate.id)
            words.add(candidate.word.casefold())
    return chosen

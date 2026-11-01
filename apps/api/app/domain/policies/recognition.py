"""Cuándo un reconocimiento de la cámara suma para «Ojo de colibrí» (§7.9, fila de §8.2)."""

from __future__ import annotations

from datetime import datetime, timedelta

MIN_CONFIDENCE = 0.7
SAME_SIGN_INTERVAL = timedelta(seconds=10)


def counts_for_eye(
    correct: bool, confidence: float, last_counted: datetime | None, now: datetime
) -> bool:
    """Solo si fue correcto, con confianza ≥ 0,7 y como máximo una vez por seña cada 10 s."""
    if not correct or confidence < MIN_CONFIDENCE:
        return False
    return last_counted is None or now - last_counted >= SAME_SIGN_INTERVAL

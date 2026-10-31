"""Ejercicios de una sesión de repaso (D23, §8.5)."""

from __future__ import annotations

import random
from collections.abc import Sequence
from dataclasses import dataclass

from app.domain.content.distractors import pick_distractors
from app.domain.enums import ExerciseType
from app.domain.exercises.models import (
    ExercisePayload,
    MeaningToVideoPayload,
    VideoToMeaningPayload,
)

DISTRACTORS = 3
MIN_OPTIONS = 2


@dataclass(frozen=True, slots=True)
class ReviewSign:
    id: str
    word: str
    category: str
    node_id: str | None
    node_order: int  # posición global del nodo (módulos → nodos); 0 si es solo de diccionario


@dataclass(frozen=True, slots=True)
class ReviewItem:
    id: str  # "R-01", "R-02"…
    type: ExerciseType
    sign_id: str
    payload: ExercisePayload


def build_review_items(
    due_sign_ids: Sequence[str],
    seen: Sequence[ReviewSign],
    session_id: str,
    all_signs: Sequence[ReviewSign] = (),
) -> list[ReviewItem]:
    """Un ejercicio por seña vencida, alternando VIDEO_TO_MEANING y MEANING_TO_VIDEO.

    Las opciones incorrectas salen solo de señas que el usuario ya vio (mismo nodo → misma
    categoría → resto). Solo si así quedan menos de 2 opciones se completa con `all_signs`.
    """
    rng = random.Random(f"review:{session_id}")  # noqa: S311 — barajado reproducible
    by_id = {sign.id: sign for sign in seen}
    items: list[ReviewItem] = []
    for i, sign_id in enumerate(due_sign_ids):
        sign = by_id.get(sign_id)
        if sign is None:
            raise ValueError(f"La seña vencida «{sign_id}» no está entre las señas vistas.")
        others = [s for s in seen if s.id != sign.id]
        tiers: list[Sequence[ReviewSign]] = [
            [s for s in others if sign.node_id is not None and s.node_id == sign.node_id],
            [s for s in others if s.category == sign.category],
            others,
        ]
        distractors = pick_distractors(sign, tiers, rng, DISTRACTORS)
        if len(distractors) + 1 < MIN_OPTIONS:
            fallback = [
                [s for s in all_signs if s.category == sign.category],
                list(all_signs),
            ]
            distractors += pick_distractors(sign, fallback, rng, MIN_OPTIONS - 1 - len(distractors))
        option_ids = [sign.id, *(d.id for d in distractors)]
        payload: ExercisePayload
        if i % 2 == 0:
            kind = ExerciseType.VIDEO_TO_MEANING
            payload = VideoToMeaningPayload(
                sign_id=sign.id, option_ids=option_ids, correct_id=sign.id
            )
        else:
            kind = ExerciseType.MEANING_TO_VIDEO
            payload = MeaningToVideoPayload(
                sign_id=sign.id, option_ids=option_ids, correct_id=sign.id
            )
        items.append(ReviewItem(id=f"R-{i + 1:02d}", type=kind, sign_id=sign.id, payload=payload))
    return items

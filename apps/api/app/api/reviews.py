"""Rutas del repaso evaluado por el servidor (§8.2, §8.5, D23). Solo validan, delegan y responden.

No existe ningún endpoint donde el cliente envíe sus aciertos.
"""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, status

from app.api.deps import ClockDep, CurrentUser, DbSession, SettingsDep
from app.schemas.lessons import AnswerIn
from app.schemas.reviews import (
    ReviewAnswerOut,
    ReviewCompletionOut,
    ReviewQueueOut,
    ReviewStartOut,
)
from app.services.review_service import ReviewService

router = APIRouter(tags=["reviews"])


def get_review_service(db: DbSession, clock: ClockDep, settings: SettingsDep) -> ReviewService:
    return ReviewService(db, clock, settings)


ReviewServiceDep = Annotated[ReviewService, Depends(get_review_service)]


@router.get("/reviews/queue", response_model=ReviewQueueOut)
def queue(user: CurrentUser, service: ReviewServiceDep) -> ReviewQueueOut:
    return service.get_queue(user.id)


@router.post(
    "/reviews/sessions", response_model=ReviewStartOut, status_code=status.HTTP_201_CREATED
)
def start_review(user: CurrentUser, service: ReviewServiceDep, db: DbSession) -> ReviewStartOut:
    result = service.start(user.id)
    db.commit()
    return result


@router.post("/review-sessions/{session_id}/answers", response_model=ReviewAnswerOut)
def answer_review(
    session_id: uuid.UUID,
    data: AnswerIn,
    user: CurrentUser,
    service: ReviewServiceDep,
    db: DbSession,
) -> ReviewAnswerOut:
    result = service.answer(user.id, session_id, data)
    db.commit()
    return result


@router.post("/review-sessions/{session_id}/complete", response_model=ReviewCompletionOut)
def complete_review(
    session_id: uuid.UUID, user: CurrentUser, service: ReviewServiceDep, db: DbSession
) -> ReviewCompletionOut:
    db.commit()  # libera la petición antes de abrir la sesión SERIALIZABLE (D21)
    return service.complete(user.id, session_id)

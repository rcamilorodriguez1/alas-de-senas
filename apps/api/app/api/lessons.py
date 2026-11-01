"""Rutas de la sesión de lección (§8.2, §8.3). Solo validan, delegan y responden."""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, status

from app.api.deps import ClockDep, CurrentUser, DbSession, SettingsDep
from app.schemas.lessons import AnswerIn, AnswerOut, LessonCompletionOut, LessonStartOut
from app.services.lesson_session_service import LessonSessionService

router = APIRouter(tags=["lessons"])


def get_lesson_service(
    db: DbSession, clock: ClockDep, settings: SettingsDep
) -> LessonSessionService:
    return LessonSessionService(db, clock, settings)


LessonServiceDep = Annotated[LessonSessionService, Depends(get_lesson_service)]


@router.post(
    "/lessons/{lesson_id}/sessions",
    response_model=LessonStartOut,
    status_code=status.HTTP_201_CREATED,
)
def start_session(
    lesson_id: str, user: CurrentUser, service: LessonServiceDep, db: DbSession
) -> LessonStartOut:
    result = service.start(user, lesson_id)
    db.commit()
    return result


@router.post("/lesson-sessions/{session_id}/answers", response_model=AnswerOut)
def answer(
    session_id: uuid.UUID,
    data: AnswerIn,
    user: CurrentUser,
    service: LessonServiceDep,
    db: DbSession,
) -> AnswerOut:
    result = service.answer(user, session_id, data)
    db.commit()
    return result


@router.post("/lesson-sessions/{session_id}/complete", response_model=LessonCompletionOut)
def complete(
    session_id: uuid.UUID, user: CurrentUser, service: LessonServiceDep, db: DbSession
) -> LessonCompletionOut:
    db.commit()  # libera la fila del usuario antes de abrir la sesión SERIALIZABLE (D21)
    return service.complete(user.id, session_id)

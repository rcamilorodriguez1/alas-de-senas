"""Rutas del seguimiento del progreso (§8.2). Solo validan, delegan y responden."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query

from app.api.deps import ClockDep, CurrentUser, DbSession
from app.schemas.progress import HistoryPageOut, ProgressSummaryOut, UnitsOut
from app.services.progress_service import ProgressService

router = APIRouter(prefix="/progress", tags=["progress"])


def get_progress_service(db: DbSession, clock: ClockDep) -> ProgressService:
    return ProgressService(db, clock)


ProgressServiceDep = Annotated[ProgressService, Depends(get_progress_service)]


@router.get("/summary", response_model=ProgressSummaryOut)
def summary(user: CurrentUser, service: ProgressServiceDep) -> ProgressSummaryOut:
    return service.get_summary(user)


@router.get("/history", response_model=HistoryPageOut)
def history(
    user: CurrentUser,
    service: ProgressServiceDep,
    page: Annotated[int, Query(ge=1, le=10_000)] = 1,
) -> HistoryPageOut:
    return service.get_history(user.id, page)


@router.get("/units", response_model=UnitsOut)
def units(user: CurrentUser, service: ProgressServiceDep) -> UnitsOut:
    return service.get_units(user.id)

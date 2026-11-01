"""Rutas de gamificación (§8.2). Solo validan, delegan y responden."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends

from app.api.deps import ClockDep, CurrentUser, DbSession, SettingsDep
from app.schemas.gamification import AchievementStatusOut, StatsOut
from app.services.gamification_service import GamificationService

router = APIRouter(prefix="/gamification", tags=["gamification"])


def get_gamification_service(
    db: DbSession, clock: ClockDep, settings: SettingsDep
) -> GamificationService:
    return GamificationService(db, clock, settings)


GamificationServiceDep = Annotated[GamificationService, Depends(get_gamification_service)]


@router.get("/stats", response_model=StatsOut)
def stats(user: CurrentUser, service: GamificationServiceDep) -> StatsOut:
    return service.get_stats(user)


@router.get("/achievements", response_model=list[AchievementStatusOut])
def achievements(user: CurrentUser, service: GamificationServiceDep) -> list[AchievementStatusOut]:
    return service.list_achievements(user.id)


@router.post("/streak-freeze", response_model=StatsOut)
def buy_streak_freeze(
    user: CurrentUser, service: GamificationServiceDep, db: DbSession
) -> StatsOut:
    result = service.buy_streak_freeze(user.id)
    db.commit()
    return result


@router.post("/hearts-refill", response_model=StatsOut)
def refill_hearts(user: CurrentUser, service: GamificationServiceDep, db: DbSession) -> StatsOut:
    result = service.refill_hearts(user.id)
    db.commit()
    return result

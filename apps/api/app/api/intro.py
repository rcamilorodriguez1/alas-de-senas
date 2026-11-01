"""Ruta pública del módulo introductorio (§8.2, R1.1)."""

from __future__ import annotations

from fastapi import APIRouter

from app.api.deps import DbSession, SettingsDep
from app.schemas.intro import IntroOut
from app.services.intro_service import IntroService

router = APIRouter(tags=["intro"])


@router.get("/intro", response_model=IntroOut)
def intro(db: DbSession, settings: SettingsDep) -> IntroOut:
    return IntroService(db, settings).get_intro()

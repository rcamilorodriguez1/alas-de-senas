"""Ruta de resultados de la cámara (§8.2). Recibe solo números: nunca imágenes ni video (R8.3)."""

from __future__ import annotations

from fastapi import APIRouter

from app.api.deps import ClockDep, CurrentUser, DbSession, SettingsDep
from app.core import rate_limit
from app.schemas.recognition import RecognitionIn, RecognitionOut
from app.services.recognition_service import RecognitionService

router = APIRouter(tags=["recognition"])


@router.post("/recognition/results", response_model=RecognitionOut)
def register_result(
    data: RecognitionIn, user: CurrentUser, db: DbSession, clock: ClockDep, settings: SettingsDep
) -> RecognitionOut:
    rate_limit.check_recognition(str(user.id))
    result = RecognitionService(db, clock, settings).register_result(user.id, data)
    db.commit()
    return result

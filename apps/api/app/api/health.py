"""`GET /api/health`: la API responde y la base de datos también."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Response
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.infra.db import get_db
from app.infra.repositories.health import database_ping

router = APIRouter(tags=["health"])


class HealthOut(BaseModel):
    ok: bool
    db: bool


@router.get(
    "/health",
    response_model=HealthOut,
    responses={503: {"model": HealthOut, "description": "La base de datos no responde"}},
)
def health(db: Annotated[Session, Depends(get_db)], response: Response) -> HealthOut:
    if database_ping(db):
        return HealthOut(ok=True, db=True)
    response.status_code = 503
    return HealthOut(ok=False, db=False)

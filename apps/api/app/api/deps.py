"""Dependencias compartidas por los routers: sesión, reloj, configuración y usuario actual."""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends, Request
from sqlalchemy.orm import Session

from app.core import rate_limit
from app.core.clock import get_clock
from app.core.config import Settings, get_settings
from app.core.errors import unauthorized
from app.core.security import decode_access_token
from app.domain.dates import Clock
from app.infra.db import get_db
from app.infra.models import User
from app.services.auth_service import AuthService

DbSession = Annotated[Session, Depends(get_db)]
ClockDep = Annotated[Clock, Depends(get_clock)]
SettingsDep = Annotated[Settings, Depends(get_settings)]


def get_auth_service(db: DbSession, clock: ClockDep, settings: SettingsDep) -> AuthService:
    return AuthService(db, clock, settings)


AuthServiceDep = Annotated[AuthService, Depends(get_auth_service)]


def current_user(request: Request, service: AuthServiceDep) -> User:
    """Usuario del token `Authorization: Bearer …`; aplica el límite por usuario (B64)."""
    header = request.headers.get("authorization", "")
    scheme, _, token = header.partition(" ")
    if scheme.lower() != "bearer" or not token:
        raise unauthorized()
    claims = decode_access_token(token, service.clock.now(), service.settings.jwt_secret)
    if claims is None:
        raise unauthorized()
    rate_limit.check_user(str(claims.user_id))
    return service.get_user(claims.user_id)


CurrentUser = Annotated[User, Depends(current_user)]


def optional_user(request: Request, service: AuthServiceDep) -> User | None:
    """Usuario si envía token (un token inválido sigue siendo 401); None si no envía ninguno."""
    if not request.headers.get("authorization"):
        return None
    return current_user(request, service)


OptionalUser = Annotated[User | None, Depends(optional_user)]


def client_ip(request: Request) -> str:
    return request.client.host if request.client else "desconocida"

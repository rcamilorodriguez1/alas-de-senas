"""Rutas de autenticación y del usuario (§8.2). Solo validan, delegan y responden."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Cookie, Request, Response, status

from app.api.deps import AuthServiceDep, CurrentUser, DbSession, client_ip
from app.core import rate_limit
from app.schemas.auth import AuthOut, LoginIn, MeUpdateIn, RegisterIn, UserOut
from app.services.auth_service import AuthResult

router = APIRouter(tags=["auth"])

REFRESH_COOKIE = "rt"
REFRESH_COOKIE_PATH = "/api/auth"
RefreshCookie = Annotated[str | None, Cookie(alias=REFRESH_COOKIE)]


def _respond(result: AuthResult, response: Response, service: AuthServiceDep) -> AuthOut:
    response.set_cookie(
        REFRESH_COOKIE,
        result.refresh_token,
        max_age=service.settings.refresh_token_days * 24 * 3600,
        path=REFRESH_COOKIE_PATH,
        httponly=True,
        samesite="lax",
        secure=service.settings.is_production,
    )
    return AuthOut(
        access_token=result.access_token,
        user=UserOut.model_validate(result.user, from_attributes=True),
    )


@router.post("/auth/register", response_model=AuthOut, status_code=status.HTTP_201_CREATED)
def register(
    data: RegisterIn, request: Request, response: Response, service: AuthServiceDep, db: DbSession
) -> AuthOut:
    rate_limit.check_register(client_ip(request))
    result = service.register(data)
    db.commit()
    return _respond(result, response, service)


@router.post("/auth/login", response_model=AuthOut)
def login(
    data: LoginIn, request: Request, response: Response, service: AuthServiceDep, db: DbSession
) -> AuthOut:
    rate_limit.check_login(client_ip(request), data.email)
    result = service.login(data)
    db.commit()
    return _respond(result, response, service)


@router.post("/auth/refresh", response_model=AuthOut)
def refresh(
    response: Response, service: AuthServiceDep, db: DbSession, rt: RefreshCookie = None
) -> AuthOut:
    result = service.refresh(rt)
    db.commit()
    return _respond(result, response, service)


@router.post("/auth/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(
    response: Response, service: AuthServiceDep, db: DbSession, rt: RefreshCookie = None
) -> Response:
    service.logout(rt)
    db.commit()
    response.status_code = status.HTTP_204_NO_CONTENT
    response.delete_cookie(
        REFRESH_COOKIE,
        path=REFRESH_COOKIE_PATH,
        httponly=True,
        samesite="lax",
        secure=service.settings.is_production,
    )
    return response


@router.get("/me", response_model=UserOut)
def me(user: CurrentUser) -> UserOut:
    return UserOut.model_validate(user, from_attributes=True)


@router.patch("/me", response_model=UserOut)
def update_me(
    data: MeUpdateIn, user: CurrentUser, service: AuthServiceDep, db: DbSession
) -> UserOut:
    updated = service.update_me(user, data)
    db.commit()
    return UserOut.model_validate(updated, from_attributes=True)

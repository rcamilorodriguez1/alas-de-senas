"""Rutas de autenticación y del usuario (§8.2). Solo validan, delegan y responden."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Cookie, Request, Response, status

from app.api.deps import AuthServiceDep, ClockDep, CurrentUser, DbSession, client_ip
from app.core import rate_limit
from app.core.errors import AppError, error_response
from app.schemas.account import AccountExportOut, DeleteAccountIn
from app.schemas.auth import AuthOut, AvatarIn, LoginIn, MeUpdateIn, RegisterIn, UserOut
from app.services.account_service import AccountService
from app.services.auth_service import AuthResult
from app.services.avatar_service import AvatarService

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
) -> AuthOut | Response:
    try:
        result = service.refresh(rt)
    except AppError as exc:
        # Cookie inválida o vencida: se borra para que el navegador no la reenvíe en cada carga.
        failed = error_response(exc.status_code, exc.code, exc.message, exc.extra)
        _delete_cookie(failed, service)
        return failed
    db.commit()
    return _respond(result, response, service)


@router.post("/auth/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(
    response: Response, service: AuthServiceDep, db: DbSession, rt: RefreshCookie = None
) -> Response:
    service.logout(rt)
    db.commit()
    response.status_code = status.HTTP_204_NO_CONTENT
    _delete_cookie(response, service)
    return response


def _delete_cookie(response: Response, service: AuthServiceDep) -> None:
    response.delete_cookie(
        REFRESH_COOKIE,
        path=REFRESH_COOKIE_PATH,
        httponly=True,
        samesite="lax",
        secure=service.settings.is_production,
    )


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


# ---------- Datos personales (Ley 1581 de 2012: acceso y supresión, D-022) ---------------------


@router.get("/me/export", response_model=AccountExportOut)
def export_me(user: CurrentUser, db: DbSession, clock: ClockDep) -> AccountExportOut:
    return AccountService(db, clock).export_data(user)


@router.delete("/me", status_code=status.HTTP_204_NO_CONTENT)
def delete_me(
    data: DeleteAccountIn,
    request: Request,
    user: CurrentUser,
    service: AuthServiceDep,
    db: DbSession,
    clock: ClockDep,
) -> Response:
    # Mismo límite que el ingreso: la contraseña no se puede adivinar por fuerza bruta.
    rate_limit.check_login(client_ip(request), user.email)
    AccountService(db, clock).delete_account(user, data.password)
    db.commit()
    response = Response(status_code=status.HTTP_204_NO_CONTENT)
    _delete_cookie(response, service)
    return response


# ---------- Foto de perfil (D-023) ----------------------------------------------------------------


@router.put("/me/avatar", response_model=UserOut)
def set_avatar(data: AvatarIn, user: CurrentUser, db: DbSession, clock: ClockDep) -> UserOut:
    updated = AvatarService(db, clock).set_avatar(user, data.image)
    db.commit()
    return UserOut.model_validate(updated, from_attributes=True)


@router.get("/me/avatar", response_class=Response)
def get_avatar(user: CurrentUser, db: DbSession, clock: ClockDep) -> Response:
    data = AvatarService(db, clock).get_avatar(user)
    # Dato personal: solo el dueño la pide (con su token) y no se guarda en cachés compartidas.
    return Response(
        content=data, media_type="image/webp", headers={"Cache-Control": "private, no-store"}
    )


@router.delete("/me/avatar", response_model=UserOut)
def remove_avatar(user: CurrentUser, db: DbSession, clock: ClockDep) -> UserOut:
    updated = AvatarService(db, clock).remove_avatar(user)
    db.commit()
    return UserOut.model_validate(updated, from_attributes=True)

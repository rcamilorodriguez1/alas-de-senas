"""Casos de uso de autenticación (§8.1, §11). Los tiempos los fija el Clock (D22)."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import timedelta

from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.errors import AppError, unauthorized
from app.core.privacy import DATA_POLICY_VERSION
from app.core.security import (
    create_access_token,
    hash_password,
    hash_refresh_token,
    new_refresh_token,
    verify_password,
)
from app.domain.dates import Clock
from app.infra.models import RefreshToken, Role, User
from app.schemas.auth import LoginIn, MeUpdateIn, RegisterIn
from app.services.gamification_service import GamificationService


def _invalid_credentials() -> AppError:
    return AppError(401, "INVALID_CREDENTIALS", "Correo o contraseña incorrectos")


@dataclass(frozen=True, slots=True)
class AuthResult:
    access_token: str
    refresh_token: str
    user: User


class AuthService:
    def __init__(self, session: Session, clock: Clock, settings: Settings) -> None:
        self.session = session
        self.clock = clock
        self.settings = settings

    def register(self, data: RegisterIn) -> AuthResult:
        user = User(
            name=data.name,
            email=data.email,
            password_hash=hash_password(data.password),
            role=Role.LEARNER,
            daily_goal_minutes=data.daily_goal_minutes,
            # Prueba de la autorización (Ley 1581): la hora la fija el servidor (D22).
            data_policy_accepted_at=self.clock.now(),
            data_policy_version=DATA_POLICY_VERSION,
        )
        self.session.add(user)
        try:
            self.session.flush()
        except IntegrityError as exc:
            self.session.rollback()
            raise AppError(409, "EMAIL_TAKEN", "Ya existe una cuenta con este correo") from exc
        if data.intro_completed:
            GamificationService(self.session, self.clock, self.settings).grant_intro(user)
        return self._issue(user)

    def login(self, data: LoginIn) -> AuthResult:
        user = self.session.execute(
            select(User).where(User.email == data.email)
        ).scalar_one_or_none()
        # Se compara siempre (hash ficticio si el correo no existe): mismo tiempo, B28.
        valid = verify_password(data.password, user.password_hash if user else None)
        if user is None or not valid:
            raise _invalid_credentials()
        return self._issue(user)

    def refresh(self, token: str | None) -> AuthResult:
        """Rota el token de renovación: revoca el anterior y emite uno nuevo (§11)."""
        if not token:
            raise unauthorized()
        now = self.clock.now()
        stored = self.session.execute(
            select(RefreshToken)
            .where(RefreshToken.token_hash == hash_refresh_token(token))
            .with_for_update()
        ).scalar_one_or_none()
        if stored is None or stored.revoked_at is not None or stored.expires_at <= now:
            raise unauthorized()
        stored.revoked_at = now
        user = self.session.get(User, stored.user_id)
        if user is None:
            raise unauthorized()
        return self._issue(user)

    def logout(self, token: str | None) -> None:
        if not token:
            return
        self.session.execute(
            update(RefreshToken)
            .where(RefreshToken.token_hash == hash_refresh_token(token))
            .where(RefreshToken.revoked_at.is_(None))
            .values(revoked_at=self.clock.now())
        )

    def get_user(self, user_id: uuid.UUID) -> User:
        user = self.session.get(User, user_id)
        if user is None:
            raise unauthorized()
        return user

    def update_me(self, user: User, data: MeUpdateIn) -> User:
        changes = data.model_dump(exclude_unset=True, exclude_none=True)
        for field, value in changes.items():
            setattr(user, field, value)
        self.session.flush()
        return user

    def _issue(self, user: User) -> AuthResult:
        now = self.clock.now()
        refresh, refresh_hash = new_refresh_token()
        self.session.add(
            RefreshToken(
                user_id=user.id,
                token_hash=refresh_hash,
                expires_at=now + timedelta(days=self.settings.refresh_token_days),
            )
        )
        self.session.flush()
        access = create_access_token(
            user.id,
            user.role.value,
            now,
            self.settings.access_token_minutes,
            self.settings.jwt_secret,
        )
        return AuthResult(access_token=access, refresh_token=refresh, user=user)

"""Esquemas de autenticación y del usuario (§8.2)."""

from __future__ import annotations

import re
import uuid
from typing import Literal

from pydantic import Field, field_validator

from app.core.security import LENGTH_RULE_TEXT, password_size_ok
from app.schemas.common import ApiModel

_EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
DailyGoal = Literal[5, 10, 15, 20]
DominantHand = Literal["right", "left"]


def normalize_email(value: str) -> str:
    return value.strip().lower()  # B17


class _EmailIn(ApiModel):
    email: str = Field(max_length=254)

    @field_validator("email", mode="after")
    @classmethod
    def _valid_email(cls, value: str) -> str:
        value = normalize_email(value)
        if not _EMAIL.match(value):
            raise ValueError("Correo no válido")
        return value


class RegisterIn(_EmailIn):
    name: str = Field(min_length=1, max_length=80)
    password: str
    daily_goal_minutes: DailyGoal
    accepted_data_policy: bool
    intro_completed: bool = False  # se usa en la tarea 9.2 (logro «Primer aleteo»)

    @field_validator("name", mode="after")
    @classmethod
    def _strip_name(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Escribe tu nombre.")
        return value

    @field_validator("password", mode="after")
    @classmethod
    def _password_size(cls, value: str) -> str:
        if not password_size_ok(value):
            raise ValueError(LENGTH_RULE_TEXT)
        return value

    @field_validator("accepted_data_policy", mode="after")
    @classmethod
    def _accepted(cls, value: bool) -> bool:
        if not value:
            raise ValueError("Debes aceptar la política de tratamiento de datos.")
        return value


class LoginIn(_EmailIn):
    password: str = Field(max_length=512)


class UserOut(ApiModel):
    id: uuid.UUID
    name: str
    email: str
    role: Literal["LEARNER", "ADMIN"]
    daily_goal_minutes: int
    dominant_hand: str


class AuthOut(ApiModel):
    access_token: str
    user: UserOut


class MeUpdateIn(ApiModel):
    name: str | None = Field(default=None, min_length=1, max_length=80)
    daily_goal_minutes: DailyGoal | None = None
    dominant_hand: DominantHand | None = None

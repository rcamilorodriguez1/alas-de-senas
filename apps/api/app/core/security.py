"""Contraseñas, tokens de acceso (JWT) y de renovación (§11)."""

from __future__ import annotations

import hashlib
import secrets
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta

import bcrypt
import jwt

BCRYPT_ROUNDS = 12
JWT_ALGORITHM = "HS256"
MIN_PASSWORD_BYTES = 8
MAX_PASSWORD_BYTES = 72  # bcrypt no admite más (B27)
LENGTH_RULE_TEXT = "La contraseña debe tener entre 8 y 72 bytes (las tildes y la ñ cuentan doble)."

# Hash con el que se compara cuando el correo no existe: el login tarda lo mismo (B28).
_DUMMY_HASH = bcrypt.hashpw(b"contrasena-ficticia-para-tiempo", bcrypt.gensalt(BCRYPT_ROUNDS))


def password_size_ok(password: str) -> bool:
    return MIN_PASSWORD_BYTES <= len(password.encode("utf-8")) <= MAX_PASSWORD_BYTES


def hash_password(password: str) -> str:
    hashed = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt(BCRYPT_ROUNDS))
    return hashed.decode("utf-8")


def verify_password(password: str, password_hash: str | None) -> bool:
    """Compara siempre (contra el hash ficticio si no hay usuario) para no revelar por tiempo
    qué correos existen."""
    candidate = password.encode("utf-8")
    too_long = len(candidate) > MAX_PASSWORD_BYTES
    if too_long or not password_hash:
        # Ninguna contraseña registrada pasa de 72 bytes: se compara contra el hash ficticio
        # (mismo tiempo) y se rechaza. Truncar dejaría entrar con «contraseña + cualquier cosa».
        bcrypt.checkpw(candidate[:MAX_PASSWORD_BYTES], _DUMMY_HASH)
        return False
    return bcrypt.checkpw(candidate, password_hash.encode("utf-8"))


@dataclass(frozen=True, slots=True)
class AccessClaims:
    user_id: uuid.UUID
    role: str


def create_access_token(
    user_id: uuid.UUID, role: str, now: datetime, minutes: int, secret: str
) -> str:
    payload = {
        "sub": str(user_id),
        "role": role,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(minutes=minutes)).timestamp()),
    }
    return jwt.encode(payload, secret, algorithm=JWT_ALGORITHM)


def decode_access_token(token: str, now: datetime, secret: str) -> AccessClaims | None:
    """None si el token es inválido, vencido (según `now`, el Clock) o de otro algoritmo."""
    try:
        payload = jwt.decode(
            token,
            secret,
            algorithms=[JWT_ALGORITHM],  # explícito: rechaza «none» y otros algoritmos
            # exp se valida con el Clock (D22) abajo; iat no se usa (PyJWT lo compararía con la
            # hora real del sistema).
            options={"require": ["sub", "exp"], "verify_exp": False, "verify_iat": False},
        )
        expires = payload["exp"]
        if not isinstance(expires, int) or expires <= int(now.timestamp()):
            return None
        return AccessClaims(user_id=uuid.UUID(str(payload["sub"])), role=str(payload.get("role")))
    except (jwt.PyJWTError, ValueError, KeyError):
        return None


def new_refresh_token() -> tuple[str, str]:
    """(token para la cookie, SHA-256 hex que se guarda). Nunca se guarda el token."""
    token = secrets.token_urlsafe(32)
    return token, hash_refresh_token(token)


def hash_refresh_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()

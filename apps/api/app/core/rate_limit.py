"""Límites de peticiones (§11) con la librería `limits` (la misma que usa slowapi).

Login 5/min por IP + correo, registro 10/min por IP y rutas autenticadas 240/min por usuario
(no por IP: en la universidad muchos equipos comparten la IP pública, B64). Las constantes se
leen en cada llamada para poder ajustarlas en las pruebas.
"""

from __future__ import annotations

from limits import parse
from limits.storage import MemoryStorage
from limits.strategies import MovingWindowRateLimiter

from app.core.errors import AppError

LOGIN_LIMIT = "5/minute"
REGISTER_LIMIT = "10/minute"
USER_LIMIT = "240/minute"
RECOGNITION_LIMIT = "60/minute"  # §8.2: resultados de la cámara por usuario
TOO_MANY_MESSAGE = "Demasiados intentos, espera un minuto"

_storage = MemoryStorage()
_limiter = MovingWindowRateLimiter(_storage)


def _hit(limit: str, *keys: str) -> None:
    if not _limiter.hit(parse(limit), *keys):
        raise AppError(429, "TOO_MANY_REQUESTS", TOO_MANY_MESSAGE)


def check_login(ip: str, email: str) -> None:
    _hit(LOGIN_LIMIT, "login", ip, email)


def check_register(ip: str) -> None:
    _hit(REGISTER_LIMIT, "register", ip)


def check_user(user_id: str) -> None:
    _hit(USER_LIMIT, "user", user_id)


def check_recognition(user_id: str) -> None:
    _hit(RECOGNITION_LIMIT, "recognition", user_id)


def reset_rate_limits() -> None:
    _storage.reset()

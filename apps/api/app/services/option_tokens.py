"""Tokens opacos de las opciones (D20): el cliente nunca recibe IDs de seña.

token = HMAC_SHA256(clave, «sesión:ejercicio:lado:valor»)[:10] con clave = sha256(«option-tokens:»
+ JWT_SECRET). Es determinista: para evaluar se recalculan, no se guardan.
"""

from __future__ import annotations

import hashlib
import hmac

from app.domain.exercises.models import Tokenize

TOKEN_LENGTH = 10


def _key(secret: str) -> bytes:
    return hashlib.sha256(b"option-tokens:" + secret.encode("utf-8")).digest()


def make_tokenizer(secret: str, session_id: str, exercise_id: str) -> Tokenize:
    key = _key(secret)

    def tokenize(side: str, value: str) -> str:
        message = f"{session_id}:{exercise_id}:{side}:{value}".encode()
        return hmac.new(key, message, hashlib.sha256).hexdigest()[:TOKEN_LENGTH]

    return tokenize

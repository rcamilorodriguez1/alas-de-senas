"""Foto de perfil (D-023): valida, recorta y re-codifica la imagen antes de guardarla.

Re-codificar quita los metadatos (EXIF, ubicación GPS de los celulares) y garantiza que lo
guardado sea una imagen real, aunque el cliente envíe otra cosa.
"""

from __future__ import annotations

import base64
import binascii
import io

from PIL import Image, ImageOps, UnidentifiedImageError
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.domain.dates import Clock
from app.infra.models import User

MAX_BYTES = 300 * 1024
MAX_SIDE = 4096  # evita «bombas» de descompresión
SIZE = 256
ALLOWED_FORMATS = {"JPEG", "PNG", "WEBP"}


def _invalid(message: str) -> AppError:
    return AppError(422, "INVALID_IMAGE", message)


def normalize_avatar(encoded: str) -> bytes:
    """base64 → WebP de 256 x 256 recortada al centro, sin metadatos. Lanza 422 si no sirve."""
    try:
        raw = base64.b64decode(encoded, validate=True)
    except (binascii.Error, ValueError) as exc:
        raise _invalid("La imagen no llegó bien. Elige otra.") from exc
    if len(raw) > MAX_BYTES:
        raise _invalid("La imagen pesa demasiado (máximo 300 KB después de reducirla).")
    try:
        with Image.open(io.BytesIO(raw)) as source:
            if source.format not in ALLOWED_FORMATS:
                raise _invalid("Usa una imagen JPG, PNG o WebP.")
            if max(source.size) > MAX_SIDE:
                raise _invalid("La imagen es demasiado grande.")
            image = ImageOps.exif_transpose(source).convert("RGB")
    except (UnidentifiedImageError, OSError) as exc:
        raise _invalid("El archivo no es una imagen válida.") from exc
    square = ImageOps.fit(image, (SIZE, SIZE), method=Image.Resampling.LANCZOS)
    out = io.BytesIO()
    square.save(out, format="WEBP", quality=85)  # sin exif: se descartan los metadatos
    return out.getvalue()


class AvatarService:
    def __init__(self, session: Session, clock: Clock) -> None:
        self.session = session
        self.clock = clock

    def set_avatar(self, user: User, encoded: str) -> User:
        user.avatar = normalize_avatar(encoded)
        user.avatar_updated_at = self.clock.now()
        self.session.flush()
        return user

    def remove_avatar(self, user: User) -> User:
        user.avatar = None
        user.avatar_updated_at = None
        self.session.flush()
        return user

    def get_avatar(self, user: User) -> bytes:
        data = self.session.execute(select(User.avatar).where(User.id == user.id)).scalar_one()
        if data is None:
            raise AppError(404, "AVATAR_NOT_FOUND", "Aún no tienes foto de perfil.")
        return data

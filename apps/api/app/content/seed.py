"""`alas db seed`: carga idempotente del contenido con INSERT … ON CONFLICT DO UPDATE (D4, §6.4)."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from sqlalchemy.orm import Session


@dataclass(frozen=True, slots=True)
class SeedCounts:
    categories: int
    modules: int
    nodes: int
    lessons: int
    signs: int
    exercises: int
    achievements: int


def seed_content(
    session: Session,
    content_dir: Path,
    media_dir: Path,
    *,
    admin_email: str | None = None,
    admin_password: str | None = None,
) -> SeedCounts:
    """Upsert de categorías, módulos, nodos (también de módulos no publicados), lecciones y
    ejercicios generados (solo módulos publicados), señas (video_path, poster_path,
    is_placeholder y media_source desde el MANIFIESTO, nunca desde raw/; introduced_in_lesson_id
    según el generador) y logros. Borra los ejercicios que el generador ya no produce (sus
    respuestas caen por CASCADE); nunca borra lecciones, usuarios ni sesiones (R9.7).
    Administrador opcional (rol ADMIN) si se dan correo y contraseña (bcrypt, costo 12).
    ContentError si falta una seña en el manifiesto. No hace commit (lo hace quien llama).
    Devuelve los conteos de filas de contenido tras la carga.
    """
    raise NotImplementedError

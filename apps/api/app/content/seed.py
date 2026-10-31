"""`alas db seed`: carga idempotente del contenido con INSERT … ON CONFLICT DO UPDATE (D4, §6.4)."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path

import bcrypt
from sqlalchemy import Table, delete, func, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.content.errors import ContentError
from app.content.loader import CATEGORIES, load_content, to_sign_specs
from app.content.media import load_manifest
from app.domain.content.generator import generate_content
from app.domain.exercises.models import dump_payload
from app.domain.policies.achievements import ACHIEVEMENTS
from app.domain.text import normalize_text
from app.infra.models import (
    Achievement,
    ActivityKind,
    Base,
    Category,
    Exercise,
    Lesson,
    Module,
    Node,
    Role,
    Sign,
    User,
)

BCRYPT_ROUNDS = 12
ACTIVITY_KINDS: Mapping[int, ActivityKind] = {
    1: ActivityKind.OBSERVE,
    2: ActivityKind.SELECT,
    3: ActivityKind.PRODUCE,
    4: ActivityKind.USE,
}
# Descripción e ícono (lucide-react) de cada logro de §7.9.
ACHIEVEMENT_DETAILS: Mapping[str, tuple[str, str]] = {
    "FIRST_FLAP": ("Completaste la introducción a la LSC.", "feather"),
    "FIRST_LESSON": ("Aprobaste tu primera lección.", "graduation-cap"),
    "STREAK_3": ("Practicaste 3 días seguidos.", "flame"),
    "STREAK_7": ("Practicaste 7 días seguidos.", "calendar-check"),
    "NODE_DONE": ("Aprobaste tu primer reto final.", "flag"),
    "GOLDEN_NODE": ("Obtuviste 100 % en un reto final.", "crown"),
    "MODULE_1": ("Aprobaste todas las lecciones del módulo 1.", "award"),
    "SIGNS_50": ("Respondiste bien 50 señas distintas.", "hand"),
    "HUMMINGBIRD_EYE": ("Lograste 20 reconocimientos correctos con la cámara.", "eye"),
}


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
    bundle = load_content(content_dir)
    manifest = load_manifest(media_dir)
    missing = [row.slug for row in bundle.signs if row.slug not in manifest.signs]
    if missing:
        raise ContentError(
            f"Falta el video de «{missing[0]}» en el manifiesto ({len(missing)} en total). "
            "Ejecuta alas content all."
        )
    content = generate_content(
        [record.spec for record in bundle.modules],
        to_sign_specs(bundle.signs),
        bundle.conversations,
    )
    introduced = {
        sign_id: lesson.id
        for lesson in content.lessons
        if lesson.order <= 3
        for sign_id in lesson.sign_ids
    }

    # Los UNIQUE de `order` se revisan fila por fila: si el equipo reordena módulos o nodos,
    # el upsert chocaría con el valor viejo de otra fila. Se mueven a negativos primero.
    session.execute(update(Module).values(order=-Module.order).where(Module.order > 0))
    session.execute(update(Node).values(order=-Node.order).where(Node.order > 0))
    session.execute(update(Category).values(order=-Category.order).where(Category.order > 0))
    _upsert(
        session,
        Category,
        [
            {"id": cid, "name": name, "order": order}
            for order, (cid, name) in enumerate(CATEGORIES, start=1)
        ],
    )
    _upsert(
        session,
        Module,
        [
            {
                "id": r.spec.id,
                "order": r.spec.order,
                "title": r.spec.title,
                "description": r.description,
                "published": r.spec.published,
            }
            for r in bundle.modules
        ],
    )
    _upsert(
        session,
        Node,
        [
            {"id": n.id, "module_id": r.spec.id, "order": n.order, "title": n.title, "kind": n.kind}
            for r in bundle.modules
            for n in r.spec.nodes
        ],
    )
    _upsert(
        session,
        Lesson,
        [
            {
                "id": les.id,
                "node_id": les.node_id,
                "order": les.order,
                "type": les.type,
                "title": les.title,
            }
            for les in content.lessons
        ],
    )
    _upsert(
        session,
        Sign,
        [
            {
                "id": row.slug,
                "word": row.word,
                "normalized_word": normalize_text(row.word),
                "meaning": row.meaning,
                "how_to": row.how_to,
                "usage_example": row.usage_example,
                "category_id": row.category,
                "node_id": row.node,
                "introduced_in_lesson_id": introduced.get(row.slug),
                "order": row.order,
                "motion": row.motion,
                "video_path": manifest.signs[row.slug].video,
                "poster_path": manifest.signs[row.slug].poster,
                "is_placeholder": manifest.signs[row.slug].placeholder,
                "media_source": manifest.signs[row.slug].source,
            }
            for row in bundle.signs
        ],
    )
    exercise_ids = [e.id for e in content.exercises]
    # Ejercicios que el generador ya no produce: sus respuestas caen por CASCADE (§5). El id
    # («<lección>-NN») fija la posición, así que (lesson_id, order) nunca choca al reescribir.
    session.execute(delete(Exercise).where(Exercise.id.not_in(exercise_ids)))
    _upsert(
        session,
        Exercise,
        [
            {
                "id": e.id,
                "lesson_id": e.lesson_id,
                "order": e.order,
                "activity": ACTIVITY_KINDS[e.activity],
                "type": e.type,
                "sign_id": e.sign_id,
                "scored": e.scored,
                "payload": dump_payload(e.payload),
            }
            for e in content.exercises
        ],
    )
    _upsert(
        session,
        Achievement,
        [
            {
                "id": rule.id,
                "title": rule.title,
                "description": ACHIEVEMENT_DETAILS[rule.id][0],
                "icon": ACHIEVEMENT_DETAILS[rule.id][1],
                "nectar_reward": rule.nectar_reward,
                "order": order,
            }
            for order, rule in enumerate(ACHIEVEMENTS, start=1)
        ],
    )
    if admin_email and admin_password:
        _upsert_admin(session, admin_email, admin_password)
    session.flush()
    return SeedCounts(
        categories=_count(session, Category),
        modules=_count(session, Module),
        nodes=_count(session, Node),
        lessons=_count(session, Lesson),
        signs=_count(session, Sign),
        exercises=_count(session, Exercise),
        achievements=_count(session, Achievement),
    )


def _upsert(session: Session, model: type[Base], rows: Sequence[Mapping[str, object]]) -> None:
    """INSERT … ON CONFLICT (pk) DO UPDATE de todas las columnas (D4: recargar no duplica)."""
    if not rows:
        return
    table = model.__table__
    if not isinstance(table, Table):
        raise TypeError(f"{model.__name__} no está mapeado a una tabla")
    keys = [column.name for column in table.primary_key.columns]
    statement = insert(table).values(list(rows))
    updates = {name: statement.excluded[name] for name in rows[0] if name not in keys}
    session.execute(statement.on_conflict_do_update(index_elements=keys, set_=updates))


def _upsert_admin(session: Session, email: str, password: str) -> None:
    """Crea el administrador o actualiza su contraseña. Nunca asciende una cuenta existente:
    si alguien se registró con ADMIN_EMAIL, sería una escalada de privilegios (§11)."""
    normalized = email.strip().lower()
    password_hash = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt(BCRYPT_ROUNDS)).decode(
        "utf-8"
    )
    existing = session.execute(
        select(User).where(User.email == normalized).with_for_update()
    ).scalar_one_or_none()
    if existing is None:
        session.add(
            User(
                name="Administrador",
                email=normalized,
                password_hash=password_hash,
                role=Role.ADMIN,
            )
        )
        return
    if existing.role is not Role.ADMIN:
        raise ContentError(
            f"Ya existe un usuario con el correo {normalized} y no es administrador. "
            "Cambia ADMIN_EMAIL; por seguridad, el seed no le da permisos de administrador."
        )
    existing.password_hash = password_hash


def _count(session: Session, model: type[Base]) -> int:
    return session.execute(select(func.count()).select_from(model)).scalar_one()

"""Consultas del diccionario (§8.2): búsqueda, categorías, ficha y favoritos."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import ColumnElement, delete, func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.infra.models import Category, Favorite, Lesson, Module, Node, Sign


def escape_like(term: str) -> str:
    """Escapa los comodines de LIKE para buscar el texto tal cual (`\\` es el escape)."""
    return term.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def search(
    session: Session, term: str, category: str | None, offset: int, limit: int
) -> tuple[list[tuple[Sign, Category]], int]:
    conditions: list[ColumnElement[bool]] = []
    if term:
        conditions.append(Sign.normalized_word.ilike(f"%{escape_like(term)}%", escape="\\"))
    if category:
        conditions.append(Sign.category_id == category)
    total = session.execute(select(func.count(Sign.id)).where(*conditions)).scalar_one()
    statement = (
        select(Sign, Category)
        .join(Category, Sign.category_id == Category.id)
        .where(*conditions)
        .order_by(Sign.normalized_word, Sign.id)
        .offset(offset)
        .limit(limit)
    )
    return [(row[0], row[1]) for row in session.execute(statement)], total


def all_words(session: Session, category: str | None) -> list[tuple[str, str, str]]:
    """(slug, palabra, palabra normalizada) para las sugerencias."""
    statement = select(Sign.id, Sign.word, Sign.normalized_word).order_by(Sign.id)
    if category:
        statement = statement.where(Sign.category_id == category)
    return [(row[0], row[1], row[2]) for row in session.execute(statement)]


def categories_with_signs(session: Session) -> list[tuple[Category, int]]:
    statement = (
        select(Category, func.count(Sign.id))
        .join(Sign, Sign.category_id == Category.id)
        .group_by(Category.id)
        .order_by(Category.order, Category.id)
    )
    return [(row[0], row[1]) for row in session.execute(statement)]


def get_sign(session: Session, slug: str) -> tuple[Sign, Category] | None:
    row = session.execute(
        select(Sign, Category)
        .join(Category, Sign.category_id == Category.id)
        .where(Sign.id == slug)
    ).first()
    return (row[0], row[1]) if row else None


def published_lesson(session: Session, lesson_id: str) -> Lesson | None:
    statement = (
        select(Lesson)
        .join(Node, Lesson.node_id == Node.id)
        .join(Module, Node.module_id == Module.id)
        .where(Lesson.id == lesson_id, Module.published.is_(True))
    )
    return session.execute(statement).scalar_one_or_none()


def is_favorite(session: Session, user_id: uuid.UUID, slug: str) -> bool:
    return session.get(Favorite, (user_id, slug)) is not None


def favorites(session: Session, user_id: uuid.UUID) -> list[tuple[Sign, Category]]:
    statement = (
        select(Sign, Category)
        .join(Favorite, Favorite.sign_id == Sign.id)
        .join(Category, Sign.category_id == Category.id)
        .where(Favorite.user_id == user_id)
        .order_by(Favorite.created_at.desc(), Sign.id)
    )
    return [(row[0], row[1]) for row in session.execute(statement)]


def add_favorite(session: Session, user_id: uuid.UUID, slug: str, created_at: datetime) -> None:
    session.execute(
        insert(Favorite)
        .values(user_id=user_id, sign_id=slug, created_at=created_at)
        .on_conflict_do_nothing(index_elements=["user_id", "sign_id"])
    )


def remove_favorite(session: Session, user_id: uuid.UUID, slug: str) -> None:
    session.execute(delete(Favorite).where(Favorite.user_id == user_id, Favorite.sign_id == slug))

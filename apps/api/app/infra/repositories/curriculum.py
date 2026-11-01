"""Consultas del currículo y de los hechos de progreso de un usuario (§8.1, sin N+1)."""

from __future__ import annotations

import uuid
from collections.abc import Mapping
from dataclasses import dataclass

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.infra.models import LessonSession, Module, Node, Sign


@dataclass(frozen=True, slots=True)
class LessonFacts:
    best_score: int | None
    passed: bool


def load_curriculum(session: Session) -> list[Module]:
    """Módulos → nodos → lecciones en tres consultas (selectinload), siempre ordenados (B8)."""
    statement = (
        select(Module)
        .options(selectinload(Module.nodes).selectinload(Node.lessons))
        .order_by(Module.order)
    )
    return list(session.execute(statement).scalars().all())


def lesson_facts(session: Session, user_id: uuid.UUID) -> Mapping[str, LessonFacts]:
    """Hechos guardados (D3): mejor puntaje y si alguna vez aprobó, por lección completada."""
    statement = (
        select(
            LessonSession.lesson_id,
            func.max(LessonSession.score),
            func.bool_or(LessonSession.passed),
        )
        .where(LessonSession.user_id == user_id, LessonSession.completed_at.is_not(None))
        .group_by(LessonSession.lesson_id)
        .order_by(LessonSession.lesson_id)
    )
    return {
        lesson_id: LessonFacts(best_score=best, passed=bool(passed))
        for lesson_id, best, passed in session.execute(statement).tuples()
    }


def node_signs(session: Session, node_id: str) -> list[Sign]:
    statement = select(Sign).where(Sign.node_id == node_id).order_by(Sign.order, Sign.id)
    return list(session.execute(statement).scalars().all())

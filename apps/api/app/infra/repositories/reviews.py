"""Consultas de la sesión de repaso (§8.5): cola, señas vistas, sesiones y respuestas."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.domain.content.review_builder import ReviewSign
from app.domain.policies.review import SignReview as ReviewState
from app.infra.models import Module, Node, ReviewAnswer, ReviewSession, Sign, SignReview


def user_reviews(session: Session, user_id: uuid.UUID) -> list[ReviewState]:
    statement = select(SignReview).where(SignReview.user_id == user_id).order_by(SignReview.sign_id)
    return [
        ReviewState(row.sign_id, row.strength, row.next_review_day)
        for row in session.execute(statement).scalars()
    ]


def words(session: Session, sign_ids: list[str]) -> dict[str, str]:
    if not sign_ids:
        return {}
    statement = select(Sign.id, Sign.word).where(Sign.id.in_(sign_ids)).order_by(Sign.id)
    return dict(session.execute(statement).tuples().all())


def review_signs(session: Session) -> list[ReviewSign]:
    """Todas las señas con la posición global de su nodo (módulos → nodos); 0 sin nodo."""
    nodes = session.execute(
        select(Node.id).join(Module, Node.module_id == Module.id).order_by(Module.order, Node.order)
    ).scalars()
    node_order = {node_id: index for index, node_id in enumerate(nodes, start=1)}
    rows = session.execute(select(Sign).order_by(Sign.id)).scalars()
    return [
        ReviewSign(
            id=sign.id,
            word=sign.word,
            category=sign.category_id,
            node_id=sign.node_id,
            node_order=node_order.get(sign.node_id, 0) if sign.node_id else 0,
        )
        for sign in rows
    ]


def open_session(session: Session, user_id: uuid.UUID) -> ReviewSession | None:
    """La sesión de repaso sin completar más reciente del usuario."""
    statement = (
        select(ReviewSession)
        .where(ReviewSession.user_id == user_id, ReviewSession.completed_at.is_(None))
        .order_by(ReviewSession.started_at.desc(), ReviewSession.id.desc())
        .limit(1)
    )
    return session.execute(statement).scalar_one_or_none()


def get_user_session(
    session: Session, session_id: uuid.UUID, user_id: uuid.UUID, *, for_update: bool = False
) -> ReviewSession | None:
    statement = select(ReviewSession).where(
        ReviewSession.id == session_id, ReviewSession.user_id == user_id
    )
    if for_update:
        statement = statement.with_for_update(key_share=True).execution_options(
            populate_existing=True
        )
    return session.execute(statement).scalar_one_or_none()


def insert_answer(
    session: Session,
    session_id: uuid.UUID,
    item_id: str,
    answer: dict[str, object],
    correct: bool,
    answered_at: datetime,
) -> bool:
    """Primer intento: ON CONFLICT DO NOTHING RETURNING. True solo si se insertó."""
    statement = (
        insert(ReviewAnswer)
        .values(
            session_id=session_id,
            item_id=item_id,
            answer=answer,
            correct=correct,
            answered_at=answered_at,
        )
        .on_conflict_do_nothing(index_elements=["session_id", "item_id"])
        .returning(ReviewAnswer.item_id)
    )
    return session.execute(statement).first() is not None


def get_answer(session: Session, session_id: uuid.UUID, item_id: str) -> ReviewAnswer | None:
    return session.get(ReviewAnswer, (session_id, item_id))


def session_answers(session: Session, session_id: uuid.UUID) -> dict[str, ReviewAnswer]:
    statement = (
        select(ReviewAnswer)
        .where(ReviewAnswer.session_id == session_id)
        .order_by(ReviewAnswer.item_id)
    )
    return {row.item_id: row for row in session.execute(statement).scalars()}

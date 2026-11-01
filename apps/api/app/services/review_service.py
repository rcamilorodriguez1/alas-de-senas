"""Sesión de repaso evaluada por el servidor (§8.5, D23).

Reutiliza los evaluadores y los tokens opacos de las lecciones. El cliente nunca declara sus
aciertos: solo envía respuestas, y el servidor las evalúa y reprograma las señas.
"""

from __future__ import annotations

import uuid
from collections.abc import Callable, Mapping, Sequence

from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.errors import AppError
from app.domain.content.review_builder import build_review_items
from app.domain.dates import Clock, to_local_day
from app.domain.enums import ExerciseType
from app.domain.exercises.evaluators import get_evaluator
from app.domain.exercises.models import ExercisePayload, dump_payload, parse_payload
from app.domain.policies.hearts import MAX_HEARTS, HeartsPolicy, HeartsState
from app.domain.policies.review import ReviewScheduler
from app.domain.policies.review import SignReview as ReviewState
from app.infra.models import ReviewAnswer, ReviewSession, User
from app.infra.repositories import gamification as gamification_repo
from app.infra.repositories import lessons as lessons_repo
from app.infra.repositories import reviews as repo
from app.schemas.lessons import AnswerIn
from app.schemas.reviews import (
    QueueSignOut,
    ReviewAnswerOut,
    ReviewCompletionOut,
    ReviewExerciseOut,
    ReviewQueueOut,
    ReviewStartOut,
)
from app.services.gamification_service import GamificationService
from app.services.lesson_session_service import (
    SESSION_TTL,
    with_serializable_retries,
)
from app.services.option_tokens import make_tokenizer

REVIEW_NOT_FOUND = ("SESSION_NOT_FOUND", "No encontramos este repaso.")
REVIEW_EXPIRED = "Este repaso pasó mucho tiempo abierto. Empecemos de nuevo."
HEART_THRESHOLD = 80  # % de aciertos para recuperar una vida (§7.10)


class ReviewService:
    def __init__(self, session: Session, clock: Clock, settings: Settings) -> None:
        self.session = session
        self.clock = clock
        self.settings = settings
        self.scheduler = ReviewScheduler()

    # ---- cola ----------------------------------------------------------------------------

    def get_queue(self, user_id: uuid.UUID) -> ReviewQueueOut:
        today = to_local_day(self.clock.now())
        reviews = repo.user_reviews(self.session, user_id)
        due_count = sum(1 for review in reviews if review.next_review_day <= today)
        due = self.scheduler.due(reviews, today)
        words = repo.words(self.session, [review.sign_id for review in due])
        return ReviewQueueOut(
            due=due_count, signs=[QueueSignOut(word=words[r.sign_id]) for r in due]
        )

    # ---- iniciar -------------------------------------------------------------------------

    def start(self, user_id: uuid.UUID) -> ReviewStartOut:
        now = self.clock.now()
        today = to_local_day(now)
        # Bloquea al usuario: dos inicios a la vez (StrictMode, doble clic) crean una sola sesión.
        if lessons_repo.lock_user(self.session, user_id) is None:
            raise AppError(404, *REVIEW_NOT_FOUND)
        current = repo.open_session(self.session, user_id)
        if current is not None and to_local_day(current.started_at) == today:
            return self._public(current)  # doble montaje de StrictMode (§8.5)
        if current is not None:
            # Una sesión abierta de otro día queda cerrada sin resultado: su `complete` da 409 y
            # las mismas señas no se reprograman ni dan vida dos veces (R6.8, D-014.8).
            current.completed_at = now
        reviews = repo.user_reviews(self.session, user_id)
        due = self.scheduler.due(reviews, today)
        if not due:
            raise AppError(409, "NO_REVIEWS_DUE", "No tienes señas por repasar hoy.")
        all_signs = repo.review_signs(self.session)
        seen_ids = {review.sign_id for review in reviews}
        record = ReviewSession(user_id=user_id, started_at=now, items=[])
        self.session.add(record)
        self.session.flush()
        items = build_review_items(
            [review.sign_id for review in due],
            [sign for sign in all_signs if sign.id in seen_ids],
            str(record.id),
            all_signs,
        )
        record.items = [
            {
                "id": item.id,
                "type": item.type.value,
                "signId": item.sign_id,
                "payload": dump_payload(item.payload),
            }
            for item in items
        ]
        self.session.flush()
        return self._public(record)

    # ---- responder -----------------------------------------------------------------------

    def answer(self, user_id: uuid.UUID, session_id: uuid.UUID, data: AnswerIn) -> ReviewAnswerOut:
        record = repo.get_user_session(self.session, session_id, user_id, for_update=True)
        if record is None:
            raise AppError(404, *REVIEW_NOT_FOUND)
        if record.completed_at is not None:
            raise AppError(409, "SESSION_COMPLETED", "Este repaso ya terminó.")
        self._check_open(record)
        item = next((i for i in record.items if i.get("id") == data.exercise_id), None)
        if item is None:
            raise AppError(404, "EXERCISE_NOT_FOUND", "Este ejercicio no es del repaso.")
        kind, payload = _item_payload(item)
        evaluator = get_evaluator(kind)
        try:
            answer = evaluator.parse_answer(data.answer)
        except ValidationError as exc:
            raise AppError(
                422, "VALIDATION_ERROR", "La respuesta no tiene el formato esperado."
            ) from exc
        tokenize = self._tokenizer(record.id, data.exercise_id)
        correct = evaluator.evaluate(payload, answer, tokenize)
        # El repaso nunca quita vidas (§7.10): solo se guarda el primer intento.
        inserted = repo.insert_answer(
            self.session, record.id, data.exercise_id, dict(data.answer), correct, self.clock.now()
        )
        if not inserted:
            stored = repo.get_answer(self.session, record.id, data.exercise_id)
            correct = stored.correct if stored is not None else correct
        self.session.flush()
        catalog = lessons_repo.sign_catalog(self.session, _option_signs(payload))
        feedback = evaluator.feedback(payload, catalog, tokenize)
        return ReviewAnswerOut(
            correct=correct,
            correct_token=feedback.tokens[0] if feedback.tokens else None,
            correct_tokens=list(feedback.tokens),
            correct_word=feedback.word,
            already_answered=not inserted,
        )

    # ---- completar -----------------------------------------------------------------------

    def complete(self, user_id: uuid.UUID, session_id: uuid.UUID) -> ReviewCompletionOut:
        """Sesión SERIALIZABLE propia con reintentos (D21), idempotente."""
        return with_serializable_retries(lambda db: self._complete_in(db, user_id, session_id))

    def _complete_in(
        self, db: Session, user_id: uuid.UUID, session_id: uuid.UUID
    ) -> ReviewCompletionOut:
        record = repo.get_user_session(db, session_id, user_id, for_update=True)
        if record is None:
            raise AppError(404, *REVIEW_NOT_FOUND)
        if record.completed_at is not None:
            if record.result is None:
                raise AppError(409, "SESSION_COMPLETED", "Este repaso ya terminó.")
            return ReviewCompletionOut.model_validate(record.result)
        self._check_open(record)
        answers = repo.session_answers(db, record.id)
        item_ids = [str(item.get("id")) for item in record.items]
        if any(item_id not in answers for item_id in item_ids):
            raise AppError(
                409, "SESSION_INCOMPLETE", "Responde todas las señas para terminar el repaso"
            )
        user = lessons_repo.lock_user(db, user_id)
        if user is None:
            raise AppError(404, *REVIEW_NOT_FOUND)

        now = self.clock.now()
        today = to_local_day(now)
        total = len(item_ids)
        correct = sum(1 for item_id in item_ids if answers[item_id].correct)
        self._reschedule(db, user_id, record.items, answers, today)
        gamification = GamificationService(db, self.clock, self.settings)
        elapsed = int((now - record.started_at).total_seconds())
        streak = gamification.register_activity(
            user_id, today, seconds=max(0, min(elapsed, 15 * 60)), kind="review"
        )
        hearts_gained = self._maybe_gain_heart(user, correct, total)
        new_achievements = gamification.evaluate_achievements(user)

        result = ReviewCompletionOut(
            correct=correct,
            total=total,
            score=correct * 100 // total if total else 0,
            streak=streak,
            hearts_gained=hearts_gained,
            new_achievements=new_achievements,
        )
        record.completed_at = now
        record.correct = correct
        record.total = total
        record.hearts_gained = hearts_gained
        record.result = result.model_dump(mode="json", by_alias=True)
        db.flush()
        return result

    # ---- apoyo ---------------------------------------------------------------------------

    def _reschedule(
        self,
        db: Session,
        user_id: uuid.UUID,
        items: Sequence[dict[str, object]],
        answers: Mapping[str, ReviewAnswer],
        today: str,
    ) -> None:
        sign_ids = [str(item.get("signId")) for item in items]
        stored = gamification_repo.sign_reviews(db, user_id, sign_ids)
        now = self.clock.now()
        for item in items:
            sign_id = str(item.get("signId"))
            answer = answers[str(item.get("id"))]
            row = stored.get(sign_id)
            previous = (
                ReviewState(sign_id, row.strength, row.next_review_day) if row is not None else None
            )
            correct = answer.correct
            review = self.scheduler.schedule(previous, sign_id, correct, today)
            gamification_repo.upsert_sign_review(
                db, user_id, sign_id, review.strength, review.next_review_day, now
            )

    def _maybe_gain_heart(self, user: User, correct: int, total: int) -> int:
        """+1 vida si acertó al menos el 80 % (sin redondeos: correct·100 ≥ 80·total)."""
        if not self.settings.hearts_enabled or total == 0:
            return 0
        if correct * 100 < HEART_THRESHOLD * total:
            return 0
        policy = HeartsPolicy()
        now = self.clock.now()
        state = HeartsState(user.hearts, user.hearts_updated_at)
        before, _ = policy.current(state, now)
        if before >= MAX_HEARTS:
            return 0
        after = policy.gain_one(state, now)
        user.hearts = after.hearts
        user.hearts_updated_at = after.updated_at
        return 1

    def _check_open(self, record: ReviewSession) -> None:
        if self.clock.now() - record.started_at > SESSION_TTL:
            raise AppError(410, "SESSION_EXPIRED", REVIEW_EXPIRED)

    def _public(self, record: ReviewSession) -> ReviewStartOut:
        parsed = [(str(item.get("id")), *_item_payload(item)) for item in record.items]
        signs: set[str] = set()
        for _, _, payload in parsed:
            signs |= _option_signs(payload)
        catalog = lessons_repo.sign_catalog(self.session, signs)
        return ReviewStartOut(
            session_id=record.id,
            exercises=[
                ReviewExerciseOut(
                    id=item_id,
                    type=kind,
                    content=get_evaluator(kind).to_public(
                        payload, catalog, self._tokenizer(record.id, item_id)
                    ),
                )
                for item_id, kind, payload in parsed
            ],
        )

    def _tokenizer(self, session_id: uuid.UUID, item_id: str) -> Callable[[str, str], str]:
        return make_tokenizer(self.settings.jwt_secret, str(session_id), item_id)


def _item_payload(item: dict[str, object]) -> tuple[ExerciseType, ExercisePayload]:
    payload = parse_payload(item.get("payload"))
    return ExerciseType(payload.type), payload


def _option_signs(payload: ExercisePayload) -> set[str]:
    signs = {getattr(payload, "sign_id", "")}
    signs.update(getattr(payload, "option_ids", []))
    signs.discard("")
    return signs

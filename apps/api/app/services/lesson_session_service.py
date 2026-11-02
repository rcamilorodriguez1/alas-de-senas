"""Sesión de lección: iniciar, responder y completar (§8.3, el corazón del sistema).

El servidor evalúa todo (D2): el cliente recibe opciones con tokens opacos (D20) y nunca la
respuesta correcta antes de contestar. Los tiempos los fija el Clock (D22).
"""

from __future__ import annotations

import time
import uuid
from collections.abc import Callable, Mapping, Sequence
from datetime import timedelta

from psycopg.errors import SerializationFailure
from pydantic import ValidationError
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.errors import AppError
from app.domain.dates import Clock
from app.domain.enums import LessonType, ProgressStatus
from app.domain.exercises.evaluators import get_evaluator
from app.domain.exercises.models import (
    ConversationPayload,
    ExercisePayload,
    MemoryMatchPayload,
    SpellingPayload,
    parse_payload,
)
from app.domain.policies.hearts import HeartsPolicy, HeartsState
from app.domain.policies.rewards import RewardPolicy
from app.domain.policies.scoring import score_session
from app.infra.db import serializable_session
from app.infra.models import Exercise, Lesson, LessonSession, User
from app.infra.repositories import lessons as repo
from app.schemas.lessons import (
    AnswerIn,
    AnswerOut,
    HeartsOut,
    LessonCompletionOut,
    LessonInfoOut,
    LessonStartOut,
    PublicExerciseOut,
    UnlockedOut,
)
from app.services.curriculum_service import CurriculumService
from app.services.gamification_service import GamificationService, hearts_out
from app.services.option_tokens import make_tokenizer

SESSION_TTL = timedelta(hours=24)
MAX_DURATION_SECONDS = 15 * 60  # B16: una pestaña abierta toda la noche no infla la meta
SERIALIZABLE_ATTEMPTS = 3


def _error(status: int, code: str, message: str) -> AppError:
    return AppError(status, code, message)


SESSION_NOT_FOUND = ("SESSION_NOT_FOUND", "No encontramos esta sesión de lección.")
EXPIRED_MESSAGE = "Esta lección se actualizó o pasó mucho tiempo. Empecemos de nuevo."


class LessonSessionService:
    def __init__(self, session: Session, clock: Clock, settings: Settings) -> None:
        self.session = session
        self.clock = clock
        self.settings = settings
        self.hearts = HeartsPolicy()
        self.rewards = RewardPolicy()

    # ---- iniciar -------------------------------------------------------------------------

    def start(self, user: User, lesson_id: str) -> LessonStartOut:
        found = repo.get_lesson(self.session, lesson_id)
        if found is None or not found[2].published:
            raise _error(404, "LESSON_NOT_FOUND", "No encontramos esta lección.")
        lesson, node, module = found
        progress = CurriculumService(self.session).progress_map(user.id)
        if progress.lessons.get(lesson.id, ProgressStatus.LOCKED) is ProgressStatus.LOCKED:
            raise _error(403, "LESSON_LOCKED", "Esta lección aún está bloqueada")
        now = self.clock.now()
        current, next_heart = self.hearts.current(self._hearts_state(user), now)
        if self.settings.hearts_enabled and lesson.type is not LessonType.LEARN and current == 0:
            raise AppError(
                403,
                "NO_HEARTS",
                "Te quedaste sin vidas por ahora.",
                extra={"nextHeartAt": next_heart.isoformat() if next_heart else None},
            )
        exercises = repo.lesson_exercises(self.session, lesson.id)
        record = LessonSession(
            user_id=user.id,
            lesson_id=lesson.id,
            started_at=now,
            exercises_hash=repo.exercises_fingerprint(exercises),
        )
        self.session.add(record)
        self.session.flush()
        previously = repo.has_passed_before(self.session, user.id, lesson.id, record.id)
        payloads = [parse_payload(e.payload) for e in exercises]
        catalog = repo.sign_catalog(self.session, _referenced_signs(payloads))
        groups = _groups(lesson, exercises)
        public = [
            PublicExerciseOut(
                id=exercise.id,
                order=exercise.order,
                activity=exercise.activity,
                type=exercise.type,
                scored=exercise.scored,
                group=groups.get(exercise.id),
                content=get_evaluator(exercise.type).to_public(
                    payload, catalog, self._tokenizer(record.id, exercise.id)
                ),
            )
            for exercise, payload in zip(exercises, payloads, strict=True)
        ]
        return LessonStartOut(
            session_id=record.id,
            lesson=LessonInfoOut(
                id=lesson.id,
                order=lesson.order,
                type=lesson.type,
                title=lesson.title,
                node_id=node.id,
                node_title=node.title,
                node_order=node.order,
                module_order=module.order,
                estimated_xp=self.rewards.max_xp(lesson.type, previously),
            ),
            exercises=public,
            hearts=self._hearts_out(user),
        )

    # ---- responder -----------------------------------------------------------------------

    def answer(self, user: User, session_id: uuid.UUID, data: AnswerIn) -> AnswerOut:
        # Mismo orden de bloqueos que `complete` (sesión → usuario): sin bloqueos mutuos, y una
        # sesión ya cerrada no acepta respuestas tardías.
        record = repo.get_user_session(self.session, session_id, user.id, for_update=True)
        if record is None:
            raise _error(404, *SESSION_NOT_FOUND)
        if record.completed_at is not None:
            raise _error(409, "SESSION_COMPLETED", "Esta lección ya terminó.")
        exercises = self._check_open(record)
        exercise = next((e for e in exercises if e.id == data.exercise_id), None)
        if exercise is None:
            raise _error(404, "EXERCISE_NOT_FOUND", "Este ejercicio no es de la lección.")
        payload = parse_payload(exercise.payload)
        evaluator = get_evaluator(exercise.type)
        try:
            answer = evaluator.parse_answer(data.answer)
        except ValidationError as exc:
            raise _error(
                422, "VALIDATION_ERROR", "La respuesta no tiene el formato esperado."
            ) from exc
        tokenize = self._tokenizer(record.id, exercise.id)
        correct = evaluator.evaluate(payload, answer, tokenize)

        locked_user = repo.lock_user(self.session, user.id)  # vidas sin carreras (§8.3.9)
        if locked_user is None:
            raise _error(404, *SESSION_NOT_FOUND)
        inserted = repo.insert_answer(
            self.session, record.id, exercise.id, dict(data.answer), correct, self.clock.now()
        )
        if inserted:
            lesson = self.session.get(Lesson, record.lesson_id)
            loses_heart = (
                not correct
                and exercise.scored
                and self.settings.hearts_enabled
                and lesson is not None
                and lesson.type is not LessonType.LEARN
            )
            if loses_heart:
                state = self.hearts.lose_one(self._hearts_state(locked_user), self.clock.now())
                locked_user.hearts = state.hearts
                locked_user.hearts_updated_at = state.updated_at
                record.hearts_lost += 1
        else:
            stored = repo.get_answer(self.session, record.id, exercise.id)
            correct = stored.correct if stored is not None else correct  # primer intento (B3)
        self.session.flush()
        catalog = repo.sign_catalog(self.session, _referenced_signs([payload]))
        feedback = evaluator.feedback(payload, catalog, tokenize)
        return AnswerOut(
            correct=correct,
            correct_token=feedback.tokens[0] if feedback.tokens else None,
            correct_tokens=list(feedback.tokens),
            correct_word=feedback.word,
            already_answered=not inserted,
            hearts=self._hearts_out(locked_user),
        )

    # ---- completar -----------------------------------------------------------------------

    def complete(self, user_id: uuid.UUID, session_id: uuid.UUID) -> LessonCompletionOut:
        """Sesión SERIALIZABLE propia (D21) con reintentos ante SerializationFailure."""
        return with_serializable_retries(lambda db: self._complete_in(db, user_id, session_id))

    def _complete_in(
        self, db: Session, user_id: uuid.UUID, session_id: uuid.UUID
    ) -> LessonCompletionOut:
        record = repo.get_user_session(db, session_id, user_id, for_update=True)
        if record is None:
            raise _error(404, *SESSION_NOT_FOUND)
        if record.completed_at is not None:
            if record.result is None:  # cerrada antes de guardar resultados: no se paga otra vez
                raise _error(409, "SESSION_COMPLETED", "Esta lección ya terminó.")
            return LessonCompletionOut.model_validate(record.result)  # idempotente (B2)
        exercises = self._check_open(record, db)
        answers = {a.exercise_id: a for a in repo.session_answers(db, record.id)}
        if any(exercise.id not in answers for exercise in exercises):
            raise _error(
                409, "SESSION_INCOMPLETE", "Responde todos los ejercicios para terminar la lección"
            )
        lesson = db.get(Lesson, record.lesson_id)
        user = repo.lock_user(db, user_id)
        if lesson is None or user is None:
            raise _error(404, *SESSION_NOT_FOUND)

        scored = [e for e in exercises if e.scored]
        correct = sum(1 for e in scored if answers[e.id].correct)
        score = score_session(correct, len(scored), lesson.type)
        previously = repo.has_passed_before(db, user_id, lesson.id, record.id)
        reward = self.rewards.calculate(lesson.type, score, previously)
        curriculum = CurriculumService(db)
        before = curriculum.progress_map(user_id).lessons

        now = self.clock.now()
        record.completed_at = now
        record.score = score.score
        record.correct = score.correct
        record.total = score.total
        record.passed = score.passed
        record.xp_earned = reward.xp
        record.nectar_earned = reward.nectar
        elapsed = int((now - record.started_at).total_seconds())
        record.duration_sec = max(0, min(elapsed, MAX_DURATION_SECONDS))
        user.total_xp += reward.xp
        user.nectar += reward.nectar
        db.flush()
        gamification = GamificationService(db, self.clock, self.settings).apply_completion(
            user, exercises, answers, seconds=record.duration_sec, xp=reward.xp
        )

        after = curriculum.progress_map(user_id).lessons
        unlocked = [
            UnlockedOut(type="LESSON", id=lesson_id)
            for lesson_id, status in after.items()
            if status is ProgressStatus.AVAILABLE and before.get(lesson_id) is ProgressStatus.LOCKED
        ]
        result = LessonCompletionOut(
            score=score.score,
            correct=score.correct,
            total=score.total,
            passed=score.passed,
            xp_earned=reward.xp,
            nectar_earned=reward.nectar,
            streak=gamification.streak,
            new_achievements=gamification.new_achievements,
            unlocked=unlocked,
            mascot_mood="cheer" if score.passed else "happy",
            mascot_message="¡Vas volando!"
            if score.passed
            else "¡Casi! Repasa las señas y vuelve a intentarlo.",
        )
        record.result = result.model_dump(mode="json", by_alias=True)
        return result

    # ---- apoyo ---------------------------------------------------------------------------

    def _check_open(self, record: LessonSession, db: Session | None = None) -> list[Exercise]:
        """410 si pasaron 24 h o si el contenido de la lección cambió desde que empezó."""
        session = db or self.session
        if self.clock.now() - record.started_at > SESSION_TTL:
            raise _error(410, "SESSION_EXPIRED", EXPIRED_MESSAGE)
        exercises = repo.lesson_exercises(session, record.lesson_id)
        if repo.exercises_fingerprint(exercises) != record.exercises_hash:
            raise _error(410, "SESSION_EXPIRED", EXPIRED_MESSAGE)
        return exercises

    def _tokenizer(self, session_id: uuid.UUID, exercise_id: str) -> Callable[[str, str], str]:
        return make_tokenizer(self.settings.jwt_secret, str(session_id), exercise_id)

    @staticmethod
    def _hearts_state(user: User) -> HeartsState:
        return HeartsState(hearts=user.hearts, updated_at=user.hearts_updated_at)

    def _hearts_out(self, user: User) -> HeartsOut:
        return hearts_out(user, self.clock, self.settings)


def with_serializable_retries[T](work: Callable[[Session], T]) -> T:
    for attempt in range(1, SERIALIZABLE_ATTEMPTS + 1):
        try:
            with serializable_session() as db:
                return work(db)
        except OperationalError as exc:
            if not isinstance(exc.orig, SerializationFailure) or attempt == SERIALIZABLE_ATTEMPTS:
                raise
            time.sleep(0.05 * attempt)  # espera corta antes de reintentar (§8.3.3)
    raise RuntimeError("inalcanzable")  # pragma: no cover


def _referenced_signs(payloads: Sequence[ExercisePayload]) -> set[str]:
    signs: set[str] = set()
    for payload in payloads:
        if isinstance(payload, ConversationPayload):
            for turn in payload.turns:
                signs.update([turn.prompt_id, *turn.option_ids])
        elif isinstance(payload, MemoryMatchPayload):
            signs.update(payload.sign_ids)
        elif isinstance(payload, SpellingPayload):
            signs.update(payload.letter_ids)
        else:
            signs.add(payload.sign_id)
            signs.update(getattr(payload, "option_ids", []))
    return signs


def _groups(lesson: Lesson, exercises: Sequence[Exercise]) -> Mapping[str, int]:
    """Agrupación por seña (§9.3) de L1 a L3; el reto final no se agrupa.

    Cada seña forma un bloque contiguo. Con el orden de D-021 (observar todas y luego recordar
    mezclado) los bloques son las observaciones; cuando vuelve una seña ya vista o aparece un
    ejercicio sin seña, empieza la parte de recordar, que no tiene grupo.
    """
    if lesson.type is LessonType.CHALLENGE:
        return {}
    order: dict[str, int] = {}
    groups: dict[str, int] = {}
    current: str | None = None
    for exercise in exercises:
        sign = exercise.sign_id
        if sign is None or (sign in order and sign != current):
            break
        current = sign
        groups[exercise.id] = order.setdefault(sign, len(order))
    return groups

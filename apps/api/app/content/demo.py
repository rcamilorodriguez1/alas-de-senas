"""Usuario de demostración (`alas db seed-demo`, §17.4, R10.9).

Deja una cuenta lista para la sustentación usando los servicios reales (registro, lecciones y
repaso) con un reloj simulado: así la demo nunca queda inconsistente con las reglas (D22). Las
respuestas las calcula el servidor con el payload y el secreto de los tokens, igual que haría un
usuario que acierta; la API nunca las revela (B89).
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.domain.dates import Clock, add_days, to_local_day
from app.domain.enums import ExerciseType
from app.domain.exercises.models import (
    SIDE_SPELLING,
    SIDE_VIDEO,
    SIDE_WORD,
    ConversationPayload,
    ExercisePayload,
    MeaningToVideoPayload,
    MemoryMatchPayload,
    ObservePayload,
    ProducePayload,
    SpellingPayload,
    Tokenize,
    VideoToMeaningPayload,
    parse_payload,
)
from app.infra.db import get_engine
from app.infra.models import Exercise, Lesson, ReviewSession, Sign, User
from app.infra.repositories import account as account_repo
from app.schemas.auth import RegisterIn
from app.schemas.lessons import AnswerIn
from app.services.auth_service import AuthService
from app.services.lesson_session_service import LessonSessionService
from app.services.option_tokens import make_tokenizer
from app.services.review_service import ReviewService

DEMO_DEV_PASSWORD = "demo-alas-2026"  # noqa: S105 — solo fuera de producción (§17.4)
DEMO_NAME = "Valentina"
START_HOUR = time(10, 0)  # cada día simulado empieza a las 10:00 de Bogotá (§17.4)
STEP = timedelta(seconds=20)  # tiempo simulado por respuesta
FAILED_LETTERS = 3
LETTERS_CATEGORY = "alfabeto"
# Ayer: 3 errores en 3 letras en la ÚLTIMA lección del día (una letra acertada después se
# reprogramaría y saldría de la cola). El reto tiene 12 con puntaje: 9/12 = 75 % ≥ 70 %, aprueba.
ERRORS_LESSON = "M1-N4-L4"
FIRST_LESSON = "M1-N1-L1"  # si no existe, falta `alas db seed`


@dataclass(frozen=True)
class _Day:
    days_ago: int
    lessons: tuple[str, ...]
    review: bool = False
    # «Necesito repasar» (sin puntaje) en una letra que ese día solo sale en una lección: vence
    # mañana y hace posible el repaso del día siguiente. Con todo acertado ninguna seña vencería
    # hace 2 días, porque cada lección del día la refuerza (§7.7, D-034).
    self_check: bool = False


# Plan de §17.4, en días antes de hoy.
PLAN: tuple[_Day, ...] = (
    _Day(5, ("M1-N1-L1", "M1-N1-L2", "M1-N1-L3", "M1-N1-L4")),
    _Day(4, ("M1-N2-L1", "M1-N2-L2", "M1-N2-L3", "M1-N2-L4")),
    _Day(3, ("M1-N3-L1", "M1-N3-L2", "M1-N3-L3", "M1-N3-L4"), self_check=True),
    _Day(2, ("M1-N4-L1", "M1-N4-L2"), review=True),
    _Day(1, ("M1-N4-L3", "M1-N4-L4")),
)


class DemoError(Exception):
    """La demo no se puede crear (producción sin permiso, contenido sin cargar…)."""


@dataclass(frozen=True)
class DemoResult:
    created: bool
    email: str


class _SimClock:
    """Reloj de la demo: se fija al inicio de cada día y avanza con cada paso."""

    def __init__(self, start: datetime) -> None:
        self._now = start

    def now(self) -> datetime:
        return self._now

    def set(self, moment: datetime) -> None:
        self._now = moment

    def tick(self) -> None:
        self._now = self._now + STEP


@dataclass
class _Mistakes:
    """Ejercicios que se responden mal a propósito: 3 letras distintas en `ERRORS_LESSON`."""

    remaining: int = FAILED_LETTERS
    signs: set[str] = field(default_factory=set)
    self_check: str | None = None  # seña con «Necesito repasar» pendiente de responder


def _password(settings: Settings, allow_production: bool) -> str:
    if settings.is_production:
        if not allow_production:
            raise DemoError(
                "En producción la demo solo se crea con --allow-production y DEMO_PASSWORD."
            )
        if settings.demo_password is None:
            raise DemoError("Define DEMO_PASSWORD para crear la demo en producción.")
        return settings.demo_password
    return settings.demo_password or DEMO_DEV_PASSWORD


def seed_demo(
    settings: Settings,
    clock: Clock,
    *,
    reset: bool = False,
    allow_production: bool = False,
) -> DemoResult:
    """Crea el usuario de demostración con fechas relativas a `clock.now()` (hoy)."""
    # Todo lo que puede fallar se valida antes de tocar la base de datos (B84).
    data = _register_data(settings, _password(settings, allow_production))
    email = data.email
    with Session(get_engine()) as session:
        if session.get(Lesson, FIRST_LESSON) is None:
            raise DemoError("No hay contenido cargado: ejecuta antes `uv run alas db seed`.")
        existing = session.execute(
            select(User.id, User.is_demo).where(User.email == email)
        ).one_or_none()
        if existing is not None and not existing.is_demo:
            # §17.4: nunca toca otros usuarios, ni siquiera con --reset.
            raise DemoError(
                f"{email} es una cuenta real, no la de demostración. Usa otro correo en DEMO_EMAIL."
            )
        if existing is not None and not reset:
            return DemoResult(created=False, email=email)
        if existing is not None:
            account_repo.delete_user(session, existing.id)  # ON DELETE CASCADE: su progreso
            session.commit()

    tz = ZoneInfo(settings.app_timezone)
    today = to_local_day(clock.now())
    sim = _SimClock(_day_start(add_days(today, -PLAN[0].days_ago), tz))
    user_id = _register(settings, sim, data)
    try:
        mistakes = _Mistakes()
        for day in PLAN:
            sim.set(_day_start(add_days(today, -day.days_ago), tz))
            if day.self_check:
                mistakes.self_check = _self_check_sign(day.lessons)
            for lesson_id in day.lessons:
                _play_lesson(settings, sim, user_id, lesson_id, mistakes)
            if day.review:
                _play_review(settings, sim, user_id)
    except Exception:
        # Sin demo a medias: la siguiente ejecución no debe decir «ya existe».
        with Session(get_engine()) as session:
            account_repo.delete_user(session, user_id)
            session.commit()
        raise
    return DemoResult(created=True, email=email)


def _day_start(day: str, tz: ZoneInfo) -> datetime:
    return datetime.combine(date.fromisoformat(day), START_HOUR, tzinfo=tz)


def _register_data(settings: Settings, password: str) -> RegisterIn:
    try:
        return RegisterIn.model_validate(
            {
                "name": DEMO_NAME,
                "email": settings.demo_email,
                "password": password,
                "dailyGoalMinutes": 10,
                "acceptedDataPolicy": True,
                "introCompleted": True,  # «Primer aleteo» (R1.6)
            }
        )
    except ValidationError as exc:
        fields = {str(error["loc"][0]) for error in exc.errors() if error["loc"]}
        name = "DEMO_PASSWORD" if "password" in fields else "DEMO_EMAIL"
        raise DemoError(
            f"{name} no es válido para crear la demo ({exc.error_count()} error)."
        ) from exc


def _register(settings: Settings, clock: _SimClock, data: RegisterIn) -> uuid.UUID:
    with Session(get_engine()) as session:
        user = AuthService(session, clock, settings).register(data).user
        user.is_demo = True
        session.commit()
        return user.id


def _play_lesson(
    settings: Settings, clock: _SimClock, user_id: uuid.UUID, lesson_id: str, mistakes: _Mistakes
) -> None:
    with Session(get_engine()) as session:
        user = session.get(User, user_id)
        if user is None:  # pragma: no cover — se acaba de crear
            raise DemoError("No se encontró el usuario de la demo.")
        service = LessonSessionService(session, clock, settings)
        started = service.start(user, lesson_id)
        letters = _letter_ids(session) if lesson_id == ERRORS_LESSON else set()
        for exercise in started.exercises:
            clock.tick()
            payload = _exercise_payload(session, exercise.id)
            tokenize = make_tokenizer(settings.jwt_secret, str(started.session_id), exercise.id)
            answer = _correct_answer(payload, tokenize)
            if lesson_id == ERRORS_LESSON:
                answer = _maybe_wrong(payload, tokenize, letters, mistakes) or answer
            elif isinstance(payload, ProducePayload) and payload.sign_id == mistakes.self_check:
                answer = {"method": "self", "ok": False}  # «Necesito repasar»
                mistakes.self_check = None
            service.answer(
                user,
                started.session_id,
                AnswerIn.model_validate({"exerciseId": exercise.id, "answer": answer}),
            )
        session.commit()
    clock.tick()
    with Session(get_engine()) as session:  # `complete` abre su sesión SERIALIZABLE (D21)
        LessonSessionService(session, clock, settings).complete(user_id, started.session_id)
    clock.tick()


def _play_review(settings: Settings, clock: _SimClock, user_id: uuid.UUID) -> None:
    with Session(get_engine()) as session:
        service = ReviewService(session, clock, settings)
        started = service.start(user_id)
        record = session.get(ReviewSession, started.session_id)
        if record is None:  # pragma: no cover — se acaba de crear
            raise DemoError("No se encontró el repaso de la demo.")
        payloads = {
            str(item.get("id")): parse_payload(item.get("payload")) for item in record.items
        }
        for exercise in started.exercises:
            clock.tick()
            tokenize = make_tokenizer(settings.jwt_secret, str(started.session_id), exercise.id)
            answer = _correct_answer(payloads[exercise.id], tokenize)
            service.answer(
                user_id,
                started.session_id,
                AnswerIn.model_validate({"exerciseId": exercise.id, "answer": answer}),
            )
        session.commit()
    clock.tick()
    with Session(get_engine()) as session:
        ReviewService(session, clock, settings).complete(user_id, started.session_id)
    clock.tick()


def _exercise_payload(session: Session, exercise_id: str) -> ExercisePayload:
    raw = session.execute(select(Exercise.payload).where(Exercise.id == exercise_id)).scalar_one()
    return parse_payload(raw)


def _self_check_sign(lessons: tuple[str, ...]) -> str:
    """Primera letra (por id) que el día solo aparece en una lección y allí tiene PRODUCE."""
    with Session(get_engine()) as session:
        rows = session.execute(
            select(Exercise.lesson_id, Exercise.sign_id, Exercise.type)
            .join(Sign, Sign.id == Exercise.sign_id)
            .where(Exercise.lesson_id.in_(lessons), Sign.category_id == LETTERS_CATEGORY)
            .order_by(Exercise.sign_id, Exercise.lesson_id)
        ).all()
    seen_in: dict[str, set[str]] = {}
    produce: set[str] = set()
    for lesson_id, sign_id, kind in rows:
        if sign_id is None:  # pragma: no cover — el join con Sign lo descarta
            continue
        seen_in.setdefault(sign_id, set()).add(lesson_id)
        if kind is ExerciseType.PRODUCE:
            produce.add(sign_id)
    candidates = sorted(s for s, found in seen_in.items() if len(found) == 1 and s in produce)
    if not candidates:
        raise DemoError("El contenido no tiene una letra para «Necesito repasar» (§17.4).")
    return candidates[0]


def _letter_ids(session: Session) -> set[str]:
    rows = session.execute(select(Sign.id).where(Sign.category_id == LETTERS_CATEGORY))
    return set(rows.scalars())


def _correct_answer(payload: ExercisePayload, tok: Tokenize) -> dict[str, object]:
    if isinstance(payload, ObservePayload):
        return {"watched": True}
    if isinstance(payload, VideoToMeaningPayload):
        return {"optionToken": tok(SIDE_WORD, payload.correct_id)}
    if isinstance(payload, MeaningToVideoPayload):
        return {"optionToken": tok(SIDE_VIDEO, payload.correct_id)}
    if isinstance(payload, MemoryMatchPayload):
        return {
            "attempts": [
                {"videoToken": tok(SIDE_VIDEO, s), "wordToken": tok(SIDE_WORD, s)}
                for s in payload.sign_ids
            ]
        }
    if isinstance(payload, ProducePayload):
        return {"method": "self", "ok": True}
    if isinstance(payload, ConversationPayload):
        return {"choices": [tok(SIDE_VIDEO, turn.correct_id) for turn in payload.turns]}
    if isinstance(payload, SpellingPayload):
        return {"optionToken": tok(SIDE_SPELLING, payload.word)}
    raise DemoError(f"Tipo de ejercicio sin respuesta para la demo: {payload.type}")


def _maybe_wrong(
    payload: ExercisePayload, tok: Tokenize, letters: set[str], mistakes: _Mistakes
) -> dict[str, object] | None:
    """Respuesta incorrecta para las primeras 3 letras distintas de selección simple."""
    if mistakes.remaining == 0 or not isinstance(payload, VideoToMeaningPayload):
        return None
    sign = payload.sign_id
    if sign not in letters or sign in mistakes.signs:
        return None
    other = next((o for o in payload.option_ids if o != payload.correct_id), None)
    if other is None:
        return None
    mistakes.signs.add(sign)
    mistakes.remaining -= 1
    return {"optionToken": tok(SIDE_WORD, other)}

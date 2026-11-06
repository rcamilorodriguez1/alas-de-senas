"""Modelos SQLAlchemy 2.0 (§5). Se guardan hechos; los estados se derivan (D3).

Tiempos de negocio en UTC con zona horaria, fijados por el servicio con `Clock` (D22): ningún
`server_default=func.now()` salvo `created_at` de auditoría. Días de negocio como «YYYY-MM-DD».
"""

from __future__ import annotations

import enum
import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    LargeBinary,
    MetaData,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

from app.domain.enums import ExerciseType, LessonType, NodeKind

# Nombres de restricciones estables: las migraciones autogeneradas no cambian entre equipos.
NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=NAMING_CONVENTION)


class Role(enum.StrEnum):
    LEARNER = "LEARNER"
    ADMIN = "ADMIN"


class ActivityKind(enum.StrEnum):
    OBSERVE = "OBSERVE"  # 1 Observa
    SELECT = "SELECT"  # 2 Reconoce
    PRODUCE = "PRODUCE"  # 3 Produce
    USE = "USE"  # 4 Conversa / deletrea


def _enum[E: enum.StrEnum](kind: type[E], name: str) -> Enum:
    # Guarda el valor (no el nombre) del StrEnum.
    return Enum(kind, name=name, values_callable=lambda members: [m.value for m in members])


# ---------- Contenido (cargado desde content/, IDs estables) ----------


class Module(Base):
    __tablename__ = "modules"
    id: Mapped[str] = mapped_column(String(8), primary_key=True)  # "M1"
    order: Mapped[int] = mapped_column(Integer, unique=True)
    title: Mapped[str] = mapped_column(String(120))
    description: Mapped[str] = mapped_column(Text)
    published: Mapped[bool] = mapped_column(Boolean, default=True)
    nodes: Mapped[list[Node]] = relationship(order_by="Node.order", viewonly=True)


class Node(Base):
    __tablename__ = "nodes"
    __table_args__ = (UniqueConstraint("module_id", "order"),)
    id: Mapped[str] = mapped_column(String(16), primary_key=True)  # "M1-N2"
    module_id: Mapped[str] = mapped_column(ForeignKey("modules.id"))
    order: Mapped[int]
    title: Mapped[str] = mapped_column(String(120))
    kind: Mapped[NodeKind] = mapped_column(_enum(NodeKind, "node_kind"), default=NodeKind.STANDARD)
    lessons: Mapped[list[Lesson]] = relationship(order_by="Lesson.order", viewonly=True)


class Lesson(Base):
    __tablename__ = "lessons"
    __table_args__ = (UniqueConstraint("node_id", "order"),)
    id: Mapped[str] = mapped_column(String(24), primary_key=True)  # "M1-N2-L3"
    node_id: Mapped[str] = mapped_column(ForeignKey("nodes.id"))
    order: Mapped[int]  # 1..4
    type: Mapped[LessonType] = mapped_column(_enum(LessonType, "lesson_type"))
    title: Mapped[str] = mapped_column(String(120))


class Category(Base):
    __tablename__ = "categories"
    id: Mapped[str] = mapped_column(String(32), primary_key=True)  # "saludos"
    name: Mapped[str] = mapped_column(String(64))
    order: Mapped[int]


class Sign(Base):
    __tablename__ = "signs"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)  # slug
    word: Mapped[str] = mapped_column(String(120))
    normalized_word: Mapped[str] = mapped_column(String(120), index=True)  # §7.8
    meaning: Mapped[str] = mapped_column(Text)
    how_to: Mapped[str | None] = mapped_column(Text)
    usage_example: Mapped[str] = mapped_column(Text)
    category_id: Mapped[str] = mapped_column(ForeignKey("categories.id"), index=True)
    node_id: Mapped[str | None] = mapped_column(ForeignKey("nodes.id"))
    introduced_in_lesson_id: Mapped[str | None] = mapped_column(ForeignKey("lessons.id"))
    order: Mapped[int] = mapped_column(default=0)
    motion: Mapped[str | None] = mapped_column(String(8))  # solo letras: static | dynamic
    video_path: Mapped[str] = mapped_column(String(255))  # "/media/v/<hash>.mp4" (D19)
    poster_path: Mapped[str] = mapped_column(String(255))
    is_placeholder: Mapped[bool] = mapped_column(default=True)
    media_source: Mapped[str] = mapped_column(String(12), default="placeholder")  # D25


class Exercise(Base):
    __tablename__ = "exercises"
    __table_args__ = (UniqueConstraint("lesson_id", "order"),)
    id: Mapped[str] = mapped_column(String(32), primary_key=True)  # "M1-N2-L2-04"
    lesson_id: Mapped[str] = mapped_column(ForeignKey("lessons.id", ondelete="CASCADE"))
    order: Mapped[int]
    activity: Mapped[ActivityKind] = mapped_column(_enum(ActivityKind, "activity_kind"))
    type: Mapped[ExerciseType] = mapped_column(_enum(ExerciseType, "exercise_type"))
    sign_id: Mapped[str | None] = mapped_column(ForeignKey("signs.id"))
    scored: Mapped[bool]
    payload: Mapped[dict[str, object]] = mapped_column(JSONB)  # validado con Pydantic (§7.6)


# ---------- Usuarios y sesión ----------


class User(Base):
    __tablename__ = "users"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(80))
    email: Mapped[str] = mapped_column(String(254), unique=True)  # minúsculas y sin espacios
    password_hash: Mapped[str] = mapped_column(String(100))
    role: Mapped[Role] = mapped_column(_enum(Role, "role"), default=Role.LEARNER)
    daily_goal_minutes: Mapped[int] = mapped_column(default=10)
    dominant_hand: Mapped[str] = mapped_column(String(5), default="right")
    total_xp: Mapped[int] = mapped_column(default=0)
    nectar: Mapped[int] = mapped_column(default=0)
    recognitions_correct: Mapped[int] = mapped_column(default=0)
    hearts: Mapped[int] = mapped_column(default=5)  # §7.10
    hearts_updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    is_demo: Mapped[bool] = mapped_column(default=False)  # §17.4
    # Foto de perfil (D-023): WebP de 256 x 256 re-codificada (sin metadatos); diferida para no
    # leerla en cada consulta del usuario.
    avatar: Mapped[bytes | None] = mapped_column(LargeBinary, deferred=True)
    avatar_updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # Autorización de tratamiento de datos (Ley 1581, D-037). Nula en cuentas anteriores a D-037.
    data_policy_accepted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    data_policy_version: Mapped[str | None] = mapped_column(String(20))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )  # auditoría (D22 lo permite)


class RefreshToken(Base):
    __tablename__ = "refresh_tokens"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)  # SHA-256, nunca el token
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


# ---------- Aprendizaje (hechos) ----------


class LessonSession(Base):
    __tablename__ = "lesson_sessions"
    __table_args__ = (
        Index("ix_sessions_user_lesson", "user_id", "lesson_id"),
        Index("ix_sessions_user_completed", "user_id", "completed_at"),
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    lesson_id: Mapped[str] = mapped_column(ForeignKey("lessons.id"))
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))  # Clock (D22)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    hearts_lost: Mapped[int] = mapped_column(default=0)
    # Huella de los ejercicios al empezar: si el contenido se recarga, la sesión expira (§8.3.8).
    exercises_hash: Mapped[str] = mapped_column(String(64), default="")
    # LessonCompletionResult guardado: el `complete` repetido devuelve lo mismo (R4.10).
    result: Mapped[dict[str, object] | None] = mapped_column(JSONB)
    score: Mapped[int | None]
    correct: Mapped[int | None]
    total: Mapped[int | None]
    passed: Mapped[bool | None]
    xp_earned: Mapped[int | None]
    nectar_earned: Mapped[int | None]
    duration_sec: Mapped[int | None]


class SessionAnswer(Base):
    __tablename__ = "session_answers"  # PK compuesta: cuenta el PRIMER intento (B3)
    session_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("lesson_sessions.id", ondelete="CASCADE"), primary_key=True
    )
    exercise_id: Mapped[str] = mapped_column(
        ForeignKey("exercises.id", ondelete="CASCADE"), primary_key=True
    )
    answer: Mapped[dict[str, object]] = mapped_column(JSONB)
    correct: Mapped[bool]
    answered_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))  # Clock (D22)


class ReviewSession(Base):  # D23, §8.5
    __tablename__ = "review_sessions"
    __table_args__ = (Index("ix_review_sessions_user", "user_id", "started_at"),)
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    items: Mapped[list[dict[str, object]]] = mapped_column(JSONB)  # con respuesta: solo servidor
    correct: Mapped[int | None]
    total: Mapped[int | None]
    hearts_gained: Mapped[int | None]
    # ReviewCompletionOut: el complete repetido devuelve exactamente lo mismo (idempotencia).
    result: Mapped[dict[str, object] | None] = mapped_column(JSONB)


class ReviewAnswer(Base):
    __tablename__ = "review_answers"  # PK compuesta: primer intento
    session_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("review_sessions.id", ondelete="CASCADE"), primary_key=True
    )
    item_id: Mapped[str] = mapped_column(String(8), primary_key=True)  # "R-01"
    answer: Mapped[dict[str, object]] = mapped_column(JSONB)
    correct: Mapped[bool]
    answered_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class DailyActivity(Base):
    __tablename__ = "daily_activity"
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    day: Mapped[str] = mapped_column(String(10), primary_key=True)  # "2026-11-03" (Bogotá)
    seconds: Mapped[int] = mapped_column(default=0)
    xp: Mapped[int] = mapped_column(default=0)
    lessons: Mapped[int] = mapped_column(default=0)
    reviews: Mapped[int] = mapped_column(default=0)


class Streak(Base):
    __tablename__ = "streaks"
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    current: Mapped[int] = mapped_column(default=0)
    longest: Mapped[int] = mapped_column(default=0)
    last_active_day: Mapped[str | None] = mapped_column(String(10))
    freezes_available: Mapped[int] = mapped_column(default=0)


class SignReview(Base):
    __tablename__ = "sign_reviews"
    __table_args__ = (Index("ix_reviews_user_next", "user_id", "next_review_day"),)
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    sign_id: Mapped[str] = mapped_column(ForeignKey("signs.id"), primary_key=True)
    strength: Mapped[int] = mapped_column(default=0)  # 0..5
    next_review_day: Mapped[str] = mapped_column(String(10))
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class Achievement(Base):
    __tablename__ = "achievements"
    id: Mapped[str] = mapped_column(String(32), primary_key=True)  # "FIRST_FLAP"
    title: Mapped[str] = mapped_column(String(80))
    description: Mapped[str] = mapped_column(Text)
    icon: Mapped[str] = mapped_column(String(40))
    nectar_reward: Mapped[int]
    order: Mapped[int]


class UserAchievement(Base):
    __tablename__ = "user_achievements"  # PK compuesta: imposible duplicar (B5)
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    achievement_id: Mapped[str] = mapped_column(ForeignKey("achievements.id"), primary_key=True)
    unlocked_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))  # Clock (D22)


class Favorite(Base):
    __tablename__ = "favorites"
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    sign_id: Mapped[str] = mapped_column(ForeignKey("signs.id"), primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

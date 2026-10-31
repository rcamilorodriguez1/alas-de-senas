"""Motor y sesiones de SQLAlchemy 2.0 (síncrono, D17)."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from functools import lru_cache

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import get_settings


@lru_cache
def get_engine() -> Engine:
    # pool pequeño y reciclado: Neon gratuito limita las conexiones (B53).
    return create_engine(
        get_settings().database_url,
        pool_pre_ping=True,
        pool_size=5,
        pool_recycle=300,
    )


def _session_factory(engine: Engine) -> sessionmaker[Session]:
    return sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def get_db() -> Iterator[Session]:
    """Dependencia de FastAPI: una sesión por petición."""
    session = _session_factory(get_engine())()
    try:
        yield session
    finally:
        session.close()


@contextmanager
def serializable_session() -> Iterator[Session]:
    """Sesión propia en SERIALIZABLE para cerrar lecciones y repasos (D21).

    El nivel de aislamiento se fija en la conexión antes de la primera consulta; por eso no se
    reutiliza la sesión de la petición, que ya consultó al usuario.
    """
    engine = get_engine().execution_options(isolation_level="SERIALIZABLE")
    session = _session_factory(engine)()
    try:
        yield session
        session.commit()
    except BaseException:
        session.rollback()
        raise
    finally:
        session.close()

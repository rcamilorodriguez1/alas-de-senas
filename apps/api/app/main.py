"""Crea la aplicación FastAPI: API bajo `/api` (D1)."""

from __future__ import annotations

from fastapi import FastAPI

from app.api import (
    auth,
    curriculum,
    dictionary,
    gamification,
    health,
    intro,
    lessons,
    progress,
    recognition,
    reviews,
)
from app.core.config import Settings, get_settings
from app.core.errors import register_error_handlers
from app.core.media_files import MediaFiles
from app.core.security_headers import SecurityHeadersMiddleware
from app.core.spa import SpaFiles, SpaMount
from app.schemas.errors import ERROR_RESPONSES


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    docs = not settings.is_production
    app = FastAPI(
        title="Alas de Señas",
        version="0.1.0",
        docs_url="/api/docs" if docs else None,
        redoc_url="/api/redoc" if docs else None,
        swagger_ui_oauth2_redirect_url="/api/docs/oauth2-redirect" if docs else None,
        responses=ERROR_RESPONSES,
        openapi_url="/api/openapi.json" if docs else None,
    )
    register_error_handlers(app)
    # Se agrega al final para quedar por fuera: cubre también los 500 (UnhandledErrorMiddleware).
    app.add_middleware(SecurityHeadersMiddleware)
    app.include_router(health.router, prefix="/api")
    app.include_router(auth.router, prefix="/api")
    app.include_router(curriculum.router, prefix="/api")
    app.include_router(lessons.router, prefix="/api")
    app.include_router(gamification.router, prefix="/api")
    app.include_router(progress.router, prefix="/api")
    app.include_router(reviews.router, prefix="/api")
    app.include_router(dictionary.router, prefix="/api")
    app.include_router(intro.router, prefix="/api")
    app.include_router(recognition.router, prefix="/api")
    app.mount("/media", MediaFiles(directory=settings.media_dir, check_dir=False), name="media")
    # Al final: solo recibe lo que no atendieron la API ni /media (tarea 11.1).
    app.router.routes.append(
        SpaMount("/", app=SpaFiles(directory=settings.web_dist_dir, check_dir=False), name="spa")
    )
    return app


app = create_app()

"""Crea la aplicación FastAPI: API bajo `/api` (D1)."""

from __future__ import annotations

from fastapi import FastAPI

from app.api import auth, health
from app.core.config import Settings, get_settings
from app.core.errors import register_error_handlers
from app.core.security_headers import SecurityHeadersMiddleware
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
    return app


app = create_app()

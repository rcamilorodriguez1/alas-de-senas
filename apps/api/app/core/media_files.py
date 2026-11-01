"""Archivos de `/media`: videos y pósters con nombre por contenido (D19, §11, B35, B54)."""

from __future__ import annotations

from starlette.exceptions import HTTPException
from starlette.responses import Response
from starlette.staticfiles import StaticFiles
from starlette.types import Scope

IMMUTABLE = "public, max-age=31536000, immutable"
PUBLIC_FOLDERS = ("v/", "p/")


class MediaFiles(StaticFiles):
    """Solo `v/` y `p/`. El nombre cambia si el contenido cambia, así que la caché es
    inmutable (B55). `manifest.json` no se publica: relaciona cada seña con su video (B54).
    Starlette responde 206 a peticiones con `Range` (B35)."""

    async def get_response(self, path: str, scope: Scope) -> Response:
        normalized = path.replace("\\", "/")
        if not normalized.startswith(PUBLIC_FOLDERS):
            raise HTTPException(status_code=404)
        response = await super().get_response(path, scope)
        if response.status_code in (200, 206):
            response.headers["Cache-Control"] = IMMUTABLE
        return response

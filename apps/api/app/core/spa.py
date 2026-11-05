"""SPA compilada (`WEB_DIST_DIR`) servida por FastAPI en producción (§11, §17.1, tarea 11.1)."""

from __future__ import annotations

from pathlib import Path

from starlette.exceptions import HTTPException
from starlette.responses import Response
from starlette.routing import Match, Mount
from starlette.staticfiles import StaticFiles
from starlette.types import Scope

IMMUTABLE = "public, max-age=31536000, immutable"
NO_CACHE = "no-cache"
INDEX = "index.html"
# Bajo estas carpetas una ruta sin archivo es un 404 de verdad: un script, el WASM o el modelo
# nunca deben recibir index.html (lo intentarían interpretar como JavaScript o JSON).
RESERVED = frozenset({"api", "media", "mediapipe", "models", "assets"})
# Las atienden otros montajes: si una ruta llega aquí con ese primer segmento (por ejemplo
# `/x/..%2Fmedia/manifest.json`, que StaticFiles normaliza a `media/manifest.json`) es un intento
# de saltarse ese montaje. Siempre 404, exista o no el archivo (B54: el manifiesto no se publica).
OWNED_ELSEWHERE = frozenset({"api", "media"})


class SpaFiles(StaticFiles):
    """Archivos de `dist/` con *fallback* a `index.html` para las rutas de React Router.

    - `assets/` lleva el hash del contenido en el nombre (Vite): caché inmutable.
    - Todo lo demás (`index.html`, modelos, WASM) se puede republicar con el mismo nombre:
      `no-cache` (el navegador revalida con ETag y no se queda con un modelo viejo).
    - Los 404 lanzan `HTTPException` para que respondan con el formato de error de la app.
    """

    async def check_config(self) -> None:
        # Sin `npm run build` la carpeta no existe: la app arranca igual y las rutas dan 404.
        if self.directory is not None and not Path(self.directory).is_dir():
            return
        await super().check_config()

    async def get_response(self, path: str, scope: Scope) -> Response:
        # El navegador resuelve «..» antes de pedir: si llega uno (p. ej. «..%2F»), es un intento
        # de path traversal y no se intenta adivinar a qué archivo apuntaba.
        if {".", ".."} & set(str(scope.get("path", "")).replace("\\", "/").split("/")):
            raise HTTPException(status_code=404)
        # casefold: en Windows el disco no distingue mayúsculas (/MEDIA es /media).
        first = path.replace("\\", "/").split("/", 1)[0].casefold()
        if first in OWNED_ELSEWHERE:
            raise HTTPException(status_code=404)
        try:
            response = await super().get_response(path, scope)
        except HTTPException as exc:
            if exc.status_code != 404 or first in RESERVED:
                raise
            response = await super().get_response(INDEX, scope)
            response.headers["Cache-Control"] = NO_CACHE
            return response
        if response.status_code == 200:
            response.headers["Cache-Control"] = IMMUTABLE if first == "assets" else NO_CACHE
        return response


def _is_api(path: str) -> bool:
    return path == "/api" or path.startswith("/api/")


class SpaMount(Mount):
    """Montaje en `/` que nunca atrapa `/api`: así una ruta de la API agregada después de
    `create_app` sigue funcionando, y un método equivocado da 405 (no 404) con su `Allow`.
    Una ruta `/api` inexistente cae en el 404 del router, con el formato de error de la app."""

    def matches(self, scope: Scope) -> tuple[Match, Scope]:
        if scope["type"] == "http" and _is_api(str(scope.get("path", ""))):
            return Match.NONE, {}
        return super().matches(scope)

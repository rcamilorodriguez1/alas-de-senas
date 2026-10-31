"""Cabeceras de seguridad y CSP compatible con MediaPipe y TensorFlow.js (§11)."""

from __future__ import annotations

from starlette.types import ASGIApp, Message, Receive, Scope, Send

CONTENT_SECURITY_POLICY = (
    "default-src 'self'; script-src 'self' 'wasm-unsafe-eval'; worker-src 'self' blob:; "
    "img-src 'self' data: blob:; media-src 'self' blob:; connect-src 'self'; "
    "style-src 'self' 'unsafe-inline'; font-src 'self'"
)

BASE_HEADERS: tuple[tuple[bytes, bytes], ...] = (
    (b"x-content-type-options", b"nosniff"),
    (b"referrer-policy", b"strict-origin-when-cross-origin"),
    (b"permissions-policy", b"camera=(self)"),
)

# La documentación interactiva usa recursos de CDN y solo existe fuera de producción.
CSP_EXEMPT_PREFIXES = ("/api/docs", "/api/redoc")


class SecurityHeadersMiddleware:
    """Middleware ASGI puro: también cubre las respuestas de error y los archivos estáticos."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        path = str(scope.get("path", ""))
        with_csp = not path.startswith(CSP_EXEMPT_PREFIXES)

        async def send_with_headers(message: Message) -> None:
            if message["type"] == "http.response.start":
                headers = [
                    (name, value)
                    for name, value in message.get("headers", [])
                    if name.lower() not in {h for h, _ in BASE_HEADERS}
                    and name.lower() != b"content-security-policy"
                ]
                headers.extend(BASE_HEADERS)
                if with_csp:
                    headers.append((b"content-security-policy", CONTENT_SECURITY_POLICY.encode()))
                message["headers"] = headers
            await send(message)

        await self.app(scope, receive, send_with_headers)

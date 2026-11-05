# Imagen de producción de Alas de Señas (§17.1): un solo servicio que sirve la API y la SPA.
# Construir:  docker build -t alas-de-senas .
# Probar:     docker run --rm -p 8000:8000 --env-file .env.docker alas-de-senas

# ---- 1. Dependencias del frontend ----------------------------------------------------------
FROM node:22-slim AS web-deps
# Misma estructura que el repositorio: el frontend importa CSV de `content/` (../../../../content).
WORKDIR /repo/apps/web
COPY apps/web/package.json apps/web/package-lock.json ./
# Reintentos: un corte de red a mitad de la descarga no debe tumbar la construcción.
RUN npm ci --fetch-retries=5 --fetch-retry-mintimeout=20000 --fetch-retry-maxtimeout=120000

# ---- 2. API en Python (base de la imagen final) --------------------------------------------
FROM python:3.12-slim AS api
# Misma versión de uv que generó uv.lock (fijada, nunca `latest`).
COPY --from=ghcr.io/astral-sh/uv:0.13.6 /uv /usr/local/bin/uv
WORKDIR /app
ENV UV_LINK_MODE=copy UV_PYTHON_DOWNLOADS=never
COPY pyproject.toml uv.lock ./
COPY apps/api ./apps/api
RUN uv sync --frozen --no-dev --package alas-api
COPY content ./content

# ---- 3. Archivos de MediaPipe (§10.1) ------------------------------------------------------
# `public/mediapipe/` no está en git: lo genera `alas camera-assets` (WASM del paquete npm +
# modelos .task oficiales). Se reutiliza el mismo comando para no duplicar las URLs (D-034).
FROM api AS camera
COPY --from=web-deps /repo/apps/web/node_modules/@mediapipe/tasks-vision/wasm \
     ./apps/web/node_modules/@mediapipe/tasks-vision/wasm
RUN /app/.venv/bin/alas camera-assets

# ---- 4. Compilar la SPA ----------------------------------------------------------------------
FROM web-deps AS web
COPY content /repo/content
COPY apps/web/ ./
COPY --from=camera /app/apps/web/public/mediapipe ./public/mediapipe
RUN npm run build

# ---- 5. Imagen final ----------------------------------------------------------------------
FROM api
COPY --from=web /repo/apps/web/dist ./apps/web/dist
# Los comandos se ejecutan desde .venv/bin y no con `uv run` (intentaría sincronizar al arrancar).
# Vite copia public/ dentro de dist/, por eso MEDIA_DIR apunta a dist/media.
# IP del cliente (D-035): uvicorn NO lee X-Forwarded-For (con `--forwarded-allow-ips='*'` tomaría
# el primer valor, que escribe el cliente); la app usa el valor que agregó el proxy de Render.
ENV PYTHONUNBUFFERED=1 APP_ENV=production UV_NO_SYNC=1 PATH="/app/.venv/bin:$PATH" \
    CONTENT_DIR=/app/content MEDIA_DIR=/app/apps/web/dist/media WEB_DIST_DIR=/app/apps/web/dist \
    TRUSTED_PROXY_HOPS=1
# Usuario sin privilegios; el código y .venv quedan de root (solo lectura para el proceso).
RUN useradd --create-home --uid 10001 alas
USER alas
EXPOSE 8000
CMD ["sh", "-c", "alembic -c apps/api/alembic.ini upgrade head && alas db seed && uvicorn app.main:app --app-dir apps/api --host 0.0.0.0 --port ${PORT:-8000} --no-proxy-headers"]

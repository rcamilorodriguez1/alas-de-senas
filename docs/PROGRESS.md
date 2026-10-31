# Bitácora de progreso — Alas de Señas

> Una sección por grupo de tareas. Formato:
>
> ```
> ## Grupo N — <nombre>
> - Plan: ...
> - Hecho: ...
> - Verificación manual: ✅/❌ (detalle)
> - Pendiente / riesgos: ...
> ```

## Grupo −1 — Kit de arranque
- Hecho: especificación v3, anexo de cámara, mockups, requirements/design/tasks, harness (`.claude/`) y `CLAUDE.md` incluidos en el repositorio.
- Siguiente: Grupo 0 (`/fase 0`).

## Grupo 0 — Base del proyecto
- Plan:
  - 0.1 `pyproject.toml` raíz (workspace uv `apps/api`, `exclude=["ml"]`, ruff/mypy §19.3), `.python-version`, `uv.lock`, `.env.example` (§19.4).
  - 0.2 Revisar kit y probar `guard_bash`/`guard_code` con los casos de `docs/harness.md` §7.
  - 0.3 `apps/api` (`alas-api`, hatchling): `app/core/config.py` (pydantic-settings, validación de producción), `core/errors.py` (`AppError`, manejadores, `VALIDATION_ERROR` con `fields`), `core/security_headers.py` (CSP §11), `api/health.py`, `main.py`.
  - 0.4 `infra/db.py` (`pool_pre_ping`, `serializable_session()`), Alembic (`alembic.ini`, `env.py` con URL de la config), `docker-compose.yml` (PG16 :5433), `docker/init-test-db.sql`.
  - 0.5 ruff + `mypy --strict` + pytest-cov; `tests/test_architecture.py`.
  - 0.6 `apps/web`: Vite + React + TS estricto + Tailwind + Router + TanStack Query, proxy `/api`, `@fontsource-variable`, ESLint, Vitest.
  - 0.7 `app/cli.py` (Typer) con todos los comandos (pendientes → «Pendiente de la fase N»); `core/clock.py` + `get_clock`.
  - 0.8 `tests/api/conftest.py`: fixture de sesión que aplica migraciones a `alas_test`. Subir a GitHub lo hace el equipo.
  - 0.9 `@tensorflow/tfjs@4.22.0` + `src/camera/tfjs-compat.test.ts` copiado de la plantilla.
  - Pruebas: config (prod sin secreto falla), errores (formato y validación), cabeceras, health (con BD y BD caída), arquitectura, `get_clock`, migraciones sobre BD vacía.
- Hecho: 0.1–0.7 y 0.9. Workspace uv (Python 3.12.16) con todas las dependencias de §3; API FastAPI (configuración validada, `AppError` + `ErrorOut` publicado en OpenAPI, 500 con cabeceras de seguridad, CSP de §11, `/api/health` con 503 si la BD cae); SQLAlchemy + `serializable_session()` + Alembic (aún sin migraciones); PostgreSQL 16 en Docker (5433) con `alas_test`; CLI `alas` completa (comandos futuros: «Pendiente de la fase N»); `get_clock` + `FakeClock`; web React 19 + Vite 8 + TS 5.9 estricto + Tailwind 4 + Router + TanStack Query; `tfjs-compat` pasa con `@tensorflow/tfjs` 4.22.0. `alas check` en verde: 130 pruebas Python (dominio 100 %), 7 Vitest, tipos al día. Decisiones: D-005.
- Revisión: `verificador-fase` APROBADO; `revisor-codigo` 1 bloqueante (tipo de error escrito a mano → `ErrorOut` generado) y mejoras aplicadas (500 con cabeceras, 503 en el contrato, `extra` no pisa el formato, consulta movida a `infra/repositories`, `db reset` solo en local, guarda `*_test` en pruebas, zona horaria y plazos validados, ESLint contra `as unknown as` y `@ts-expect-error`, proxy a 127.0.0.1).
- Verificación manual: ✅ `alas dev` levantó ambos servidores y `http://localhost:5173/api/health` respondió `{"ok":true,"db":true}` (con CSP); al detenerlo, los puertos 8000 y 5173 quedaron libres. Pendiente del equipo: repetirlo y probar Ctrl+C en su terminal.
- Pendiente / riesgos:
  - **0.8 sin marcar (pospuesta por el equipo, D-006)**: falta crear el repositorio en GitHub, hacer `git push` y confirmar que el job «alas check» de Actions pasa (el fixture de migraciones y los lockfiles con binarios de Linux ya están).
  - Grupo 2: con la primera migración, agregar una prueba que aplique todas las migraciones sobre una BD temporal vacía y luego `alembic check` (B47); el harness no permite bajar todas las migraciones. Llenar `USER_TABLES` en `tests/api/conftest.py`.
  - `alas dev` en Windows: si Ctrl+C deja Vite vivo (puerto 5173 ocupado), terminar el árbol de procesos con `taskkill /T`.
  - Aviso de Starlette (httpx en `TestClient`): no afecta; revisar al actualizar dependencias.

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
  - `alas dev` en Windows dejaba procesos huérfanos (puertos 8000/5173 ocupados): corregido, ahora detiene el árbol completo con `taskkill /T` (probado con el puerto 5173 ocupado).
  - Aviso de Starlette (httpx en `TestClient`): no afecta; revisar al actualizar dependencias.

## Grupo 1 — Dominio en Python (pruebas primero)
- Plan:
  - Esqueletos (tipos y firmas, sin lógica) en `app/domain`: `enums.py`, `dates.py`, `text.py`, `policies/{scoring,rewards,progress,streak,review,achievements,hearts}.py`, `exercises/{models,evaluators}.py`, `content/{models,generator,review_builder}.py`.
  - Pruebas en `tests/unit/domain/` con todos los casos obligatorios de §7 (escritor-pruebas), luego la implementación tarea por tarea (1.1 → 1.12).
  - Prueba del generador en dos procesos distintos (determinismo sin `hash()`), prueba de que `to_public()` no filtra `correctId`/`signId`/slugs.
  - Meta: cobertura de `app/domain` ≥ 95 %.
- Hecho: 1.1–1.12. 653 pruebas de dominio (dos escritores de pruebas en paralelo); cobertura de `app/domain` 99,45 %; `alas check` en verde (783 pruebas). Decisiones: D-007.
- Revisión independiente: `verificador-fase` **APROBADO**; `revisor-codigo` encontró 2 bloqueantes (respuesta deducible por la semilla pública del barajado y estímulo igual a la respuesta en conversaciones) → **corregidos** (D-008, 8 pruebas nuevas que simulan el ataque). Mejoras aplicadas: errores de contenido como `GenerationError`. Mejoras pendientes (no bloquean): `all_signs` obligatorio en `build_review_items`, usar o quitar `ReviewSign.node_order`, limitar `next_heart_at` cuando `updated_at` está en el futuro.
- Verificación manual: no aplica (el grupo no tiene interfaz); la línea «Verificar» es la cobertura ≥ 95 % → ✅ 99,45 %.

## ⏸ Punto de guardado — 31/10/2026
Estado al pausar (todo confirmado en git, `alas check` en verde, 791 pruebas):
- Grupo 0 ✅ (0.8 pospuesta por D-006: sin GitHub por ahora).
- Grupo 1 ✅ cerrado: revisado, bloqueantes corregidos, `alas check` en verde (791 pruebas, dominio 99,46 %).

Para retomar (en este orden):
1. Abrir Docker Desktop y ejecutar `uv run alas db up` (el contenedor no arranca solo).
2. `uv run alas check` debe terminar en «✓ alas check en verde».
3. (Hecho) Revisión del Grupo 1.
4. Seguir con `/fase 2` (contenido y base de datos). Las conversaciones de `content/conversations.yaml` NO pueden responder una seña con ella misma (D-008). Pendientes anotados para el Grupo 2: prueba de migraciones sobre BD temporal vacía (B47); llenar `USER_TABLES` en `tests/api/conftest.py`; repetir la prueba anti-filtración de `to_public` y la de ≥ 4 ejercicios con puntaje sobre el contenido real de `content/`; que `alas content check` exija ≥ 4 palabras de deletreo por nodo ALPHABET (para tener 4 opciones).

## Grupo 2 — Contenido y base de datos
- Plan:
  - 2.1 `infra/models.py` completo (§5) + primera migración Alembic revisada a mano; prueba que aplica todas las migraciones sobre una BD temporal vacía y luego `alembic check` (B47); `USER_TABLES` del conftest.
  - 2.2 `content/`: `curriculum.json`, `signs.csv` (109 señas, `motion`, `meaning`/`usage_example` redactados), `conversations.yaml` (`# revisar`, sin responder una seña con ella misma — D-008), `intro.json`, `fonts/` (Nunito OFL).
  - 2.3–2.4 `app/content/csv_reader.py` (utf-8-sig, mojibake), `loader.py` (JSON/CSV/YAML → specs del dominio), `validation.py` (§6.6 completo + reporte) y `alas content check [--skip-raw]`.
  - 2.5–2.6b `app/content/media.py` (manifiesto D19, nombres por contenido), `placeholders.py` (Pillow + ffmpeg), `videos.py` (normalización, póster, caché, huérfanos, sugerencias), `images.py` (plan B: EXIF, thumbnail, lienzo 1280×720, fundido).
  - 2.7 `app/content/seed.py` upsert idempotente (`ON CONFLICT DO UPDATE`) + `alas db seed` y `alas content all`.
  - Pruebas: `tests/unit/content/` (lector, carga, validaciones, emparejamiento de nombres, imágenes generadas en la prueba, ffmpeg real con clips mínimos) y `tests/api/` (migraciones en BD vacía, seed ×2 = mismos conteos, progreso intacto).
- Hecho: 2.1–2.7. `alas content all` sin errores: 109 videos de relleno (4,8 MB, versionados en `apps/web/public/media/`), 549 ejercicios; `alas db seed` dos veces → mismos conteos. `alas check` en verde (1082 pruebas). Decisiones: D-009.

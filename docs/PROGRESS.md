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
- Revisión: `verificador-fase` **APROBADO**. `revisor-codigo`: 1 bloqueante (el seed convertía en ADMIN una cuenta de estudiante con el correo del administrador) → **corregido**; mejoras aplicadas: reordenar nodos/módulos, validación de la contraseña del administrador, manifiesto ausente no borra videos, rutas del manifiesto validadas, errores de la CLI en español, nodos desconocidos en `conversations.yaml`, slugs de `intro.json`, advertencias de §6.4.1 con prueba, «no» sin comillas en YAML con prueba. `alas check` en verde (1100 pruebas).
- Verificación manual: ✅ (hecha por el agente) `alas content all` sin errores, 109 rellenos, seed ×2 = mismos conteos. **Pendiente del equipo:** abrir 2–3 videos de `apps/web/public/media/v/` y ver la palabra con tildes y «Video en preparación»; revisar con el intérprete `content/conversations.yaml` (`# revisar`), las palabras de deletreo y el `motion` de J, Ñ y Z.
- Pendiente / riesgos para grupos siguientes:
  - **Grupos 3–4:** filtrar siempre por `Module.published`; ignorar lecciones sin ejercicios (si un módulo se despublica, sus lecciones quedan en la BD). Las señas quitadas del CSV quedan en la BD con su nodo: el diccionario y la ruta deben basarse en el contenido cargado actual (pendiente: desligarlas en el seed).
  - **Pruebas de API:** `tests/api/test_seed.py` trunca las tablas de contenido; cuando haya pruebas de API que necesiten contenido (Grupo 4 en adelante), sembrar en una fixture de sesión y volver a sembrar tras `test_seed`.
  - **B54 / D20:** `apps/web/public/media/manifest.json` relaciona slug → video y se sirve como archivo público; con él se puede deducir la respuesta de VIDEO_TO_MEANING. Decidir en el Grupo 5/11 si no se sirve (el frontend no lo necesita: recibe las rutas de la API). Los videos de relleno muestran la palabra escrita por diseño (D6).
  - D-007.5 (distractores de «misma categoría» de nodos posteriores): confirmar con el equipo.

## Grupo 3 — Autenticación
- Plan:
  - 3.1 `app/core/security.py` (bcrypt costo 12, hash ficticio, JWT HS256 15 min con `exp`/`sub`/`role`, refresh `token_urlsafe(32)` guardado como SHA-256), `app/core/rate_limit.py` (librería `limits` de slowapi: login 5/min por IP+correo, registro 10/min por IP, 240/min por usuario autenticado), `app/schemas/auth.py` (camelCase, `extra="forbid"`, 8–72 bytes, meta 5/10/15/20, aceptación obligatoria), `app/services/auth_service.py`, `app/api/auth.py` + `app/api/deps.py` (`current_user`), cookie `rt` httpOnly `path=/api/auth`.
  - 3.2 `tests/api/test_auth.py`: duplicado, credenciales inválidas (mensaje genérico), 73 bytes, refresh rotado, refresh revocado tras logout, límite de intentos, `/me`, correo normalizado.
  - 3.3 `alas gen-api`; `src/lib/api.ts` (token en memoria con Zustand, *single-flight* ante 401, `volver=`), arranque con refresh y pantalla de carga, guardas `RequireAuth`/`GuestOnly`.
  - 3.4 `/ingresar` y `/registro` (React Hook Form + Zod, errores por campo del servidor), `/aprender` provisional con «Cerrar sesión».
  - Vitest: refresh único con 3 peticiones simultáneas (B22), guardas, formularios con errores del servidor.
- Hecho: 3.1–3.4. 91 pruebas de API (registro, login, rotación, logout, límites, /me, tiempos con FakeClock) y 87 de Vitest (store en memoria, refresh single-flight con 3 peticiones a la vez, arranque sin parpadeo, guardas, formularios con errores por campo del servidor). `alas check` en verde (1191 pruebas Python). Flujo real comprobado por el proxy de Vite con curl: registro → /me → refresh → logout → refresh revocado (401). Decisiones: D-010.
- Nota honesta: los escritores de pruebas trabajaron en paralelo con la implementación (mismo contrato), así que no se vieron fallar antes; el de Vitest se cortó por el límite de uso, pero sus 7 archivos quedaron completos y pasan.
- Revisión: `verificador-fase` **APROBADO** (fd51f18). `revisor-codigo`: sin bloqueantes; mejoras aplicadas: el login ya no acepta contraseñas que solo empiezan igual (truncado a 72 bytes), `PATCH /me` rechaza nombres en blanco, refresh fallido borra la cookie, cookie `Secure` en producción con prueba, la renovación solo cierra la sesión ante 401, 401 tardío sin doble rotación, `volver` solo rutas internas, caché vaciada al perder la sesión. Pendientes en D-010.11.
- Verificación manual: **pendiente del usuario** en Chrome, Edge y Firefox a 1280×720, 1366×768 y 1920×1080: registrarse → /aprender; F5 mantiene la sesión sin mostrar el login; «Cerrar sesión» → /ingresar y /aprender vuelve a pedir ingreso; DevTools: Local/Session Storage vacíos y cookie `rt` HttpOnly con Path /api/auth.

## Grupo 4 — Ruta de aprendizaje
- Plan:
  - 4.1 Relaciones `Module.nodes`/`Node.lessons` (ordenadas), `infra/repositories/curriculum.py` (una consulta con `selectinload`, hechos de `lesson_sessions` completadas), `services/curriculum_service.py` (`compute_progress` del dominio, `bestScore`, `estimatedXp` con `RewardPolicy`, % por módulo = aprobadas ÷ lecciones del módulo publicado), `schemas/curriculum.py`, router `api/curriculum.py`: `GET /learning-path`, `GET /nodes/{id}` (404 `NODE_NOT_FOUND`). Fixture `seeded_content` en `tests/api/conftest.py`.
  - 4.2 `AppLayout` (barra lateral 240 px, ruta ≤ 720 px, panel derecho 320 px que se oculta < 1280 px) y `SmallScreenGate` (< 1024 px: aviso con Tomi).
  - 4.3 `LearnPage` con módulos, nodos en zigzag, estados con ícono + texto (🔒 «Bloqueada»), popover de lección con «Empezar», sello «Próximamente».
  - 4.4 `Mascot`/`TomiSvg` (§9.6) con moods happy·cheer·sad·thinking·sleeping, burbuja de mensaje y `prefers-reduced-motion`.
  - Pruebas: API (usuario nuevo → solo M1-N1-L1, cadena tras aprobar, dorado, M4 «Próximamente» sin contar en %, 404, una sola tanda de consultas) y Vitest (estados con texto, popover, Próximamente, aviso < 1024 px, Tomi sin animación con movimiento reducido).
- Hecho: 4.1–4.4. 41 pruebas de API (estados, desbloqueo en cadena, dorado, progreso con redondeo, aislamiento por usuario, conteo de consultas constante ≤ 8) y 70 de Vitest (Tomi y moods, movimiento reducido, aviso < 1024 px, layout, ruta con popover y «Próximamente»). `alas check` en verde (1236 Python, 168 Vitest). Verificación visual con Playwright a 1366×768: usuario nuevo solo con M1-N1-L1 disponible, popover «+20 XP · Empezar», aviso a 900 px. Decisiones: D-011.
- Nota: las pruebas se escribieron en paralelo con la implementación (mismo contrato); no se vieron fallar antes.
- Revisión: `revisor-codigo` sin bloqueantes; mejoras aplicadas (reglas de % y XP estimada al dominio con pruebas, aviso de pantalla pequeña sin desmontar la app y sin bloquear el diccionario, contraste AA, foco del popover, un solo popover, saludo sin nombre, función sin uso, fixture de contenido más robusta). `verificador-fase` **APROBADO** (6db17c1); sus hallazgos de contraste, aviso que bloqueaba el diccionario, función sin uso y módulo bloqueado sin texto quedaron corregidos. `alas check` en verde (1247 Python, 174 Vitest).
- Verificación manual: **pendiente del usuario** (ver reporte del grupo).

## Grupo 5 — Lecciones
- Plan:
  - 5.1 `services/option_tokens.py` (HMAC D20), migración nueva en `lesson_sessions` (`exercises_hash` para detectar contenido recargado y `result` JSONB para devolver el mismo resultado en el `complete` repetido), `infra/repositories/lessons.py`, `schemas/lessons.py`, `services/lesson_session_service.py` (`start`/`answer`/`complete` según §8.3: 403 `LESSON_LOCKED`, 403 `NO_HEARTS` salvo Aprende, 404, 409, 410, vidas solo si la respuesta se insertó, `complete` SERIALIZABLE con reintentos, idempotente, tope de 15 min) y router `api/lessons.py`. Racha y logros quedan para el Grupo 6 (`streak` provisional).
  - 5.2 `tests/api/test_lessons.py` con FakeClock (casos de la tarea).
  - 5.3 `/media` en FastAPI con `Range` (206) y `Cache-Control: immutable`; `manifest.json` no se sirve (B54); `SignVideoPlayer`.
  - 5.4–5.6 `LessonPage` (encabezado, actividades en secuencia por seña, confirmación al salir), actividades (Observa, Selecciona, Memoria, Produce con autoevaluación, Conversación, Deletreo), `SESSION_EXPIRED`, StrictMode, atajos 1–4/Enter, ajuste a 1366×768.
- Hecho: 5.1–5.6. 68 pruebas de API (respuestas ocultas, tokens, primer intento, vidas solo si se insertó, 0 vidas bloquea L2 pero no L1 ni la lección empezada, doble complete, 409/410/404, duración con tope, Range 206 e immutable) y 71 de Vitest (reproductor, lección, actividades, atajos). `alas check` en verde (1315 Python, 245 Vitest). Verificación con Playwright a 1366×768: L1 completa por la interfaz (12 ejercicios) → «2 · Reconoce» disponible; el JSON de inicio no trae correctId/signId; video, pregunta, opciones y botón visibles en los 6 ejercicios de selección. Decisiones: D-012.
- Nota: las pruebas se escribieron en paralelo con la implementación; sus fallos encontraron 3 defectos reales de la interfaz (marca de la correcta, memoria empezando por la palabra, conversación con radios) y uno del servidor (iat validado con la hora real).

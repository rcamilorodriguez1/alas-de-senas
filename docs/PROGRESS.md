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
- Revisión: verificador-fase NO APROBADO (videos compactos sin reproducir) y revisor-codigo (carrera de vidas, orden de bloqueos, límites de tamaño, `result` nulo, placeholder en lecciones, Enter tras clic, grupo del bloque final, foco, cortes de red). Todo corregido con pruebas nuevas (D-012.8–10). `alas check` en verde (1318 Python, 248 Vitest); Playwright: L1 completa y L2 disponible.

## Grupo 6 — Gamificación
- Plan:
  - 6.1 `services/gamification_service.py`: `apply_completion` dentro de la transacción SERIALIZABLE del `complete` → `register_activity` (actividad diaria con segundos, XP y lecciones; `StreakPolicy`), repasos de las señas de la lección con `ReviewScheduler` (incluido «Necesito repasar»), estadísticas → `evaluate_achievements` → `INSERT … ON CONFLICT DO NOTHING RETURNING` y néctar solo por filas insertadas. `complete` devuelve racha real y logros nuevos.
  - 6.2 `api/gamification.py`: `GET /gamification/stats`, `GET /gamification/achievements`, `POST /gamification/streak-freeze` (50 néctar, máx. 2), `POST /gamification/hearts-refill` (30 néctar); `HEARTS_ENABLED`.
  - 6.3 `CelebrationModal` (puntaje, XP, racha, logros, néctar, confeti respetando movimiento reducido) y panel derecho/barra superior con racha, meta diaria, néctar, vidas y protector.
  - 6.4 Página `/logros`.
  - 6.5 Vidas en la interfaz: contador en barra, panel y lección; latido al perder una; modal «Sin vidas» (repasar / recargar / esperar con cuenta regresiva).
- Hecho: 6.1–6.5. 66 pruebas de API nuevas (actividad diaria, racha con 23:59/00:01 de Bogotá y protectores, repasos con «Necesito repasar», cada logro una sola vez incluso con dos `complete` simultáneos, stats, compra de protector y recarga de vidas) y 25 de Vitest (panel, barra superior, celebración y confeti, /logros, latido y modal «Sin vidas»). Dos pruebas del Grupo 5 se ajustaron: el néctar del usuario incluye FIRST_LESSON (+10) y los textos dicen «+N de néctar». `alas check` en verde (1384 Python, 303 Vitest). Playwright: L1 → celebración con «Primeras alas», barra 🔥 1 · 🌸 15 · ❤️ 5, /logros «1 de 9 desbloqueados». Decisiones: D-013.
- Revisión: verificador-fase APROBADO; revisor-codigo sin bloqueantes. Corregido: el protector comprado con la racha ya rota no la revive; pruebas de compras simultáneas y de dos lecciones completadas a la vez; «¡Empezaste una racha!»; foco del modal «Sin vidas» en «Volver a la ruta»; limpieza del temporizador del latido (D-013.8). `alas check` en verde (1388 Python, 303 Vitest).
- Verificación manual pendiente (usuario): comprar un protector descuenta 50 de néctar; un logro aparece una sola vez; con 0 vidas L2 muestra el modal y L1 se puede hacer; probar en 1280×720, 1366×768 y 1920×1080 en Chrome, Edge y Firefox.
- Pendientes menores: «Repasar señas» lleva a `/repaso` (llega en el Grupo 7); contadores que no refrescan al llegar a 0; costos repetidos en la interfaz; `nextHeartAt` del 403 no declarado en OpenAPI; fecha del logro en la zona del navegador.

## Grupo 7 — Progreso y repaso
- Plan:
  - 7.1 `services/progress_service.py` + `api/progress.py`: `GET /progress/summary` (% global y por módulo, XP, racha, señas aprendidas), `/progress/history?page=` (20 por página, más recientes primero), `/progress/units` (puntaje promedio y precisión por módulo y nodo).
  - 7.2 `services/review_service.py` + `api/reviews.py`: `GET /reviews/queue`, `POST /reviews/sessions` (409 `NO_REVIEWS_DUE`, reutiliza la abierta de hoy, `build_review_items` con distractores de señas vistas, tokens D20), `POST /review-sessions/{id}/answers` (primer intento, sin vidas), `POST /review-sessions/{id}/complete` (SERIALIZABLE, idempotente, reprograma, `register_activity(kind="review")`, +1 vida con ≥ 80 %, logros de racha; sin XP ni néctar).
  - 7.3 `tests/api/test_progress.py` y `tests/api/test_reviews.py`.
  - 7.4 `/progreso` (Recharts: barras por módulo) y `/repaso` (tarjeta como la actividad 2, reutiliza `SelectMeaningActivity`), panel con «Señas por repasar».
- Hecho: 7.1–7.4. 109 pruebas de API nuevas (39 de progreso, 70 de repaso: tokens sin slugs, sin endpoint de aciertos, cola, reutilización, primer intento, no quita vidas, reprogramación, racha, +1 vida con ≥ 80 %, idempotencia y concurrencia) y 7 de Vitest (/repaso, /progreso, panel). Dos pruebas corregidas (token vencido tras mover el reloj; semilla duplicada). La prueba de inicios simultáneos encontró una carrera real (corregida bloqueando al usuario, D-014.2). Playwright: L1 → señas por repasar en el panel → repaso 3 de 3 → segundo repaso el mismo día «No tienes señas por repasar hoy» → /progreso con gráfica, unidades e historial. Decisiones: D-014.
- Revisión: verificador-fase APROBADO; revisor-codigo sin bloqueantes. Corregido: una sesión de repaso abierta de otro día se cierra al empezar la de hoy (no paga dos veces); la precisión por unidad solo cuenta sesiones completadas; mensajes propios del repaso; gráfica responsiva y decorativa (D-014.8). 2 pruebas nuevas (111 en progreso y repaso). `alas check` en verde (1499 Python, 310 Vitest).
- Verificación manual pendiente (usuario): fallar una seña en L1 → al día siguiente aparece en «Señas por repasar»; repasarla mantiene la racha (2 días); un segundo repaso el mismo día no es posible; /progreso muestra avance, gráfica, unidades e historial. Probar en 1280×720, 1366×768 y 1920×1080 en Chrome, Edge y Firefox.
- Pendientes menores: D-014.9.

## Grupo 8 — Diccionario
- Plan:
  - 8.1 `services/dictionary_service.py`, `infra/repositories/dictionary.py`, `api/dictionary.py`: búsqueda con `ILIKE` sobre `normalized_word` (término normalizado con `normalize_text`, `%`/`_`/`\` escapados), filtro por categoría y página; sugerencias por `levenshtein ≤ 2` si no hay resultados; categorías con señas; ficha con lección relacionada (estado si hay sesión) e `isFavorite`; favoritos idempotentes. Autenticación opcional para buscar y ver la ficha.
  - 8.2 `/diccionario` (buscador, filtro de categorías, resultados, sugerencias, favoritos) y `/diccionario/:slug` (video con controles, significado, categoría, cómo se hace o «Descripción en revisión», ejemplo, práctica rápida, enlace a la lección o «bloqueada», botón de favorito), accesibles sin sesión.
- Hecho: 8.1–8.2. 81 pruebas de API (normalización con ñ real «Baño», comodines literales, sugerencias, categorías, ficha con estado de la lección, favoritos idempotentes y con Clock) y 9 de Vitest (sin sesión, búsqueda en la URL, sugerencias, filtro, favoritos, lección bloqueada). Playwright sin sesión: «GRACÍAS» → 1 seña (Gracias); «grasias» → «¿Quisiste decir Gracias?»; ficha completa. Decisiones: D-015.
- Revisión: verificador-fase APROBADO; revisor-codigo: 1 bloqueante (corazón en vez de ⭐ para favoritos) corregido, más foco del botón, DELETE en una sentencia y 2 pruebas nuevas (D-015.6).
- Verificación manual pendiente (usuario): sin sesión, /diccionario carga; «GRACÍAS» → Gracias; «grasias» → «¿Quisiste decir Gracias?»; «baño» encuentra Baño y «bano» no; ficha con video, «Descripción en revisión», práctica rápida y lección (bloqueada sin enlace); con sesión, ⭐ guardar/quitar y «Tus favoritos». Probar en 1280×720, 1366×768 y 1920×1080 en Chrome, Edge y Firefox.

## Grupo 9 — Introducción
- Plan:
  - 9.1 `services/intro_service.py` + `api/intro.py`: `GET /api/intro` público desde `content/intro.json` y la BD (palabra y video de cada seña; quiz con la correcta y 2 distractores de las tarjetas, ordenados por palabra; incluye la respuesta porque el intro no da XP, §8.2). Página `/bienvenida`: 6 tarjetas (video en bucle sin controles, palabra, mensaje de Tomi), mini-quiz de 3 preguntas con retroalimentación inmediata, marca en el navegador y paso al registro; «Ya tengo cuenta» siempre visible. `/` redirige a `/bienvenida` a quien no tiene sesión ni completó el intro.
  - 9.2 `introCompleted` en el registro → `GamificationService.grant_intro` (FIRST_FLAP con `ON CONFLICT DO NOTHING RETURNING`, néctar una vez). `unauthorized` pasa a `core/errors.py` para evitar el ciclo auth ↔ gamificación.
- Hecho: 9.1–9.2. 22 pruebas de API (intro público, orden, videos, quiz con una correcta y distractores del intro, FIRST_FLAP una vez con la fecha del Clock) y 2 de Vitest (recorrido completo y error); 2 pruebas de interfaz ajustadas al nuevo comportamiento (D-016.5). Playwright: `/` → `/bienvenida` → 6 tarjetas → quiz → registro → /logros «1 de 9 desbloqueados», néctar 10. Decisiones: D-016.
- Revisión: verificador-fase APROBADO; revisor-codigo sin bloqueantes. Corregido: foco al título en cada paso, región de retroalimentación siempre montada, marca guardada al terminar el quiz (D-016.6).
- Verificación manual pendiente (usuario): ventana privada → `/` lleva a `/bienvenida`; 6 tarjetas con video en bucle, palabra, Tomi y «Ya tengo cuenta»; quiz con retroalimentación; «Crear mi cuenta» → registro → «Primer aleteo» y 10 de néctar; después `/` sin sesión lleva a `/ingresar`. Revisar el tamaño del video de las tarjetas contra el mockup (D-016.7).

## Grupo 10 — Cámara (beta)
- Plan:
  - 10.1 `@mediapipe/tasks-vision` (versión exacta, §3) y `alas camera-assets`: copia `wasm/*` a `apps/web/public/mediapipe/wasm/` y descarga `hand_landmarker.task` (si falla, imprime la URL oficial).
  - 10.2 `src/camera/normalize.ts` `normalizeLandmarks` (espejo de la mano izquierda, origen en la muñeca, escala muñeca–punto 9, descarte < 1e-6, 63 valores) con pruebas de valores conocidos e invariancia a traslación y escala.
  - 10.3 `src/camera/recognizer.ts`: singleton con promesa en caché, timestamps crecientes, pausa con `visibilitychange`, limpieza (pistas, rAF, `close()`), predicción en `tf.tidy()`, suavizado por mayoría de 10, umbral 0,70; `MockClassifier` sin modelo.
  - 10.4 `/camara`: video en espejo con puntos, seña y confianza, aviso «Tu video no sale de tu dispositivo», errores de permiso/sin cámara/ocupada/sin HTTPS con autoevaluación.
  - 10.5 `/admin/dataset` (ADMIN) que exporta `dataset.json` (`hand-v1`, 63, slug o `NINGUNA`, alias, versión de MediaPipe); `POST /recognition/results` (60/min, cuenta si correcto, confianza ≥ 0,7 y máx. una vez por seña cada 10 s) → HUMMINGBIRD_EYE.
  - 10.6 `ml/train_static.py` (rechaza `dynamic`, validación, separación por persona, semillas, matriz de confusión, exportación con `labels.json` y `meta.json`) y cuaderno para Colab.
  - 10.7 `ProduceActivity` con cámara si la seña está en `labels.json`; prueba de que `labels.json` coincide con las salidas del modelo.
  - 10.8 **Requiere al equipo:** grabar muestras de ≥ 3 personas con letras `static` confirmadas por el intérprete y entrenar. Sin modelo, todo funciona en modo simulado (R8.6).
- Avance (punto de guardado, 01/11/2026): 10.1 hecha (`@mediapipe/tasks-vision` 1.1.0 exacta — la 1.2.0 tenía 5 días —, `alas camera-assets` con 6 pruebas; `public/mediapipe/` en `.gitignore` porque lo genera el comando). 10.2 hecha (`src/camera/normalize.ts`, 7 pruebas). 10.3 en curso: `src/camera/classifier.ts` (MockClassifier, TfjsClassifier con `tf.tidy`, carga diferida que simula si no hay modelo o no coincide con `labels.json`, suavizado por mayoría de 10 con umbral 0,70, timestamps crecientes; 10 pruebas). Falta: sesión de cámara (singleton de HandLandmarker, `visibilitychange`, limpieza), `/camara`, colector, `POST /recognition/results`, `ml/train_static.py`, Produce con cámara.
- Avance: 10.3 y 10.4 hechas. `src/camera/session.ts` (singleton de HandLandmarker con conteo de usuarios para StrictMode, `visibilitychange`, limpieza de pistas/rAF/`close()`, errores de permiso/sin cámara/ocupada/sin HTTPS) y `/camara` (video y puntos en espejo con CSS, seña y confianza, aviso de privacidad, «Modelo en entrenamiento» para ADMIN, autoevaluación ante errores, apaga la cámara al salir); 6 pruebas. Falta: 10.5 colector y `POST /recognition/results`, 10.6 `ml/train_static.py`, 10.7 Produce con cámara, 10.8 (equipo).
- Avance: 10.5 hecha. `POST /recognition/results` (solo números, campos extra → 422, 60/min, cuenta si correcto y confianza ≥ 0,7, una vez por seña cada 10 s con el Clock en memoria del proceso; «Ojo de colibrí» a los 20; 12 pruebas). `/admin/dataset` (solo ADMIN: alias, etiqueta = slug de letra o NINGUNA, cuenta regresiva 3 s, 10 s a ~10 muestras/s, conteo por clase, exporta `dataset.json` hand-v1 con la versión de MediaPipe; 4 pruebas). `/camara` reporta las señas detectadas. Falta: 10.6 `ml/train_static.py`, 10.7 Produce con cámara, 10.8 (equipo).
- Avance: 10.6 hecha en código: `ml/train_static.py` (valida versión/tamaño, rechaza letras `dynamic` y etiquetas desconocidas, separa por persona con ≥ 3, semillas, matriz de confusión, exporta modelo + `labels.json` + `meta.json` juntos) con 14 pruebas de datos, y `ml/notebooks/entrenamiento.ipynb` para Colab. **No se pudo entrenar aquí:** TensorFlow 2.15 no instala en Windows (D-017.6). Falta: 10.7 Produce con cámara, 10.8 (equipo).
- Avance: 10.7 hecha. `src/camera/labels.ts` (salidas del modelo desde `model.json`, `labelsMatchModel`, etiquetas en caché) con pruebas contra el modelo real convertido del kit y contra el modelo publicado si existe; `ProduceActivity` ofrece «Usar la cámara» solo si la seña está en `labels.json`, envía `{method:"camera", ok:true, confidence}` al reconocerla, reporta el reconocimiento y apaga la cámara; la autoevaluación siempre está (3 pruebas).
- **10.8 pendiente (equipo):** grabar con `/admin/dataset` ≥ 300 muestras por letra estática confirmada por el intérprete (5–10 letras) de ≥ 3 personas y ≥ 600 de NINGUNA; entrenar en Colab con `ml/notebooks/entrenamiento.ipynb`; copiar `lsc-alfabeto/` tal cual en `apps/web/public/models/`.
- Revisión: revisor-codigo con 1 bloqueante (cámara encendida al salir mientras se enciende) y 6 importantes, todos corregidos (D-017.8). `alas check` en verde (1625 Python, 359 Vitest) + 16 pruebas de `ml/tests`.
- Verificación manual pendiente (usuario): `uv run alas camera-assets` y luego `/camara` en Chrome: permiso, video en espejo con puntos, «Tu video no sale de tu dispositivo», «Apagar cámara» apaga la luz de la cámara, salir de la página también; negar el permiso muestra el mensaje y la autoevaluación. Con ADMIN, `/admin/dataset` graba y exporta `dataset.json`. Cuando exista el modelo (10.8): la letra entrenada se reconoce, sin mano no aparece nada, y «Produce la seña» ofrece la cámara.
- Avance 10.8 (D-019): con LSC-54 se preparó el modelo de **números 1–5** (estáticos, pendiente de confirmar por el intérprete). Colector «Desde videos» con el mismo pipeline del navegador; dataset de 3.908 muestras de 18 personas en `ml/data/` (fuera de git). Falta: entrenar en Colab (usuario) y copiar `lsc-alfabeto/` a `apps/web/public/models/`.
- 10.8 hecha (D-019): modelo de números 1–5 entrenado en Colab y publicado; reconoce el número correcto en 4 de 5 videos de prueba en `/camara`. MediaPipe en CPU (la GPU fallaba sin aviso). **Grupo 10 terminado.**
- Verificación manual pendiente (usuario): en `/camara`, hacer los números 1 al 5 frente a la cámara (mano a la altura del pecho, fondo claro); en el nodo «Números» (M2-N3), «Produce la seña» ofrece «Usar la cámara» en 1–5. Intérprete: confirmar que 1–5 son estáticos.

## Grupo 10B — Cámara holística: dos manos + rostro
- Plan:
  - 10B.1 `alas camera-assets` descarga también `holistic_landmarker.task`; `src/camera/holistic/` crea el detector con GPU y, si falla, CPU; verifica los 18 nombres de *blendshapes*.
  - 10B.2 `buildHolisticFrame` (159 valores: forma/posición/presencia de las dos manos respecto a los hombros, mano→cara, 18 *blendshapes*, presencia de cara; reflejo para zurdos) + pruebas A.12. `dominantHand` ya está en `PATCH /me` y en el perfil.
  - 10B.3 `FrameSequencer` (remuestreo a 30 cuadros por timestamps, interpolación de huecos ≤ 3, control de calidad 80/70/90 %) + pruebas.
  - 10B.4 Interfaces `FeatureExtractor`, `SignClassifier`, `RecognizerFactory`; el alfabeto sigue igual.
  - 10B.5 Guía visual (silueta, mensajes en vivo) y FPS en modo ADMIN.
  - 10B.6 Colector `holistic-v2` (cuenta regresiva de 2 s).
  - 10B.7 `ml/train_sequence.py` (GRU `reset_after=False`, aumentos, normalización media/desviación, separación por persona, exportación con `meta.json`) + fixtures de paridad probados con pytest y Vitest.
  - 10B.8 Importador `/admin/importar` (videos e imágenes) + `content/dataset-mapping.csv` + créditos.
  - 10B.9 `ProduceActivity` en modo gestos.
  - 10B.10 Entrenar 3–5 señas con movimiento con los videos de cortesía de LSC-54 (18 personas) y validar con personas no vistas (meta ≥ 80 %). Los rostros de LSC-54 vienen pixelados: el bloque de expresión facial puede quedar en 0.

### Estado del Grupo 10B (03/11/2026): terminado
- [x] 10B.1 `holistic_landmarker.task` en `alas camera-assets`; GPU → CPU al crear, y además si la GPU no detecta la pose o lanza errores al detectar (`SilentGpuGuard`, D-025/D-028); aviso si faltan blendshapes (H4).
- [x] 10B.2 `buildHolisticFrame` (159 valores, mano dominante, reflejo) + pruebas A.12; `dominantHand` ya estaba en `PATCH /me` y en el perfil.
- [x] 10B.3 `FrameSequencer` (remuestreo, huecos ≤ 3, recorte al tramo con mano, calidad medida en ese tramo) + pruebas A.12.
- [x] 10B.4 `FeatureExtractor`/`SignClassifier`/`RecognizerFactory`; el alfabeto usa `HandOnlyExtractorV1` con el mismo comportamiento.
- [x] 10B.5 `GestureCamera`: aviso de privacidad, silueta, dibujo de manos/hombros/cara, mensajes cada 0,5 s, FPS y ms (ADMIN). El detector carga antes de encender la cámara.
- [x] 10B.6 `/admin/gestos`: cuenta regresiva 3-2-1, 2 s, alias, autorización y exportación A.6.
- [x] 10B.7 `ml/train_sequence.py` (GRU `reset_after=False`, aumentos, CV por persona, prototipos para Tomi, `meta.json`) + `ml/fixtures/holistic_v2_cases.json` probados con pytest y Vitest (H11).
- [x] 10B.8 `/admin/importar` (lotes con pausa, tiempo límite por video, mano que firma automática) + `content/dataset-mapping.csv` (validado por `alas content check`) + créditos.
- [x] 10B.9 `ProduceActivity` en modo gestos (`gestureLabel`, D-026), retroalimentación de Tomi y equivalencias B = 4 (D-027).
- [x] 10B.10 Modelo `lsc-gestos` publicado: 409 muestras de LSC-54 (18 personas): hola, adiós, por favor, de nada, perdón + NINGUNA. Validación cruzada por persona **89,7 %** (NINGUNA 93 %, adiós 81 %, de nada 96 %, hola 76 %, perdón 88 %, por favor 96 %). Keras ↔ TensorFlow.js: diferencia máx. 1,2e-7. Prueba E2E con cámara falsa: la lección reconoce «hola» y apaga la cámara (con 4,5 FPS en Chrome sin pantalla, la calidad a veces descarta la muestra).
- Verificación: `alas check` en verde (1664 pytest, 431 Vitest); `ml/tests` 39 en verde; revisión de `revisor-codigo` sin bloqueantes (corregidos los 6 importantes y 6 menores).
- Verificación independiente (`verificador-fase`): APROBADO CON OBSERVACIONES; las observaciones quedan en D-029 y en la verificación manual. Prueba nueva `published-model.test.ts` sobre el modelo publicado.
- **Verificar a mano:** con cámara real en 1366×768, ≥ 12 FPS (se ve en `/admin/gestos`); «hola» reconocida con una persona que no esté en LSC-54, con la mano derecha y con la izquierda; al salir de la lección la cámara se apaga. Las señas con movimiento sin modelo (p. ej. «buenos días») siguen con autoevaluación.
- Riesgos: modelo entrenado sin expresión facial (LSC-54 pixelado); solo 18 personas; «hola» a veces se confunde con «adiós». Grabar al equipo con `/admin/gestos` y reentrenar lo mejora. El intérprete debe confirmar B = 4.

## Grupo 11 — Cierre
- Plan:
  - 11.1 `app/core/spa.py` (`SpaFiles`): sirve `WEB_DIST_DIR` en `/`; rutas sin archivo → `index.html`, salvo bajo `/api`, `/media`, `/mediapipe`, `/models`, `/assets` (404 de verdad, para que el modelo o un script no reciban HTML); `Cache-Control` `immutable` en `/assets` y `no-cache` en `index.html`; la CSP la sigue poniendo el middleware (excepto `/api/docs`). Se monta al final en `main.py` y solo si existe `dist/`. Pruebas en `tests/api/test_spa.py` con una carpeta `dist` temporal.
  - 11.2 Revisión en 1280×720, 1366×768 y 1920×1080 con Playwright (capturas, sin desplazamiento horizontal) y revisión de accesibilidad. Lighthouse ≥ 90 lo mide el usuario en Chrome (no hay Lighthouse en el entorno).
  - 11.3 `apps/api/tests/e2e/test_main_flow.py` (Playwright para Python, Chromium y Firefox, 1366×768) con el flujo obligatorio de §15; responde traduciendo video → seña con `media/manifest.json` y `content/signs.csv` (sin «modo prueba», B89). `data-testid` de §15 en el frontend (`lesson-option-<n>`, `check-answer`, `continue`, `node-<id>`, `hearts`). `alas e2e`: compila la SPA, migra y siembra `alas_test`, arranca uvicorn en modo producción en un puerto libre, instala los navegadores si faltan, ejecuta `pytest -m e2e` y detiene el servidor. `alas start-prod`: `npm run build` + uvicorn sin recarga.
  - 11.4 `Dockerfile` multi-etapa de §17.1 (uv con versión fija), `.dockerignore` (sin `ml/`, `.github/`, `raw/`, `node_modules`, `.venv`, `.env`), `docker build` y arranque local; `README.md` con instalación, comandos, despliegue Render + Neon y el checklist de §17.3. El despliegue en Render + Neon y el `git push` los hace el equipo (D-006: aún no hay repositorio remoto).
  - 11.5 `app/content/demo.py` + `alas db seed-demo [--reset] [--allow-production]`: servicios reales (`LessonSessionService`, `ReviewService`) con un reloj simulado, fechas relativas a hoy (10:00 de Bogotá), respuestas tomadas del servidor; se niega en producción sin `--allow-production` y `DEMO_PASSWORD` (B84). Prueba de API con `FakeClock`: racha 5 en riesgo, 16 lecciones de M1, M2-N1-L1 disponible, 3 letras falladas en la cola, 5 vidas, 6 logros; dos ejecuciones con `--reset` dan lo mismo.
- Hecho:
  - **11.1** `app/core/spa.py` (`SpaFiles`, `SpaMount`): SPA con *fallback*; 404 JSON bajo `api`, `media`, `mediapipe`, `models` y `assets`; caché `immutable` en `assets/` y `no-cache` en el resto; CSP del middleware. 62 pruebas en `tests/unit/test_spa.py` (con *path traversal* y el manifiesto dentro de `dist`).
  - **11.3** `tests/e2e/test_main_flow.py` con el flujo obligatorio de §15. Responde con `manifest.json` y `signs.csv`, sin «modo prueba». `alas e2e` **en verde en Chromium y Firefox**. `data-testid` de §15 en el frontend. `alas start-prod` implementado.
  - **11.4 (parte del equipo pendiente)** `Dockerfile` en 5 etapas (MediaPipe con `alas camera-assets`), `.dockerignore`, `README.md` con instalación, comandos, demo, despliegue y checklist de §17.3. `docker build` en verde. La imagen arranca contra PostgreSQL:
    - aplica las migraciones y carga el contenido;
    - `/api/health` responde 200 y `/aprender` sirve la SPA;
    - `/api/docs` y `/media/manifest.json` dan 404;
    - `assets/` lleva `immutable`;
    - corre con uid 10001.
  - **11.5** `app/content/demo.py` + `alas db seed-demo`, con servicios reales y reloj simulado (§17.4). 31 pruebas de API y 10 de guardas (B84).
  - **11.2 (parte automatizable)** 9 pantallas × 3 resoluciones con Playwright: sin desplazamiento horizontal, controles con nombre accesible, imágenes con `alt`, `lang="es-CO"`. El aviso aparece a 900 px.
  - Fuera de plan, pedido por el usuario: las actividades que la lección no trae dicen «No incluida en esta lección» (D-034.6).
  - Decisiones: D-034.
- Revisión:
  - **`verificador-fase`:** APROBADO CON OBSERVACIONES. El contraste de «No incluida» quedaba en 2,7:1; se corrigió con gris AA sin opacidad.
  - **`revisor-codigo`:** 1 bloqueante, el manifiesto publicado por la SPA con rutas normalizadas (B54). Corregido con pruebas.
  - Importantes corregidos:
    - la demo no borra cuentas reales;
    - `alas e2e` solo trabaja en bases `_test`;
    - `.dockerignore` excluye los `.env` de todas las carpetas;
    - contraste de «No incluida».
  - Menores corregidos:
    - validación de `DEMO_PASSWORD` antes de tocar la base;
    - la demo no queda a medias;
    - `next()` sin valor por defecto;
    - docstring de la prueba de guardas;
    - código de la imagen de root.
  - La prueba obsoleta «comandos pendientes» se reemplazó por una prueba de la guarda `_test`: llamaba de verdad a `e2e` y `start-prod` dentro de `alas check`.
- Verificación manual pendiente (usuario):
  - **Lighthouse:** en Chrome, desde `/aprender`, Accesibilidad ≥ 90.
  - **Demo:**
    1. `uv run alas db seed-demo --reset`, luego `uv run alas start-prod`.
    2. Entra a http://localhost:8000 con `demo@alasdesenas.co` / `demo-alas-2026`.
    3. Comprueba: racha 5 en riesgo, 5 vidas, Módulo 1 completo con M1-N1 dorado, M2-N1-L1 disponible, un repaso pendiente con 3 letras y 6 logros.
    4. Haz M2-N1-L1: la racha debe subir a 6.
  - **Lección L1:** la tarjeta 4 dice «No incluida en esta lección».
- Pendiente / riesgos:
  - ~~**11.2:** falta medir Lighthouse.~~ **Hecho (06/11/2026):** Lighthouse medido por el usuario en Chrome (escritorio, `alas start-prod`, `/aprender`): **Accesibilidad 100**, **Rendimiento 94**.
  - **11.4, despliegue en Render + Neon:** lo hace el equipo y necesita el repositorio en GitHub (0.8 / D-006).
  - ~~`--forwarded-allow-ips='*'`~~ **Resuelto (D-035):** la IP del límite de inicio de sesión y de registro sale del valor que agrega el proxy de confianza (`TRUSTED_PROXY_HOPS`), nunca del que escribe el cliente; la imagen arranca con `--no-proxy-headers`. Cambia el comando de §17.1: **el equipo debe aprobarlo**. Al desplegar, comprobar en Render que dos personas distintas reciben IP distintas.
  - **`alas e2e` y `alas check`:** no deben correr a la vez, porque comparten `alas_test`.
  - **Docker:** la red dentro del contenedor cortó `npm ci` una vez; se agregaron reintentos.

## Mejoras posteriores al cierre (11/11/2026)
- **Cámara del alfabeto** (D-038, D-040, D-041), integrada desde la rama `prueba/optimizacion-camara`. El punto de guardado anterior es la etiqueta `antes-prueba-camara`.
  - Un análisis por cuadro de la cámara (`requestVideoFrameCallback`), modelo denso calculado en JavaScript y reconocimiento por tiempo (250 ms estables). Contador de FPS solo para quien administra.
  - 2 = V y 3 = W como señas equivalentes, igual que B = 4.
  - Suma de probabilidades de los pares equivalentes: con el modelo publicado, el 3 pasa el umbral del 41 % al 60 % de las veces, la B del 74 % al 89 % y el 2 del 48 % al 58 %, sin más errores.
  - Reentrenar con aumento de datos o con clases equilibradas **no** mejoró (validación cruzada por persona): el modelo publicado se queda.
- **Iconos** propios para la racha, el néctar y las vidas (D-042), en lugar de los emojis.
- Verificación manual pendiente (usuario):
  - En `/camara` con una cuenta de administrador: anotar FPS y ms por cuadro en 2 portátiles (meta ≥ 12 FPS); el 2 debe mostrar «V / 2» y el 3 «W / 3».
  - Con una cuenta de estudiante: no debe aparecer el contador de FPS.
  - Barra superior, panel «Tu día» y una lección: la llama, la flor y el corazón se ven bien, y el corazón late al perder una vida.
- Pendiente del equipo: ratificar la interpretación de R8.2 de D-041; el intérprete confirma 2 = V y 3 = W.

## Plan de mejora de la cámara de movimiento, versión reducida (12/11/2026, D-045)
Rama `feat/camara-movimiento-lsc54`. Se hicieron solo los pasos más factibles del plan (`docs/plan-mejora-camara-movimiento.md`): 80/100 en el análisis, frente a 52/100 del plan completo.
- **Hecho:**
  - **Paso A, captura manual** en Cámara beta y en `/admin/gestos`: «Yo marco el inicio y el fin», con «Terminar» y «Cancelar», entre 0,5 y 4 s. El modo de 2 s sigue siendo el predeterminado y las lecciones no cambian. Funciona con el modelo publicado sin reentrenar, porque la secuencia es la misma de 30 cuadros.
  - **Paso B:**
    - Guía de grabación en `docs/guia-grabacion-gestos.md`.
    - El colector ofrece las 18 señas del mapeo, más NINGUNA.
  - **Paso C, procedimiento:**
    - `train_sequence.py` evalúa con el umbral 0,70 de la aplicación y reporta por seña el acierto, las no reconocidas, las confusiones y las falsas detecciones.
    - Calcula las señas publicables (≥ 80 %, D-043).
    - `--balance` aplica pesos por clase.
    - Cuaderno de Colab `ml/notebooks/entrenamiento-gestos.ipynb`, con dos candidatos en carpetas aparte.
  - **Importador:** arrastrar carpetas, y si se suelta fuera de la zona el navegador ya no abre el video.
- **No hecho, por decisión:** el visor de fotogramas y el recorte editable (etapas 2 y 3), el inicio y el final automáticos, y una representación nueva (`holistic-v3`).
- **Verificación:**
  - Vitest: 20 pruebas nuevas en `capture.test.ts`, `lifecycle.test.ts`, `GestureCamera.test.tsx`, `GesturePractice.test.tsx`, `GestureDatasetPage.test.tsx` y `drop-files.test.ts`, más 3 en `ImportPage.test.tsx`.
  - `ml/tests`: 45 en verde, 6 nuevas, en un entorno temporal con NumPy y sin TensorFlow.
  - ESLint, tsc y ruff sin errores.
- **Revisión de `revisor-codigo`:** sin bloqueantes. Corregidos:
  - **Importantes:**
    - La parada temprana elegía la época con las mismas personas que se evaluaban; ahora usa otras personas del entrenamiento (`fold_split`).
    - `--balance` devuelve pesos para todas las clases, porque Keras falla si falta una.
    - Pruebas nuevas: un «Terminar» viejo no cierra la grabación siguiente; salir a mitad de una captura apaga la cámara (R8.5); al salir del importador se quitan los listeners.
    - Al arrastrar, solo cuenta lo último que se soltó y nada se aplica durante una importación. Aparece «Leyendo lo que soltaste…», y un error de lectura tiene su propio mensaje.
  - **Menores:**
    - El umbral se compara en doble precisión, igual que en TypeScript.
    - El modo de captura queda fijo durante la grabación.
    - El foco vuelve al botón de grabar y «Cancelar» muestra un aviso.
    - El alias del colector se fija al empezar a grabar.
    - `--out` ahora es obligatorio en `train_sequence.py`, para que un entrenamiento de prueba no sobrescriba el modelo publicado.
    - Textos del cuaderno.
  - Descartado: el cursor «no se puede soltar» fuera de la zona, que es solo cosmético.
- **No hay modelo nuevo entrenado ni mejora de precisión medida.**
- **Verificar a mano:**
  1. En `/camara` → «Señas con movimiento», elige «Yo marco el inicio y el fin», haz «hola» y pulsa «Terminar»: debe reconocerla igual que en el modo de 2 s.
  2. Pulsa «Terminar» enseguida: debe decir que la grabación fue muy corta.
  3. «Cancelar» no evalúa nada.
  4. Una lección con cámara de gestos sigue con 2 s.
- **Pendiente (personas):**
  - Grabar al equipo con la guía.
  - Entrenar en Colab con LSC-54 más esas grabaciones.
  - Publicar solo las señas publicables, con una copia del modelo anterior.
  - Probar con personas que no grabaron.
  - El equipo aprueba D-045, porque el anexo A.4 habla de ventanas de 2 s.

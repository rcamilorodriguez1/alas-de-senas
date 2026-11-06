# Plan de implementación — Alas de Señas

> **Spec-Driven Development · documento 3 de 3.** Lista ordenada de tareas para el agente de IA.
> Reglas:
> - Ejecuta **una tarea a la vez**, en orden. Al terminarla, marca `[x]` y ejecuta `uv run alas check` (ruff, mypy, pytest, ESLint, tsc, Vitest y tipos de la API al día).
> - No marques una tarea si `alas check` falla. No borres ni saltes pruebas.
> - Cada tarea indica los requisitos que cumple (`_R4.4_`) y, cuando aplica, la verificación manual (**Verificar:**).
> - Al terminar cada grupo, actualiza `docs/PROGRESS.md` y haz commit `feat(grupo-N): …`.
> - Lenguajes: **Python** en todo excepto `apps/web` (**TypeScript**). Detalle técnico: `design.md` y `docs/especificacion.md` (v3.3).

---

## Grupo 0 — Base del proyecto

- [x] **0.1** `pyproject.toml` raíz (workspace de uv con `apps/api`, `exclude = ["ml"]`, configuración de ruff con `per-file-ignores` y de mypy con `overrides`, §19.3), `.python-version` (3.12), `uv.lock`, `.env.example`. `.gitattributes` y `.gitignore` ya vienen en el kit: solo completarlos si falta algo.
- [x] **0.2** Verificar que el kit de arranque está completo (`CLAUDE.md`, `.claude/`, `docs/`) y probar el harness con los comandos de `docs/harness.md` §7 (deben bloquear y permitir lo indicado). No modificar `.claude/` ni la especificación.
- [x] **0.3** `apps/api` como paquete instalable (`alas-api`, `[build-system]` hatchling, paquete `app`, script `alas`). FastAPI con configuración `pydantic-settings` (valores por defecto en desarrollo para que arranque sin `.env`; en producción falla si falta `DATABASE_URL` o `JWT_SECRET` o si el secreto es el de desarrollo), `AppError` + manejadores de error `{ statusCode, code, message }` (incluida la traducción de errores de Pydantic), cabeceras de seguridad y `GET /api/health` que verifica la BD.
- [x] **0.4** SQLAlchemy 2.0 (`db.py` con `pool_pre_ping` y `serializable_session()`, D21) + Alembic (`script_location = %(here)s/alembic`, URL desde la configuración); `docker-compose.yml` con PostgreSQL 16 en el puerto 5433 y `docker/init-test-db.sql` que crea `alas_test`.
- [x] **0.5** Calidad Python: ruff (lint + formato), `mypy --strict` con plugin de Pydantic, pytest + pytest-cov; `tests/test_architecture.py` (el dominio no importa `fastapi` ni `sqlalchemy`).
- [x] **0.6** `apps/web`: React + Vite + TypeScript estricto + Tailwind + React Router + TanStack Query; proxy `/api` → `localhost:8000`; fuentes `@fontsource`; ESLint y Vitest.
- [x] **0.7** CLI `alas` (Typer): `dev`, `check`, `gen-api`, `db up|migrate|seed|seed-demo|reset`, `content …`, `camera-assets`, `e2e`, `start-prod` (los que aún no tengan contenido muestran «Pendiente de la fase N»). Dependencia `get_clock` inyectable (D22).
- [ ] **0.8** Integración continua: `.github/workflows/ci.yml` ya viene en el kit (no reescribirlo). Las pruebas de API aplican las migraciones a `alas_test` en un fixture de sesión. Subir el repositorio a GitHub y confirmar que el flujo pasa. _R10.8_
- [x] **0.9** Compatibilidad TensorFlow.js: instalar `@tensorflow/tfjs@4.22.0` (versión exacta) en `apps/web`, copiar `docs/plantillas/tfjs-compat.test.ts` a `apps/web/src/camera/` sin cambiar su lógica y verificar que pasa con `ml/fixtures/tfjs-smoke/` (no requiere instalar TensorFlow). _R8.8_
  **Verificar:** `uv run alas dev` levanta ambos servidores y `http://localhost:5173/api/health` responde `{ ok: true, db: true }`. `uv run alas check` en verde (incluida la prueba `tfjs-compat`). CI en verde en GitHub.

## Grupo 1 — Dominio en Python (pruebas primero)

- [x] **1.1** `domain/dates.py`: `Clock`, `to_local_day`, `add_days`, `diff_days` (+ `tzdata`); pruebas de medianoche en Bogotá, cambio de año y `datetime` sin zona horaria. _R5.5_
- [x] **1.2** `domain/text.py`: `normalize_text` y `levenshtein` con pruebas (`GRACÍAS`, `¿Cómo estás?`, `Año`, `BAÑO`). _R7.1_
- [x] **1.3** `round_half_up` y `score_session` con pruebas de umbral (3/5, 7/10, 6/10, 2/3, 1/8, total 0). _R3.4_
- [x] **1.4** `RewardPolicy` (XP y néctar) con pruebas. _R5.1–5.4_
- [x] **1.5** `compute_progress` con pruebas (usuario nuevo, cadena, cambio de módulo, módulo no publicado, contenido agregado después). _R3.2–3.7_
- [x] **1.6** `StreakPolicy.apply_activity` y `display` con pruebas (incluida «lección y repaso el mismo día suben 1»). _R5.5–5.8_
- [x] **1.7** `ReviewScheduler` con pruebas. _R6.4–6.5_
- [x] **1.8** Modelos Pydantic discriminados de `payload`/`answer`; `ExerciseEvaluator` (clase abstracta), **7** evaluadores (incluido `SPELLING`) y registro; opciones con tokens opacos recibiendo una función `tokenize` inyectada (D20); prueba de que `to_public()` nunca incluye `correctId`, `signId` ni slugs en las opciones. _R4.4–4.7_
- [x] **1.9** `AchievementRule` (9 logros) y `evaluate_achievements`. _R5.10_
- [x] **1.10** `generate_exercises` determinista (§6.7: L1 con repaso `MEANING_TO_VIDEO`, L3 con `MEANING_TO_VIDEO`, fórmula de preguntas de L4, `SPELLING` en ALPHABET, reparto ALPHABET por posición, `cameraLabel` solo en letras `static`, nada para módulos no publicados, ≥ 4 ejercicios con puntaje); separación de palabras en letras por coincidencia más larga (con y sin `letra-ll`); prueba que ejecuta el generador en dos procesos distintos y compara resultados. _R9.8, R9.9, R9.11, R4.10c_
- [x] **1.11** `HeartsPolicy` (`current`, `lose_one`, `gain_one`, `refill`) con los casos de §7.10. _R5.13–5.16_
- [x] **1.12** `build_review_items` (repaso: alterna los dos tipos, distractores solo de señas vistas, determinista). _R6.7_
  **Verificar:** cobertura de `app/domain` ≥ 95 %.

## Grupo 2 — Contenido y base de datos

- [x] **2.1** `infra/models.py` (SQLAlchemy 2.0) y primera migración Alembic revisada a mano; prueba que aplica las migraciones sobre una BD vacía. _R9_
- [x] **2.2** `content/curriculum.json` (M1: Saludos y cortesía · Presentaciones · Alfabeto A–M · Alfabeto N–Z), `content/signs.csv` (prellenado con la columna `motion`; `meaning` y `usage_example` redactados; `how_to` vacío), `content/conversations.yaml` (`# revisar`; listas `spelling` de M1-N3 y M1-N4), `content/intro.json`, fuente en `content/fonts/`. _R1.2, R3.1, R9.1_
- [x] **2.3** Lector CSV (`utf-8-sig`, detección de mojibake). _R9.5_
- [x] **2.4** `alas content check` (con y sin `--skip-raw`) con todas las validaciones de §6.6 (incluidas `motion` y letras `dynamic` en `labels.json`) y reporte. _R9.6, R8.3a_
- [x] **2.5** `alas content placeholders` (Pillow + ffmpeg; nunca reemplaza videos reales) con nombres por contenido y `media/manifest.json` (D19). _R9.2_
- [x] **2.6** `alas content videos` (normalización, póster, nombre por contenido, manifiesto, limpieza de archivos huérfanos, caché local, sugerencia de slug parecido). _R9.3, R9.4_
- [x] **2.6b** Plan B de imágenes (§6.4.1): `app/content/images.py` (EXIF, reducción, lienzo 1280×720, fundido, ffmpeg), emparejamiento de nombres (`slug.jpg`, `slug__N.jpg`), prioridad video > imágenes > relleno, validaciones (huecos, máx. 4, `.heic`, resolución, `how_to` vacío) y `source`/`media_source` en manifiesto y BD; pruebas con imágenes generadas en la prueba (rotada por EXIF, 4000×3000, 1001×777, `numero-1.jpg`). _R9.12_
- [x] **2.7** `alas db seed` idempotente con `INSERT … ON CONFLICT DO UPDATE` (datos de video desde el manifiesto, módulos no publicados sin lecciones, ejercicios generados, logros y administrador opcional). Verificar que los videos procesados y el manifiesto quedan en git. _R9.7, R9.10_
  **Verificar:** `uv run alas content all` sin errores; 109 videos de relleno; `alas db seed` dos veces deja los mismos conteos.

## Grupo 3 — Autenticación

- [x] **3.1** `AuthService` + router: registro (correo normalizado, bcrypt, 8–72 bytes, aceptación de datos), login (hash ficticio si el correo no existe), refresh rotativo con SHA-256, logout, `GET/PATCH /me`; slowapi: login 5/min por IP + correo, registro 10/min por IP, rutas autenticadas por usuario. _R2_
- [x] **3.2** Pruebas de API: correo duplicado, credenciales inválidas, contraseña de 73 bytes, refresh rotado, refresh revocado tras logout, límite de intentos. _R2.3–2.7_
- [x] **3.3** `alas gen-api` + cliente HTTP tipado en `apps/web/src/lib/api.ts` con token en memoria y renovación *single-flight*; arranque con `refresh` y pantalla de carga; guardas de ruta. _R2.6, R10.4_
- [x] **3.4** Páginas `/ingresar` y `/registro` (React Hook Form + Zod en el cliente) con mensajes en español, mostrando también los errores por campo del servidor. _R2.1_
  **Verificar:** registrarse → `/aprender`; recargar mantiene la sesión; cerrar sesión obliga a volver a ingresar.

## Grupo 4 — Ruta de aprendizaje

- [x] **4.1** `GET /learning-path` y `GET /nodes/{id}` con `compute_progress` (carga con `selectinload`, sin N+1). _R3_
- [x] **4.2** Layout de escritorio y pantalla «solo computador» para < 1024 px. _R10.1_
- [x] **4.3** `HomePage` con nodos en zigzag, estados (🔒 + texto), popover y módulo «Próximamente». _R3.1, R3.5, R3.6_
- [x] **4.4** Componente `Mascot` (Tomi SVG) con estados de ánimo y movimiento reducido. _R5.12_
  **Verificar:** usuario nuevo solo ve disponible M1-N1-L1.

## Grupo 5 — Lecciones

- [x] **5.1** `LessonSessionService.start` (403 `LESSON_LOCKED`, 403 `NO_HEARTS` salvo en Aprende, 404 `LESSON_NOT_FOUND`), `answer` (`ON CONFLICT DO NOTHING RETURNING`, tokens, 409/410, descuento de vidas solo si se insertó, usuario con `FOR UPDATE`), tiempos con `Clock` (D22), `complete` (sesión SERIALIZABLE propia, `FOR UPDATE`, reintentos ante `SerializationFailure`, idempotente, `SESSION_INCOMPLETE`, `SESSION_EXPIRED` por 24 h o contenido recargado, tope de 15 min). _R3.8, R4.4–4.10c_
- [x] **5.2** Pruebas de API (con `FakeClock`): respuestas ocultas y opciones sin slugs, segundo intento no cambia el resultado ni descuenta otra vida, doble `complete` no duplica XP, `complete` incompleto → 409, sesión de otro usuario → 404, sesión expirada → 410, error en L1 no quita vidas, 0 vidas bloquea L2 pero la lección empezada se termina. _R4.4, R4.6, R4.10–4.10b, R5.13–5.15_
- [x] **5.3** `SignVideoPlayer` (velocidad, repetir, error con reintento, etiqueta de relleno, etiqueta «Secuencia de imágenes» sin velocidad lenta, precarga). Prueba de que `/media` responde `206` a peticiones con `Range` y envía `Cache-Control: immutable`. _R4.3, R4.12, R9.3_
- [x] **5.4** `LessonPage`: encabezado, actividades en secuencia, agrupación por seña, confirmación al salir. _R4.1, R4.2, R4.11_
- [x] **5.5** Componentes `ObserveActivity`, `SelectMeaningActivity`, `MemoryMatchActivity`, `ProduceActivity` (autoevaluación por ahora), `ConversationActivity`, `SpellingActivity`; manejo de `SESSION_EXPIRED` y del doble montaje de StrictMode. _R4.5, R4.7, R4.8_
- [x] **5.6** Atajos 1–4 y Enter; ajuste para 1366×768. _R4.13, R4.14_
  **Verificar:** completar L1 desbloquea L2; en DevTools → Network no aparece la respuesta correcta antes de responder.

## Grupo 6 — Gamificación

- [x] **6.1** `GamificationService.apply_completion` dentro de la transacción de `complete` (logros con `on_conflict_do_nothing` + `RETURNING`). _R5.1–5.8, R5.10_
- [x] **6.2** `GET /gamification/stats` (con `hearts`), `/achievements`, `POST /gamification/streak-freeze`, `POST /gamification/hearts-refill`; `HEARTS_ENABLED`. _R5.9, R5.11, R5.14, R5.16_
- [x] **6.3** `CelebrationModal` y panel derecho actualizado (racha, néctar, vidas). _R4.9, R5.12_
- [x] **6.4** Página `/logros`.
- [x] **6.5** Vidas en la interfaz: contador ❤️ (barra superior, panel, encabezado de lección), animación al perder una, modal «Sin vidas» con repasar / recargar / esperar (cuenta regresiva). _R5.13–5.15_
  **Verificar:** comprar un protector descuenta 50 de néctar; un logro aparece una sola vez; con 0 vidas L2 muestra el modal y L1 se puede hacer.

## Grupo 7 — Progreso y repaso

- [x] **7.1** `GET /progress/summary`, `/history`, `/units`. _R6.1–6.3_
- [x] **7.2** `ReviewService` (modelos `ReviewSession`/`ReviewAnswer` de §5, creados en la tarea 2.1) (`get_queue`, `start` con 409 `NO_REVIEWS_DUE` y reutilización de la sesión abierta, `answer`, `complete` SERIALIZABLE e idempotente que reprograma señas, registra actividad para la racha y da +1 vida con ≥ 80 %). **No existe** un endpoint donde el cliente envíe sus aciertos (D23). _R6.4–6.8, R5.5, R5.14_
- [x] **7.3** Pruebas de API del repaso: tokens sin slugs, cuenta para la racha, segunda sesión el mismo día → 409, no quita vidas, da vida con ≥ 80 %.
- [x] **7.4** Páginas `/progreso` (Recharts) y `/repaso` (tarjeta de lección con la actividad 2).
  **Verificar:** fallar una seña la pone en «Señas por repasar»; repasarla al día siguiente mantiene la racha.

## Grupo 8 — Diccionario

- [x] **8.1** `DictionaryService`: `ILIKE` sobre `normalized_word` (escapando `%` y `_`), sugerencias por Levenshtein ≤ 2, categorías no vacías, ficha con lección relacionada, favoritos idempotentes. _R7_
- [x] **8.2** Páginas `/diccionario` y `/diccionario/:slug`. _R7.4–7.7_
  **Verificar:** «GRACÍAS» encuentra «Gracias»; «grasias» la sugiere.

## Grupo 9 — Introducción

- [x] **9.1** `GET /api/intro` (público) y página `/bienvenida` con 6 tarjetas y mini-quiz; redirección inicial desde `/`. _R1.1–1.5_
- [x] **9.2** `introCompleted` en el registro y logro «Primer aleteo». _R1.6_

## Grupo 10 — Cámara (beta)

- [x] **10.1** `alas camera-assets` (WASM y modelos `.task` en `apps/web/public/mediapipe/`). _R8_
- [x] **10.2** `normalizeLandmarks` (TypeScript) con pruebas Vitest. _R8_
- [x] **10.3** Reconocedor: *singleton*, timestamps crecientes, pausa en pestaña oculta, limpieza, `tf.tidy()`, `MockClassifier`. _R8.5, R8.6_
- [x] **10.4** Página `/camara` con video en espejo, puntos, seña detectada, confianza y errores de permiso. _R8.1–8.4_
- [x] **10.5** Colector `/admin/dataset` que exporta `dataset.json` (`hand-v1`, 63 valores, etiquetas = slugs de la seña o `NINGUNA`, alias, versión de MediaPipe). `POST /recognition/results` evalúa el logro HUMMINGBIRD_EYE. _R8.7_
- [x] **10.6** Entorno `ml/` con el `ml/pyproject.toml` del kit (versiones verificadas: no cambiarlas sin regenerar `ml/fixtures/tfjs-smoke` y pasar `tfjs-compat`; si TensorFlow no instala en un computador, usar Colab) y `ml/train_static.py` (rechaza letras `motion = dynamic`): validación, separación por persona, semillas fijas, matriz de confusión, exportación con `labels.json` y `meta.json`; cuaderno equivalente para Colab. _R8.7_
- [x] **10.7** `ProduceActivity` con cámara cuando la seña está en `labels.json`; prueba Vitest de que `labels.json` coincide con las salidas del modelo. _R4.8_
- [x] **10.8** Entrenar y copiar el modelo de 5–10 letras `static` confirmadas por el intérprete, con datos de ≥ 3 personas (copiar la carpeta tal cual: `model.json` + `group1-shard*.bin`).
  **Verificar:** la letra entrenada se reconoce; sin mano aparece «NINGUNA»; la cámara se apaga al salir.

## Grupo 10B — Cámara holística: dos manos + rostro (opcional, después del Grupo 10)

> Detalle en `docs/anexo-camara-holistica.md`. Solo si el equipo lo decide; no debe retrasar el Grupo 11.

- [x] **10B.1** Descargar `holistic_landmarker.task`; prueba de arranque (GPU → CPU) y nombres de *blendshapes*. _R8_
- [x] **10B.2** `buildHolisticFrame` (TypeScript, 159 valores, mano dominante, reflejo para zurdos) + pruebas; `dominantHand` en `PATCH /me`. _R8_
- [x] **10B.3** `FrameSequencer` (remuestreo a 30 cuadros, huecos, calidad) + pruebas. _R8_
- [x] **10B.4** Interfaces `FeatureExtractor`, `SignClassifier`, `RecognizerFactory`; el alfabeto sigue igual. _R8_
- [x] **10B.5** Guía visual de captura y medición de FPS. _R8.1_
- [x] **10B.6** Colector `holistic-v2` con cuenta regresiva de 2 s. _R8.7_
- [x] **10B.7** `ml/train_sequence.py` (GRU con `reset_after=False`, aumentos, separación por persona, exportación con `meta.json`) y fixtures de paridad `ml/fixtures/holistic_v2_cases.json` probados con pytest y Vitest. _R8.7_
- [x] **10B.8** Importador `/admin/importar` (navegador) + `content/dataset-mapping.csv` + página `/creditos`. _R8.7_
- [x] **10B.9** `ProduceActivity` en modo gestos y retroalimentación de Tomi. _R4.8_
- [x] **10B.10** Entrenar 3–5 señas con ≥ 5 personas; validar con personas no vistas (≥ 80 %).

## Grupo 11 — Cierre

- [x] **11.1** FastAPI sirve la SPA (con *fallback* a `index.html` fuera de `/api`, `/media`, `/mediapipe`, `/models`, `/assets`), aplica la CSP (excepto `/api/docs`) y las cabeceras de caché (`immutable` para `/media/v`, `/media/p`, `/assets`; `no-cache` para `index.html`). _R10.4_
- [x] **11.2** Revisión en 1280×720, 1366×768 y 1920×1080; accesibilidad (Lighthouse ≥ 90). _R10.1, R10.5_
- [x] **11.3** Prueba E2E del flujo principal con **Playwright para Python** (`alas e2e`, 1366×768); responde bien traduciendo video ↔ palabra con `manifest.json` y `signs.csv`, sin «modo prueba» en la API (B89). _R10.6_
- [ ] **11.4** `Dockerfile` multi-etapa (§17: `UV_NO_SYNC`, binarios de `.venv`, `CONTENT_DIR`/`MEDIA_DIR`/`WEB_DIST_DIR`), probar `docker build` y arranque local con `alas db seed` sin `raw/`; despliegue (Render + Neon), `README.md` y checklist de la demostración.
- [x] **11.5** `alas db seed-demo` (`app/content/demo.py`, §17.4): servicios reales con reloj simulado, fechas relativas a hoy, `--reset`, bloqueo en producción; prueba de API con `FakeClock` que verifica el estado final. Actualizar el checklist de §17.3 en `README.md`. _R10.9_
  **Verificar:** `alas e2e` en verde; la app desplegada responde en HTTPS; `alas db seed-demo --reset` deja racha 5, repaso pendiente y M2-N1-L1 disponible.

## Grupo 12 — Tienda: accesorios de Tomi (opcional, después del Grupo 11)

> Detalle en `docs/DECISIONES.md` D-033. **Requiere que el equipo apruebe D-033** (amplía el alcance de §1). No debe retrasar el Grupo 11.

- [ ] **12.1** `domain/policies/shop.py` (pruebas primero): `can_purchase` → `ALREADY_OWNED` / `NOT_ENOUGH_NECTAR` / `ITEM_LOCKED` (módulo requerido sin terminar); `can_equip` solo con accesorios comprados; un accesorio a la vez. Cobertura del dominio ≥ 95 %. _D-033_
- [ ] **12.2** `content/shop.json` (id, nombre, precio, `requiredModule` opcional, dibujo) validado por `alas content check` (ids únicos, precios > 0, módulo existente) y cargado por `alas db seed`. _D-033_
- [ ] **12.3** Modelos `ShopItem` y `UserItem` (PK compuesta `user_id` + `item_id`, `purchased_at` con `clock.now()`), `users.equipped_item_id` y migración Alembic; los accesorios entran en la exportación de la cuenta y se borran con ella. _D-033_
- [ ] **12.4** `GET /shop` (accesorios con `owned`/`equipped`/`locked`, néctar del usuario) y `POST /shop/items/{id}/purchase` (usuario `FOR UPDATE`, `ON CONFLICT DO NOTHING RETURNING`, descuenta solo si se insertó; 409 con el código del dominio); accesorio puesto en `PATCH /me` y `GET /me`; `alas gen-api`. Pruebas de API: dos compras a la vez descuentan una sola vez; sin néctar; bloqueado; poner uno no comprado → 409. _D-033_
- [ ] **12.5** Página `/tienda` y enlace «Tienda» en la barra lateral (mockup §3.1): secciones «Tu racha» (protector), «Vidas» (recarga cuando falta alguna y `HEARTS_ENABLED`) y «Accesorios de Tomi»; confirmar antes de comprar; mensajes «No tienes suficiente néctar» y «Termina el Módulo N para desbloquearlo». _D-033, R5.9, R5.14_
- [ ] **12.6** `Tomi` con accesorio (SVG encima de la mascota, sin cambiar sus pruebas actuales) en la ruta, la celebración y el perfil; texto alternativo con el accesorio; respeta movimiento reducido. _D-033_
  **Verificar:** comprar la gorra descuenta 40 de néctar y no se puede comprar otra vez; el birrete aparece bloqueado hasta terminar el Módulo 3; ponerse un accesorio lo muestra en la ruta y en la celebración; con 3 vidas la tienda ofrece recargar; la exportación de la cuenta incluye los accesorios.

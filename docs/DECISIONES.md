# Registro de decisiones — Alas de Señas

> Decisiones tomadas durante la implementación que no estaban en la especificación o que la ajustan.
> Usa el comando `/decision <texto>` para agregar entradas con el formato correcto.

## D-001 · Backend y herramientas en Python · 30/10/2026
- Contexto / problema: la v2 usaba TypeScript en todo el sistema.
- Opciones consideradas: TypeScript en todo (un solo lenguaje, tipos compartidos) · Python en todo lo que no corre en el navegador (estándar para IA, el equipo lo domina).
- Decisión: Python 3.12 (FastAPI, SQLAlchemy, Alembic, pytest) para servidor, dominio, contenido y pruebas; Python 3.11 + TensorFlow 2.15 para entrenar; TypeScript solo en `apps/web`.
- Consecuencias: tipos del frontend generados desde OpenAPI (`alas gen-api`); dos gestores (uv y npm).
- Secciones afectadas: especificación v3 completa.

## D-002 · Revisión técnica v3.1 · 30/10/2026
- Contexto / problema: la revisión de la v3 encontró 19 bugs de diseño (B54–B72): respuestas deducibles desde el JSON, caché de video vieja, videos ausentes en el despliegue, aislamiento SERIALIZABLE mal aplicado, sesiones vacías que daban racha, límites por IP que bloqueaban a toda la universidad, Docker y herramientas que no arrancaban.
- Opciones consideradas: parchear cada síntoma en la implementación · corregir la especificación antes de escribir código.
- Decisión: especificación v3.1 con D19 (videos por contenido + `manifest.json` versionado), D20 (tokens HMAC opacos en las opciones), D21 (sesión SERIALIZABLE propia para completar), ejercicio `SPELLING`, endpoint `/api/intro`, errores `SESSION_INCOMPLETE`/`SESSION_EXPIRED`, límites por usuario/correo, y ajustes de Docker, pyproject y configuración.
- Consecuencias: los videos procesados sí van en git (los originales no); reemplazar un video cambia su URL; recargar contenido invalida sesiones abiertas.
- Secciones afectadas: §5, §6.4–6.7, §7.6, §8, §11, §14.6, §16, §17, §19; requirements R1, R2.5, R4.4, R4.10a–c, R9.3, R9.8–R9.10; design.md; tasks.md.

## D-003 · Siete mejoras aprobadas por el equipo (v3.2) · 30/10/2026
- Contexto / problema: propuestas de la revisión técnica que el equipo decidió implementar.
- Decisión:
  1. **Alfabeto en dos nodos** (A–M y N–Z) con reparto por posición; «Saludos» y «Cortesía» se unen para conservar 4 nodos por módulo (máximo 9 señas por nodo; `con-permiso` pasa a solo diccionario).
  2. **Letras con movimiento:** columna `motion` (`static`/`dynamic`) en `signs.csv`, validación del modelo y lista de verificación con el intérprete (`docs/validacion-interprete.md`). Soporte de CH/LL/RR sin cambiar código.
  3. **Usuario de demostración:** `alas db seed-demo` con los servicios reales y fechas relativas a hoy.
  4. **Integración continua:** `.github/workflows/ci.yml` (alas check + E2E en `main`).
  5. **El repaso cuenta para la racha:** sesión de repaso evaluada por el servidor (D23); se elimina `POST /reviews/results`.
  6. **Vidas:** 5, −1 por error en L2–L4, +1 cada 4 h, +1 por repaso ≥ 80 %, recarga por 30 néctar; desactivables con `HEARTS_ENABLED` (D24).
  7. **Versiones de TensorFlow verificadas** (instalación limpia + conversión + carga en TensorFlow.js con salida idéntica): `tensorflow==2.15.1`, `tensorflowjs==4.22.0`, `numpy<2`, `setuptools<81`; `@tensorflow/tfjs` 4.22.0.
- Hallazgos de la verificación real (7): el GRU con `reset_after=True` (valor por defecto de Keras) **no carga** en TensorFlow.js → `reset_after=False` obligatorio (B73, hook del harness); `tensorflowjs` falla sin `setuptools` (B74); el conversor genera `group1-shard*.bin`, no `weights.bin` (B75).
- Además: D22 (tiempos con `Clock`), requerido por las vidas, la expiración y la demo.
- Consecuencias: más trabajo en los grupos 1, 5, 6, 7 y 11 (≈ 1,5 días); la cámara del alfabeto empieza con letras confirmadas como estáticas; riesgos B73–B89.
- Secciones afectadas: §1.1, §2, §3, §4.1, §5, §6.1, §6.2, §6.5–6.7, §7.5, §7.9, §7.10 (nueva), §8.1–8.5, §9.3, §10, §14.7 (nueva), §15.1 (nueva), §16, §17.3, §17.4 (nueva), §19; anexo A.7; requirements R3.1, R5.5, R5.13–16, R6.7–8, R8.3a, R8.8, R9.6, R9.11, R10.8–9; design.md; tasks.md 0.8, 0.9, 1.11, 1.12, 6.5, 7.2–7.4, 11.5.

## D-004 · Plan B: señas con imágenes si no se pueden grabar videos · 30/10/2026
- Contexto / problema: por razones externas podría no ser posible grabar los videos de las señas.
- Opciones consideradas: reproductor de imágenes aparte (cambia interfaz, ejercicios, diccionario y pruebas) · convertir las imágenes en un clip MP4 con el mismo formato que los videos.
- Decisión: D25 — `alas content videos` acepta `slug.jpg` (una imagen) o `slug__1.jpg`…`slug__4.jpg` (secuencia) y genera un clip (3 s fijo o 1,2 s por imagen con fundido). Prioridad video > imágenes > relleno. Prototipo verificado (EXIF, 4000×3000, medidas impares → 720p H.264).
- Consecuencias: se pueden mezclar videos e imágenes y pasar a video después sin tocar código. Pedagógicamente, las letras estáticas y los números no pierden nada; las señas con movimiento se entienden peor y requieren `how_to` escrito. La cámara no se afecta (se entrena con muestras de la webcam). Las imágenes deben ser propias o con permiso escrito.
- Secciones afectadas: §2 (D25), §5 (`media_source`), §6.4, §6.4.1 (nueva), §6.6, §14.7 (B90–B95), §18.1 (nueva); requirements R9.12–R9.13; design.md; tasks.md 2.6b y 5.3.

## D-005 · Ajustes técnicos del Grupo 0 · 30/10/2026
- Contexto / problema: detalles que la especificación no fija o que cambian con las versiones instaladas.
- Decisiones:
  1. **Errores de validación con estado 422** (el de FastAPI) y cuerpo `{ statusCode: 422, code: "VALIDATION_ERROR", message, fields }`; el campo es el último elemento de `loc` (alias camelCase).
  2. **`/api/health` devuelve 503 `{ ok: false, db: false }`** si la BD no responde (para que un monitor lo detecte).
  3. **TypeScript 5.9.3** (no 7.x): `typescript-eslint` exige `<6.1` y `openapi-typescript` exige `^5`. Dependencias npm con versión exacta (`--save-exact`).
  4. **Vitest con dos proyectos**: `dom` (jsdom) y `node` solo para `src/camera/tfjs-compat.test.ts`, que usa `node:fs` e `import.meta.url` con esquema `file:` (en jsdom falla). La plantilla se copió sin cambios.
  5. **Variables vacías** (`ADMIN_EMAIL=`, `ADMIN_PASSWORD=`, `DEMO_PASSWORD=`) se leen como `None` (= no configurado).
  6. **`JWT_SECRET` ≥ 32 caracteres en todo entorno**; en producción además debe estar definido explícitamente y no ser el de desarrollo.
  7. **`alas start-prod` queda «Pendiente de la fase 11»**: servir la SPA desde FastAPI es la tarea 11.1.
  8. **FastAPI 0.162** ya no expone las rutas incluidas en `app.routes` (usa un `_IncludedRouter` interno): la prueba de `test_main.py` comprueba la ruta de salud con `app.url_path_for("health")`.
  9. Todas las dependencias de §3 se agregaron en el Grupo 0 (incluidas las de grupos posteriores: PyJWT, bcrypt, slowapi, PyYAML, imageio-ffmpeg, Pillow, pytest-playwright) para no pedir permisos en cada fase.
- Consecuencias: ninguna sobre el diseño; el contrato de errores queda fijado para el Grupo 3 (páginas de registro).

## D-006 · Sin repositorio remoto por ahora · 30/10/2026
- Contexto / problema: el equipo quiere ver la aplicación funcionando antes de subir el código a GitHub.
- Decisión: la parte de la tarea 0.8 que exige subir el repositorio y ver el CI en verde queda **pospuesta**. El trabajo continúa solo con git local; la parte local de 0.8 (fixture de migraciones, lockfiles) ya está hecha.
- Consecuencias: R10.8 (CI automática) no se verifica hasta que se suba el repositorio; antes de la entrega hay que hacer `git push` y confirmar el job «alas check».

## D-007 · Reglas del dominio que la especificación no fija (Grupo 1) · 31/10/2026
- Contexto / problema: §6.7, §7 y §8.5 dejan abiertos detalles necesarios para que el generador y las políticas sean deterministas y probables.
- Decisiones:
  1. **Actividad** de cada tipo: OBSERVE 1 · VIDEO_TO_MEANING, MEANING_TO_VIDEO y MEMORY_MATCH 2 · PRODUCE 3 · CONVERSATION y SPELLING 4.
  2. **Reto final (L4):** las señas del nodo se barajan con el rng de la lección y se recorren en ciclo; las preguntas pares son VIDEO_TO_MEANING y las impares MEANING_TO_VIDEO.
  3. **Conversaciones:** L2 y L3 usan la primera conversación de 2 turnos con señas ya enseñadas; L4 la primera de 3 turnos. Opciones de cada turno = respuesta + distractores del YAML.
  4. **Deletreo:** L2 usa la primera palabra válida; L3 y L4 prefieren una no usada antes en el nodo. Las palabras deben estar en mayúsculas (una en minúsculas es un error de contenido).
  5. **Distractores:** nivel 3 «misma categoría» = señas de otros nodos publicados de la misma categoría; dentro de cada nivel el orden lo decide el rng. Lógica compartida con el repaso (`domain/content/distractors.py`).
  6. **MEMORY_MATCH:** señas del nodo enseñadas hasta esa lección; si son más de 6, 6 elegidas con el rng.
  7. **Repaso:** distractores solo de señas vistas (mismo nodo → misma categoría → resto); permite 2 a 4 opciones; solo si quedan menos de 2 se completa con señas no vistas.
  8. **`cameraLabel`** solo en letras `static` de nodos ALPHABET (las palabras no tienen modelo de cámara todavía).
  9. **Módulo publicado:** LOCKED si su primer nodo está bloqueado, COMPLETED si todos sus nodos están COMPLETED o GOLDEN, si no IN_PROGRESS.
  10. **Vidas:** `gain_one` conserva el avance de la recarga; con 0 vidas `lose_one` devuelve el estado materializado.
- Consecuencias: el contenido de §6.5 (conversaciones y palabras) debe cumplir estas reglas; `alas content check` (Grupo 2) las verificará con los mismos generadores.
- Nota tras la verificación del Grupo 1: D-007.7 se aparta de §8.5 («solo señas vistas», `optionIds[4]`) en un caso límite: con menos de 2 señas vistas se completa con señas no vistas, y el repaso puede tener 2–3 opciones. En la práctica no ocurre (L1 enseña ≥ 2 señas); el servicio de repaso (Grupo 7) solo programa señas de lecciones completadas. D-007.5: el nivel «misma categoría» puede incluir señas de nodos posteriores (aún no enseñadas); pendiente de confirmar con el equipo.

## D-008 · Orden público de las opciones por token y estímulos fuera de sus opciones · 31/10/2026
- Contexto / problema: la revisión del Grupo 1 demostró que la respuesta se deducía en el 100 % de los ejercicios. §7.6 manda barajar con `random.Random(f"{session_id}:{exercise_id}")`, pero el cliente conoce ambos valores y la correcta iba primera en el payload: repitiendo el barajado se sabe qué opción es la correcta (también las parejas de MEMORY_MATCH). Además, en conversaciones como «hola → hola» el video del estímulo es idéntico al de la opción correcta (B54).
- Opciones consideradas: barajar el payload en el generador (no protege MEMORY_MATCH) · semilla derivada del secreto en el servicio (depende de que cada servicio lo haga bien) · **ordenar las opciones públicas por su token** (HMAC con secreto, D20).
- Decisión:
  1. `to_public()` ya no recibe `rng`: ordena las opciones por token. Es estable dentro de la sesión e impredecible sin el secreto; videos y palabras tienen tokens independientes. **Se aparta del texto literal de §7.6** (barajado con semilla pública).
  2. En las conversaciones, el estímulo no puede aparecer entre sus opciones (ni como respuesta ni como distractor): el generador lanza `GenerationError`. **El ejemplo de §6.5 («hola → hola») deja de ser válido**; el contenido del Grupo 2 debe usar respuestas distintas (p. ej. «hola → buenos días»), a revisar con el intérprete.
  3. El generador convierte el contenido mal escrito en `GenerationError` con mensaje en español: turnos con opciones repetidas, palabras de deletreo en minúsculas, menos de 2 palabras de deletreo, nodos con muy pocas señas para 3 lecciones.
- Consecuencias: pruebas nuevas que simulan el ataque (semilla pública) y verifican que ya no acierta, que las columnas de MEMORY_MATCH no revelan las parejas y que ningún estímulo aparece entre sus opciones. Las pruebas de «barajado con rng» se reemplazaron por las de orden por token.
- Secciones afectadas: §6.5, §7.6.

## D-009 · Detalles del pipeline de contenido (Grupo 2) · 31/10/2026
- Contexto / problema: puntos que §5–§6 no fijan o que aparecieron al implementar.
- Decisiones:
  1. **YAML sin booleanos implícitos:** en YAML 1.1 la seña `no` (sin comillas) se lee como `False`. `conversations.yaml` se lee con un `SafeLoader` que no resuelve booleanos; el equipo puede escribir `no` y `si` sin comillas.
  2. **Manifiesto:** campo opcional `label` (palabra dibujada) en las entradas de relleno, para no regenerar los 109 rellenos en cada ejecución; `source_hash` (SHA-256 de los originales) en las entradas reales sirve de caché. `content/videos/.cache.json` es una copia local ignorada en git.
  3. **Rellenos** con una sola imagen en bucle (`ffmpeg -loop 1`), fuente Nunito (OFL) incluida en `content/fonts/` (copiada de `@fontsource-variable/nunito`, se carga como woff2 con Pillow).
  4. **`lesson_sessions.lesson_id` sin CASCADE** y el seed **nunca borra lecciones**: solo borra ejercicios que el generador ya no produce (sus respuestas caen por CASCADE, §5). Así recargar el contenido nunca borra progreso (R9.7).
  5. **Categorías** definidas en código (`app/content/loader.py`, orden de §6.2), no en `curriculum.json`.
  6. **Logros:** descripción e ícono (lucide-react) definidos en `app/content/seed.py`.
  7. **Mensajes no dados por §6.6** redactados por analogía (máximos de señas por nodo, deletreo: ««SAL» usa la letra S, que aún no se ha enseñado en M1-N3-L4.»).
  8. **`labels.json`** se busca por defecto en `public/models/lsc-alfabeto/labels.json` (al lado de `public/media`).
- Consecuencias: las conversaciones de `content/conversations.yaml` son una propuesta marcada `# revisar` y no responden una seña con ella misma (D-008).
- Ajustes tras la revisión del Grupo 2 (D-009, continuación):
  9. **Administrador:** el seed nunca asciende una cuenta existente (si `ADMIN_EMAIL` pertenece a un estudiante, falla con un mensaje claro); si ya es ADMIN, la contraseña del `.env` reemplaza la anterior. `ADMIN_EMAIL` y `ADMIN_PASSWORD` van juntos y la contraseña debe tener 8–72 bytes UTF-8.
  10. **Manifiesto:** `video`/`poster` deben cumplir `^/media/v/<16 hex>.mp4$` y `^/media/p/<16 hex>.jpg$` (sin rutas fuera de `media/`). Si `manifest.json` no existía al empezar, no se borran «huérfanos» (podrían ser videos aún sin commit).
  11. **Reordenar módulos o nodos** no rompe el seed: los `order` existentes se mueven a negativos antes del upsert.

## D-010 · Detalles de la autenticación (Grupo 3) · 31/10/2026
- Decisiones:
  1. **Límites de peticiones con `limits`** (la librería sobre la que está construido slowapi), llamados desde el router y desde `current_user`: el límite de login necesita el correo del cuerpo, que el decorador de slowapi no ve. Almacenamiento en memoria (un solo proceso en Render); `reset_rate_limits()` para las pruebas.
  2. **Correo validado con una expresión simple** (`x@y.z`) en vez de `email-validator`, para no agregar dependencias (§0.1 regla 5).
  3. **Errores de validación personalizados:** los `ValueError` de los validadores propios (contraseña de 8–72 bytes, política de datos, correo) llegan tal cual a `fields`.
  4. **Tipos generados** con `openapi-typescript --default-non-nullable=false`: los campos con valor por defecto (p. ej. `introCompleted`) son opcionales al enviar.
  5. **`refreshSession` single-flight** sirve también para el arranque: el doble montaje de StrictMode comparte la petición (sin estado global aparte).
  6. **429 en el login** siempre muestra «Demasiados intentos, espera un minuto» (R2.5), aunque el servidor envíe otro texto.
  7. **`/`** lleva a `/aprender` con sesión y a `/ingresar` sin ella hasta que exista `/bienvenida` (Grupo 9). `/aprender` es provisional hasta el Grupo 4.
- Ajustes tras la revisión del Grupo 3 (D-010, continuación):
  8. **Login sin truncar:** una contraseña de más de 72 bytes se compara contra el hash ficticio y se rechaza (antes «contraseña + cualquier cosa» abría la cuenta).
  9. **La renovación solo cierra la sesión ante 401/403;** un 5xx o un corte de red no sacan al usuario de una lección (al arrancar, sí pasa a anónimo). Un 401 tardío con el token ya renovado reintenta sin volver a rotar.
  10. **`volver`** solo acepta rutas del mismo origen (sin `\`, caracteres de control ni las pantallas de ingreso). Un refresh fallido borra la cookie `rt`. La caché de TanStack Query se vacía al perder la sesión.
  11. **Pendientes conscientes:** dos pestañas que recargan a la vez pueden rotar el token al mismo tiempo y la segunda quedar en `/ingresar` (el `FOR UPDATE` evita tokens dobles; coordinar pestañas o dar un margen de gracia queda como mejora). No se revoca toda la familia de tokens al detectar reutilización (§11 no lo exige). **Grupo 11:** arrancar uvicorn con `--proxy-headers --forwarded-allow-ips=<IP del proxy de Render>` (nunca `*`) para que los límites usen la IP real.

## D-011 · Detalles de la ruta de aprendizaje (Grupo 4) · 31/10/2026
- Decisiones:
  1. **Estados en la API con los enums del dominio** (`ProgressStatus`, `NodeKind`, `LessonType`); cada nivel usa el subconjunto de §7.4.
  2. **`estimatedXp`** = XP de aprobar con 100 % según `RewardPolicy` (20 en L1–L3, 30 en el reto; la mitad si ya la aprobó).
  3. **`progress`** del módulo = round_half_up(aprobadas·100, lecciones del módulo); 0 en módulos no publicados, cuyos nodos llegan con `COMING_SOON` y sin lecciones.
  4. **Movimiento reducido** con un hook propio (`lib/motion.ts`) que lee `matchMedia` y escucha cambios: el de Framer Motion guarda el valor una sola vez.
  5. **Panel derecho** oculto por debajo de 1280 px (§9.7); aviso «solo computador» por debajo de 1024 px para toda la app.
  6. **Barra superior provisional** (nombre y «Cerrar sesión»); racha, XP, néctar y vidas llegan en el Grupo 6.
- Ajustes tras la revisión del Grupo 4 (D-011, continuación; reemplaza D-011.5):
  7. **Reglas al dominio:** `module_progress_percent` (`domain/policies/progress.py`) y `RewardPolicy.max_xp` (XP estimada); el servicio solo las llama (ProgressService del Grupo 7 reutilizará la primera).
  8. **Aviso de pantalla pequeña como capa:** la app queda montada y oculta (`hidden` + `inert`) para no perder estado ni repetir el refresh al cambiar el tamaño; `/diccionario` no se bloquea (§9.7).
  9. **Accesibilidad:** verde de «completado» y «Empezar» con `#047857` (contraste AA con blanco); el popover recibe el foco una sola vez, lo devuelve al botón al cerrar, `aria-expanded`/`aria-controls`, y hay un solo popover abierto en toda la ruta.
  10. **Pendiente (Grupo 6):** entre 1024 y 1279 px el panel derecho queda oculto; cuando tenga racha y vidas, mostrarlo tras un botón (§9.7).
  11. **Riesgo de pruebas:** las pruebas de API comparten `alas_test`; si dos procesos de pytest corren a la vez (p. ej. un revisor y `alas check`), los que truncan contenido pueden hacer fallar a los otros. No correr dos suites de API en paralelo.

## D-012 · Detalles de la sesión de lección (Grupo 5) · 01/11/2026
- Decisiones:
  1. **Dos columnas nuevas en `lesson_sessions`** (migración `f25914da6c54`): `exercises_hash` (huella de los ejercicios al empezar; si el contenido se recarga distinto, la sesión responde 410, §8.3.8) y `result` (JSONB con el `LessonCompletionResult`; el `complete` repetido devuelve exactamente lo mismo, R4.10).
  2. **`group`** en cada ejercicio público = índice de su seña (agrupación de §9.3) en L1–L3; `null` en los finales y en todo el reto. No revela la respuesta (el número no dice qué seña es).
  3. **`correctTokens`** además de `correctToken`: la conversación tiene un token correcto por turno.
  4. **Racha y logros provisionales en `complete`** (`streak {0, false}`, `newAchievements []`): los aplica `GamificationService.apply_completion` en el Grupo 6. XP y néctar sí se suman ya al usuario.
  5. **JWT sin `verify_iat`:** PyJWT comparaba `iat` con la hora real; ahora exp/iat se validan solo con el Clock (D22, B77).
  6. **`/media` en FastAPI** sirve solo `v/` y `p/` con `Cache-Control: immutable` y `Range` (206); **`manifest.json` no se publica** (relaciona slug y video, B54). En desarrollo Vite sí lo sirve desde `public/`: el riesgo queda solo en local.
  7. **Interfaz:** las 4 actividades siempre visibles; estado relativo al ejercicio actual (activa · ✔ Completada · 🔒 Pendiente). Video principal de 220–260 px y opciones en 2 columnas para que a 1366×768 se vean video, pregunta, opciones y «Comprobar respuesta» (medido con Playwright). `autoPlay` del reproductor apagado por defecto y activado en la lección.
  8. **Correcciones de la revisión (verificador NO APROBADO + revisor):** `answer` bloquea primero la sesión y luego al usuario (mismo orden que `complete`, sin interbloqueos), y `lock_user`/`get_user_session(for_update)` usan `populate_existing` (dos errores simultáneos descuentan dos vidas). Límites de tamaño en las respuestas (tokens ≤ 32, intentos de memoria ≤ 36, elecciones ≤ 6 → 422). Sesión completada sin `result` → 409 `SESSION_COMPLETED`. `VideoRef` lleva `placeholder` y `source` (R9.13 en lecciones). Los bloques por seña son contiguos: el bloque final de L1 (señas que reaparecen) no tiene `group`. Los reproductores compactos se reproducen solos y en bucle; Enter tras elegir con el mouse comprueba; «Continuar» recibe el foco; un corte de red avisa sin tumbar la lección.
  9. **Límite conocido aceptado:** cruzando el `src` de los videos entre ejercicios del JSON de inicio se puede deducir la respuesta (Observa muestra la seña justo antes del quiz y el diccionario público relaciona palabra y video). Es inherente al diseño (§7.6 «límite conocido»); no se envía `correctId` ni `signId`.
  10. **Pendientes menores:** memoria y conversación no marcan la correcta tras comprobar (R4.5); sin flechas en los radiogroup; un par de memoria no se deshace; el último turno de conversación no se cambia. El modal NO_HEARTS y el latido van en 6.5; la cabecera de proxy en producción en el Grupo 11.

## D-013 · Detalles de la gamificación (Grupo 6) · 01/11/2026
- Decisiones:
  1. **Seña «bien» para el repaso:** al completar una lección, una seña queda correcta solo si TODAS sus respuestas de la sesión fueron correctas (incluye Observa, Produce y el bloque final). Un error o «Necesito repasar» la deja en fuerza 0 y repaso mañana (§7.7, R6.4). Una lección reprobada también programa sus señas.
  2. **`extended`** en la racha = primera actividad del día local (la racha cambió de día), aunque se haya reiniciado a 1.
  3. **Estadísticas de logros:** `lessons_passed` = sesiones aprobadas; `challenges_passed`/`golden_challenges` = retos aprobados / con 100 %; `module1_completed` = todas las lecciones del primer módulo (por `order`) aprobadas; `distinct_signs_correct` = señas distintas con una respuesta correcta en un ejercicio con puntaje; `camera_correct` = `users.recognitions_correct`. FIRST_FLAP queda para `grant_intro` (tarea 9.2).
  4. **`newAchievements[].nectar`** (campo nuevo): la celebración muestra el néctar de cada logro. `nectarEarned` sigue siendo solo el de la lección; el néctar de los logros se suma al usuario solo por filas insertadas (`RETURNING`).
  5. **Compras:** `streak-freeze` comprueba `MAX_FREEZES` antes que el néctar; `hearts-refill` comprueba `HEARTS_FULL` (también con `HEARTS_ENABLED=false`) antes que el néctar. Ambas bloquean al usuario (`FOR UPDATE`) y devuelven el mismo cuerpo que `GET /gamification/stats`.
  6. **`ApiError.nextHeartAt`:** el cliente conserva el `nextHeartAt` del 403 `NO_HEARTS` para la cuenta regresiva del modal «Sin vidas». La cuenta regresiva redondea hacia arriba.
  7. **Interfaz:** la celebración es un diálogo modal (foco en «Volver a la ruta», Escape cierra, confeti solo si aprobó y sin movimiento reducido). Panel derecho y barra superior leen `GET /gamification/stats`; tras completar se invalidan estadísticas y logros. Textos de néctar como «+N de néctar». En pruebas, `canvas-confetti` se simula globalmente (jsdom no tiene canvas).
  8. **Revisión (revisor-codigo, sin bloqueantes):** un protector comprado cuando la racha ya se rompió no la revive: la compra deja la racha en 0 sin último día (la siguiente actividad empieza en 1 y conserva los protectores). Pruebas nuevas de compras simultáneas (protector y vidas cobran una vez) y de dos lecciones distintas completadas a la vez. «¡Empezaste una racha!» en vez de «¡Racha extendida!» cuando la racha queda en 1. El foco inicial del modal «Sin vidas» va a «Volver a la ruta» hasta que exista `/repaso` (Grupo 7). Pendientes menores: costos y máximos repetidos en la interfaz (exponerlos en `StatsOut`), `nextHeartAt` del 403 no declarado en OpenAPI, contadores que no refrescan al llegar a 0, atrapar el foco en los modales, `aria-label` en `span`.

## D-014 · Detalles del progreso y el repaso (Grupo 7) · 01/11/2026
- Decisiones:
  1. **`review_sessions.result`** (migración `7b2e9d41a0c3`): JSONB con el `ReviewCompletionOut`; el `complete` repetido devuelve exactamente lo mismo, igual que en lecciones.
  2. **Inicio del repaso:** bloquea la fila del usuario antes de buscar la sesión abierta de hoy; dos inicios simultáneos (StrictMode, doble clic) crean una sola sesión. Una sesión abierta de un día anterior no se reutiliza.
  3. **Señas vistas** (para distractores) = señas con fila en `sign_reviews`; si no alcanzan 2 opciones, se completa con el resto del contenido (`build_review_items`).
  4. **Porcentajes de `/progress/summary`** con `round_half_up`, igual que la ruta; `averageScore`, `accuracy` y el `score` del repaso con división entera hacia abajo.
  5. **Duración del repaso** para la meta diaria: tiempo desde el inicio, con el mismo tope de 15 min que las lecciones.
  6. **`AnswerResult` del cliente** = solo los campos de corrección (`Pick` del tipo generado); la lección usa `LessonAnswerResult` (con vidas) y el repaso `ReviewAnswerOut`. `/repaso` reutiliza `SelectMeaningActivity`.
  7. **Recharts 3.10.1** (exacta; ya estaba en §3 pero faltaba instalarla): barras de avance por módulo con una lista oculta para lectores de pantalla.
  8. **Revisión (revisor-codigo, sin bloqueantes):** al empezar un repaso, una sesión abierta de un día anterior queda cerrada sin resultado (su `complete` responde 409 `SESSION_COMPLETED`): las mismas señas no se reprograman ni dan vida dos veces (R6.8). La precisión por unidad cuenta solo respuestas de sesiones completadas, igual que el promedio. Mensajes de error propios del repaso. La gráfica de `/progreso` se adapta al ancho y es decorativa (`aria-hidden`; la lista oculta da los datos); «aprobada» con texto para lectores de pantalla.
  9. **Pendientes menores:** reutilizar la sesión responde 201 (las pruebas aceptan 200/201); `ReviewPage` no distingue 410/409 al responder y no mueve el foco al terminar; `LessonPage` no invalida la cola de repaso ni el progreso (hoy no se nota porque se vuelven a pedir al montar).

## D-015 · Detalles del diccionario (Grupo 8) · 01/11/2026
- Decisiones:
  1. **Búsqueda:** `normalize_text(q)` contenido en `normalized_word` con `ILIKE` y `\` como escape (`%`, `_` y `\` literales); `q` máx. 80 caracteres; 24 por página, orden `normalized_word`, slug. Sugerencias solo sin resultados: Levenshtein ≤ 2 sobre las palabras normalizadas (respetando el filtro de categoría), la más cercana primero, máx. 5. Son ~110 señas: se calcula en memoria.
  2. **Autenticación opcional** (`OptionalUser`): sin cabecera, anónimo; un token inválido sigue siendo 401 (el cliente renueva). En la interfaz, estadísticas, cola de repaso y favoritos solo se piden con sesión; el panel invita a crear cuenta.
  3. **Ficha:** `relatedLesson` solo si el módulo está publicado; `status` null sin sesión (el enlace lleva a la lección y, sin sesión, al ingreso). Bloqueada → «(bloqueada por ahora)» sin enlace. «Práctica rápida» = autoevaluación sin puntaje ni llamadas al servidor.
  4. **Favoritos:** `created_at` lo fija el Clock (D22); POST idempotente con `ON CONFLICT DO NOTHING`, DELETE idempotente; orden más recientes primero.
  5. **Búsqueda en la URL** (`?q=&categoria=&pagina=`) con espera de 300 ms al escribir.
  6. **Revisión (verificador APROBADO; revisor con 1 bloqueante corregido):** el favorito usa ⭐ (`Star`, ámbar) y no ❤, que en la barra son las vidas (especificación, nota inicial). El botón usa `aria-disabled` (el foco no salta al guardar) y su texto cambia sin `aria-pressed` contradictorio. Quitar favorito con un solo `DELETE`. La práctica rápida solo menciona 0,5x si la seña es video. Pruebas nuevas: token inválido en la ficha → 401; el visitante no pide la cola de repaso.
  7. **Pendientes menores:** `?q=%` sugiere letras sueltas (distancia 1); `?pagina=` fuera de rango muestra la lista vacía; `q` de más de 80 caracteres pegado en la URL da error genérico; la clave de caché de la ficha no incluye la sesión (se limpia al cerrar sesión).

## D-016 · Detalles del módulo introductorio (Grupo 9) · 01/11/2026
- Decisiones:
  1. **`GET /api/intro`** se arma en cada petición desde `content/intro.json` y la BD (palabra y `VideoRef` de cada seña). Cada pregunta del quiz: la correcta y 2 distractores = las tarjetas siguientes a la seña (en ciclo, sin azar), ordenadas por palabra; incluye `correct` porque el intro no da XP (§8.2).
  2. **Marca del intro** en `localStorage` (`alas.introCompleted`; no es un token ni un dato sensible), con `try/catch`. `/` sin sesión → `/bienvenida` la primera vez y `/ingresar` después; `/bienvenida` es solo para visitantes (con sesión → `/aprender`).
  3. **«Primer aleteo»:** `GamificationService.grant_intro` en el registro con `introCompleted: true` (inserción `ON CONFLICT DO NOTHING RETURNING`, +10 néctar solo si se insertó). `unauthorized()` pasa a `core/errors.py` para que `auth_service` pueda usar `gamification_service` sin ciclo de importación.
  4. **Mensajes de Tomi** del intro en el cliente (uno por tarjeta, siempre de ánimo). Las tarjetas usan el reproductor compacto (bucle, sin controles, §6.3).
  5. **Pruebas de interfaz ajustadas:** `/` sin sesión ahora va a `/bienvenida` si no completó el intro (R1.1), y el registro envía `introCompleted`.
  6. **Revisión (verificador APROBADO; revisor sin bloqueantes):** foco al título en cada tarjeta y pregunta; región `role="status"` siempre montada; la marca se guarda al responder la última pregunta (R1.4), no al pulsar «Crear mi cuenta». `slug` en tarjetas y preguntas (fuera del contrato de §8.2) se conserva como clave estable: no revela nada que el intro no incluya ya (`correct`). La marca la decide el cliente: en un mismo navegador cada cuenta nueva recibe «Primer aleteo» (recompensa simbólica, aceptado).
  7. **Pendientes menores:** el reproductor compacto ignora `maxHeight` (tarjeta de 128 px de alto; revisar contra el mockup); `catalog[slug]` da 500 si la BD no tiene una seña del intro (la validación del contenido lo previene); falta prueba de interfaz del registro con `introCompleted: true`.
  8. **Logros sin catálogo:** `insert_achievements` solo inserta logros que existen en la tabla `achievements`; con la BD sin sembrar, el registro con `introCompleted` no da 500 por la FK (lo encontró una prueba de `test_auth.py` que dependía del orden).

## D-017 · Detalles de la cámara (Grupo 10) · 01/11/2026
- Decisiones:
  1. **`@mediapipe/tasks-vision` 1.1.0 exacta** (dependencia de §3): la 1.2.0 tenía 5 días de publicada; se fija la anterior estable. Una prueba comprueba que `TASKS_VISION_VERSION` (que va en cada `dataset.json`) coincide con `package.json`.
  2. **`apps/web/public/mediapipe/` en `.gitignore`:** ~30 MB de WASM y el modelo `.task` los genera `uv run alas camera-assets` (también lo hará la imagen de producción, Grupo 11).
  3. **Singleton de HandLandmarker con conteo de usuarios:** StrictMode monta dos veces; la instancia se cierra cuando la suelta el último usuario. El modelo propio se carga en diferido (`import()` de tfjs) y, si no existe o sus salidas no coinciden con `labels.json`, se usa `MockClassifier` (R8.6).
  4. **Suavizado:** mayoría de los últimos 10 resultados; se muestra con la confianza media de esa etiqueta si es ≥ 0,70 y no es «NINGUNA».
  5. **«Una vez por seña cada 10 s»** del logro se lleva en memoria del proceso con el Clock (la app corre en un solo proceso; tras un reinicio, como mucho cuenta una vez más esa seña). El límite de 60/min usa `limits` como el resto.
  6. **TensorFlow no instala en Windows** (`tensorflow-io-gcs-filesystem` 0.37.1 no tiene wheel para win_amd64) y las versiones de `ml/pyproject.toml` no se cambian: se entrena en Google Colab con `ml/notebooks/entrenamiento.ipynb`, que usa `uv run --project ml` con el mismo `pyproject.toml` (el harness no permite instalar con pip, y así las versiones son idénticas). La carga y validación de datos de `train_static.py` no importa TensorFlow y tiene 14 pruebas (`uv run --no-project --with pytest pytest ml/tests`).
  7. **`/camara` reporta** cada seña detectada a `POST /recognition/results` como correcta (no hay seña objetivo); `ProduceActivity` reportará si coincide con la seña pedida.
  8. **Revisión (revisor-codigo: 1 bloqueante y 6 importantes, corregidos):** las páginas `/camara` y `/admin/dataset` apagan la cámara si se sale mientras se enciende (prueba nueva; B40, R8.5). El suavizado exige 6 votos de la misma etiqueta (un cuadro aislado no basta, B37) con tolerancia de redondeo en el umbral. La regla «cuenta para Ojo de colibrí» pasa al dominio (`domain/policies/recognition.py`, con pruebas). Si falla la carga se suelta el HandLandmarker y el modelo; un cuadro fallido no detiene el bucle. Solo la letra detectada se anuncia (la confianza no) y no se re-renderiza en cada cuadro sin cambios. `CameraCheck` guarda `onRecognized` en un ref. El colector pide las 2 páginas del alfabeto (27 letras), bloquea la etiqueta al grabar, termina a tiempo aunque salga la mano y tiene «Apagar cámara». `train_static.py` descarta (con aviso) las muestras de letras con movimiento en lugar de rechazar el archivo, rechaza booleanos y explica JSON mal formados.
  9. **Pendientes menores:** rutas de cámara sin `lazy()` (MediaPipe y tfjs sí se cargan en diferido); el cuaderno no sube `ml/uv.lock` (no se pudo generar en Windows); `enable_op_determinism` no activado en Colab.

## D-018 · Videos de LSC-54 para 22 señas · 01/11/2026
- Contexto: el usuario pidió buscar datasets con videos para los módulos y eligió **LSC-54** (Universidad de La Sabana; Mora-Zarate, Garzón-Castro y Castellanos-Rivillas, 2025, *Data in Brief* 63, 112145; datos DOI 10.57760/sciencedb.25639; licencia **CC BY-NC 4.0**: uso académico no comercial con atribución).
- Decisiones:
  1. Se usan los videos de **cortesía y números** (los colores no están en el contenido). Coinciden 22 señas: hola, buenos-dias, buenas-tardes, buenas-noches, como-estas, adios (seña «Chao» de LSC-54), gracias, por-favor, de-nada, si, no, perdon y numero-1 a numero-10.
  2. **Una sola persona** (la 1: fondo blanco, mismo encuadre, las 22 señas) y la toma 0 de cada seña, para que la app se vea coherente. Los `.avi` (XviD, 640×360) se convierten a `.mp4` y se dejan en `content/videos/raw/<slug>.mp4` (fuera de git); `alas content all` los normaliza como cualquier video propio.
  3. **Créditos visibles** en `/creditos` (pública, enlazada desde la barra lateral), con cita, DOI, licencia y los cambios hechos (exigido por CC BY).
- **Pendiente con el intérprete** (`docs/validacion-interprete.md`): los rostros vienen pixelados en el original (la expresión facial no se ve) y hay que confirmar que «Chao» sirve para «Adiós». Si alguna no sirve, se reemplaza por un video propio y se quita de `/creditos`.

## D-019 · Modelo de la cámara para los números 1–5 con LSC-54 · 01/11/2026
- Contexto: LSC-54 no trae alfabeto; el usuario pidió entrenar con LSC-54 en Colab y decidir lo mejor.
- Decisiones:
  1. **Números 1–5 `static`, 6–10 `dynamic`** en `signs.csv` (provisional: **pendiente de confirmar por el intérprete**). La validación acepta `motion` en los números (opcional) y el generador da `camera_label` a toda seña estática (letras y números): «Produce la seña» puede usar la cámara con los números 1–5.
  2. **Datos desde videos con el mismo pipeline del navegador (D11):** el colector `/admin/dataset` tiene «Desde videos» (`src/camera/video-extract.ts`): recorre cada video local cada 0,1 s con HandLandmarker (CPU) + `normalizeLandmarks`; etiqueta y persona salen del nombre `etiqueta__persona__toma.mp4`. Los videos no se suben. `dataset.json` admite `collector` por muestra (varias personas en un archivo) y `train_static.py` lo usa para separar por persona.
  3. **NINGUNA** = 6 señas de cortesía de LSC-54 que no son números (Hola, Gracias, Por favor, Bien, Esperar, Permiso), toma 0 de cada persona.
  4. **Resultado:** `ml/data/dataset-lsc54-numeros.json` (fuera de git): 3.908 muestras de 18 personas — NINGUNA 1.004 y 565–599 por número (cumple ≥ 300 por clase, ≥ 600 de NINGUNA y ≥ 3 personas).
  5. **Entrenamiento en Google Colab** con `ml/notebooks/entrenamiento.ipynb` (uv con `ml/pyproject.toml`; se instala uv si falta). El `venv/` local del equipo (TF 2.15.0 sin `tensorflowjs`, que no instala en Windows) no se usa para exportar.
  6. **Parte central de cada clip** (25 %–85 % de la duración) para las señas en «Desde videos»; «NINGUNA» usa el clip completo. Los cuadros de subir y bajar la mano confundían al modelo. Validación con 4 personas no vistas (TensorFlow local, misma arquitectura y semillas): 75,8 % → **82,1 %** (NINGUNA 96 %, números 68–84 %). El primer modelo de Colab (sin recorte) se descarta. En la app el suavizado (6 de 10 votos, ≥ 0,70) filtra errores aislados.
  7. **Modelo publicado** (`apps/web/public/models/lsc-alfabeto/`, entrenado en Colab con el dataset recortado: NINGUNA + numero-1…5, 18 personas). En TensorFlow.js sobre todo el dataset: NINGUNA 95 %, números 63–72 %. Prueba de punta a punta con una «cámara falsa» de Chrome que reproduce videos de una persona no usada en la validación local: `/camara` reconoce el número correcto en 4 de 5 (el 1 a veces sale como 5).
  8. **MediaPipe en CPU también en la cámara en vivo:** con GPU, en un navegador sin aceleración (como los de laboratorio o automatizados) HandLandmarker no detectaba manos y no daba error; una mano a 30 fps cabe en CPU. Los números se muestran como dígitos («numero-3» → «3»).
  9. **Pendiente:** el intérprete confirma que los números 1–5 son estáticos; para mejorar el modelo, grabar con la cámara del equipo (más variedad de personas y fondos) y volver a entrenar.

## D-021 · Primero observar, después recordar (lecciones L1 a L3) · 01/11/2026
- Contexto: el usuario notó que en «Aprende» se mostraba una seña (video + palabra) e inmediatamente se preguntaba por ella, así que la pregunta no hacía recordar nada. Lo mismo pasaba en L2 y L3. Aprobó la opción «primero ver todas, después preguntar mezclado».
- Decisión (cambia la agrupación por seña de §9.3):
  - **L1 Aprende:** observar todas las señas nuevas → «¿Qué significa?» en orden mezclado → producir cada una → «¿Cuál es la seña de…?» mezcladas.
  - **L2 Reconoce:** observar todas (repaso) → las dos preguntas mezcladas → actividad final.
  - **L3 Practica:** observar todas → preguntas mezcladas → producir → memoria → actividad final.
  - El orden mezclado sale del rng de la lección (reproducible) y la primera pregunta nunca es la última seña mostrada. L4 (reto) no cambia.
  - `group` solo marca las observaciones («Seña 1 de 3»…); las preguntas no pertenecen a una seña y van sin grupo.
- Pruebas: estructura nueva de L1–L3, «la primera pregunta nunca es la última seña mostrada» y «las preguntas no siguen el orden observado» (generador); grupos nuevos en las pruebas de API.
- Mejora futura (opción 2): mostrar en las preguntas la seña hecha por otra persona cuando haya varios videos por seña.

## D-022 · Página de perfil y derechos sobre los datos (Ley 1581 de 2012) · 02/11/2026
- Contexto: `/perfil` estaba en el menú y en las rutas de diseño, pero ninguna tarea la construía. El usuario aprobó las secciones 1, 2 y 4.
- Decisiones:
  1. **Tus datos:** nombre, meta diaria (5/10/15/20) y mano dominante con el `PATCH /me` existente; la sesión local se actualiza con el usuario devuelto.
  2. **Tu resumen:** XP, racha actual y más larga, néctar, señas aprendidas y logros, con los endpoints existentes (sin API nueva).
  3. **Privacidad y cuenta:** enlace a la política, «Descargar mis datos» (`GET /me/export`, JSON con perfil, racha, sesiones, actividad, logros, favoritos y repasos; nunca la contraseña ni tokens) y «Eliminar mi cuenta» (`DELETE /me` con la contraseña; borra al usuario y todo lo suyo por `ON DELETE CASCADE`, borra la cookie). Para evitar fuerza bruta usa el mismo límite que el ingreso; en la interfaz exige escribir «ELIMINAR».
  4. **`/privacidad`** (pública): la enlazaba el registro pero no existía; explica qué se guarda, qué no (la cámara) y los derechos.
- Funciones nuevas fuera de §8.2 (endpoints de exportación y supresión): justificadas por los derechos de acceso y supresión de la Ley 1581 (§11 de la especificación).

## D-023 · Foto de perfil · 02/11/2026
- Contexto: el usuario pidió poder tener foto de perfil y cambiarla con una imagen de sus archivos.
- Decisiones:
  1. **En el navegador** se recorta al centro y se reduce a 256 × 256 (WebP) antes de enviarla; se aceptan JPG, PNG y WebP de hasta 15 MB de origen.
  2. **En el servidor** (`PUT /me/avatar`, JSON con la imagen en base64: no se agrega `python-multipart`) se valida que sea JPG/PNG/WebP real con Pillow, ≤ 300 KB y ≤ 4096 px por lado, y se **re-codifica** como WebP 256 × 256: así se descartan los metadatos (EXIF, ubicación GPS) y lo guardado es siempre una imagen válida.
  3. **Se guarda en `users.avatar`** (`LargeBinary`, diferida) con `avatar_updated_at` (migración `3c8e1f5a9d27`). `GET /me/avatar` solo para el dueño, con `Cache-Control: private, no-store`; el cliente la pide con el token y la muestra como `blob:` (permitido por la CSP). `DELETE /me/avatar` la quita.
  4. **`UserOut.avatarUpdatedAt`** (null = sin foto) sirve para saber si hay foto y para refrescarla. La exportación de datos indica `hasAvatar`; al eliminar la cuenta se borra con el usuario.
  5. **Dónde se ve:** perfil (subir, cambiar, quitar) y barra superior junto al nombre (enlace a `/perfil`); sin foto se muestra Tomi.

## D-024 · Modelo de la cámara con el alfabeto (LSC70) · 02/11/2026
- Contexto: el usuario pidió que la cámara reconozca el abecedario y que se busquen datasets libres; eligió LSC70 (Universidad del Cauca, Mendeley Data, DOI 10.17632/9ssyn8tff5.2, **CC BY 4.0**: 70 personas, fotos del alfabeto y números validadas por expertos).
- Decisiones:
  1. **Datos:** fotos de cuerpo completo (LSC70AN) de las 24 letras estáticas de `signs.csv` y los números 1, 4, 5, procesadas en el navegador con el colector («Desde videos» acepta fotos, MediaPipe en modo IMAGE, misma normalización, D11) + los videos de LSC-54 (números 1–5 y NINGUNA). 14.782 muestras de 88 personas. J, Ñ y Z (movimiento) siguen con autoevaluación.
  2. **Elegir la mano que hace la seña** (`pickSigningHand`): MediaPipe busca 2 manos y se usa la más alta. Con 1 mano tomaba a veces la que cuelga en reposo, que parece la «Q» (todo se confundía con Q). Aplicado igual en la extracción y en la cámara en vivo. Validación cruzada por persona de las letras: 64,7 % → 86,6 %.
  3. **Entrenamiento local** con TensorFlow 2.15 del `venv` del equipo y **exportador propio** a TensorFlow.js en `train_static.py` (si `tensorflowjs` no está, escribe `model.json` + `group1-shard1of1.bin`); sin scikit-learn, la separación por persona y la matriz de confusión usan numpy. La salida en TensorFlow.js coincide con Keras (diferencia máx. 3e-7). Colab sigue sirviendo.
  4. **Resultado publicado** (30 clases): validación cruzada por persona 82,7 % por cuadro (letras 75–96 %, salvo H 60 % y S 58 %; números de LSC-54 57–84 %). Con la cámara falsa: A, L, Y, O reconocidas de forma estable; B se confunde con 4 (formas casi iguales) y los números de LSC-54 no alcanzan el umbral. En uso real mejora con el suavizado (6 de 10, ≥ 0,70).
  5. **Créditos** de LSC70 y LSC-54 en `/creditos` (CC BY 4.0 exige atribución). No se publican las fotos ni los videos, solo el modelo.
- Pendiente: grabar al equipo con su cámara para mejorar H, S, B/4 y los números; el intérprete confirma las letras y números estáticos.

## D-025 · Cámara holística (Grupo 10B): recorte, importador y delegados · 02/11/2026
- Contexto: anexo A (cámara holística). Los videos de LSC-54 duran 1–5 s y la cámara graba 2 s; las caras de LSC-54 vienen pixeladas.
- Decisiones:
  1. **Recorte al tramo con mano** (`FrameSequencer.toFrames({ trim: true })`): antes de remuestrear a 30 cuadros se toma del primer al último cuadro con mano dominante. Se aplica igual en la cámara y en el importador, para que la misma seña tenga la misma forma temporal (complementa H3).
  2. **Importador por búsqueda de cuadros**: los videos se recorren cada 1/15 s con `currentTime`/`seeked` en vez de `requestVideoFrameCallback` (A.7.1). Es determinista y funciona en navegadores automatizados; el instante del video es el timestamp. Siempre con CPU (D-019).
  3. **Delegado**: en vivo, GPU → CPU al crear (A.2.1) y, además, `SilentGpuGuard`: 60 cuadros seguidos sin detectar nada con GPU cambian el detector a CPU (la GPU falla sin error en algunos equipos, D-019).
  4. **Sin rostro** (`faceFeatures: false` en el dataset y en `meta.json`): todo lo que depende de la cara — mano–cara (6), blendshapes (18) y presencia de cara — va en 0 al entrenar y al reconocer (`maskFace`/`mask_face`, en los fixtures de paridad). En LSC-54 la cara pixelada casi nunca se detecta: si solo se anularan los blendshapes, el modelo vería mano–cara en 0 al entrenar y con valores en vivo. El control de calidad no exige cara al importar datasets pixelados.
  5. **La calidad se mide en el tramo recortado** (`quality({ trim: true })`): en los clips de LSC-54 las manos suben y bajan, y medida sobre el clip entero la mano dominante aparecía en 31–62 % de los cuadros (se habría descartado casi todo). Se mide sobre los mismos cuadros que se guardan.
  6. **«NINGUNA» no exige mano** en el control de calidad (las manos pueden estar abajo). En `content/dataset-mapping.csv` el slug `NINGUNA` marca señas externas usadas como ejemplos negativos (Bien, Mal, Ayudar de LSC-54).
  7. **`content/dataset-mapping.csv`** lo valida `alas content check` (cabecera, slugs de `signs.csv`, sin etiquetas repetidas) y el importador lo lee con `?raw` (Vite permite leer `content/`).

## D-026 · `gestureLabel` en PRODUCE para señas con movimiento · 02/11/2026
- Contexto: `cameraLabel` solo existe para señas estáticas (D-019) y A.10 pide que el cliente elija modo gestos, estático o autoevaluación según los `labels.json` publicados.
- Decisión: `ProducePayload`/`PublicProduce` ganan `gesture_label` (= slug si la seña tiene movimiento; si no, null). `camera_label` no cambia. Igual que D-007.8, no filtra la respuesta: PRODUCE ya muestra la palabra y no tiene opciones. El cliente usa la cámara de gestos solo si `/models/lsc-gestos/meta.json` es válido y lista la seña. Requiere volver a sembrar (`alas db seed`) para que las lecciones existentes lo tengan.

## D-027 · Letras y números con la misma forma de mano · 02/11/2026
- Contexto: en LSC algunas letras y números se hacen con la misma forma de mano; el modelo del alfabeto confunde B con 4 (D-024). El usuario preguntó cómo manejarlo.
- Decisión: **el modelo mantiene las clases separadas** (así se pueden distinguir si más adelante hay datos con diferencias sutiles) y **el contexto decide**, con `content/camera-equivalences.csv` (`slug,equivalente,nota`, simétrico):
  1. En una lección (PRODUCE, estático y gestos) se acepta la seña pedida o una equivalente: si piden «B» y la cámara ve «4», cuenta como correcta.
  2. En `/camara` (sin contexto) se muestran las dos: «B / 4».
  3. `alas content check` valida el archivo (slugs de `signs.csv`, sin pares consigo mismos ni repetidos). Agregar un par no exige reentrenar.
- Por ahora solo **B = 4** (evidencia de los datos). **Pendiente con el intérprete:** confirmar ese par y completar la lista.

## D-028 · Mano que firma: la del perfil o, si no sirve, la otra · 02/11/2026
- Contexto: en LSC-54 algunas personas firman con la mano izquierda (p. ej. p21 en «hola»). Con la mano dominante fija («derecha»), esas muestras quedaban con el espacio dominante vacío: el importador descartó 61 de 430 videos («Tu mano salió del cuadro», 20 de los 53 de «hola») y en vivo la cámara no reconocía a quien firma con la otra mano sin haber cambiado su perfil.
- Decisión: el extractor calcula cada cuadro con las dos asignaciones de mano (`alternate`). `chooseSigningHand`: se usa la mano del perfil (A.3.2) si la muestra pasa el control de calidad; si no pasa y con la otra mano sí, se usa la otra (reflejada con `buildHolisticFrame`, igual que para zurdos). Igual en el importador (en los datasets no se sabe quién es zurdo; el `dominantHand` de cada muestra queda registrado) y en vivo. «NINGUNA» siempre usa la mano del perfil.
- También: la GPU de algunos equipos crea `HolisticLandmarker` sin error pero cada detección falla con «UNIMPLEMENTED»; 5 errores seguidos pasan el detector a CPU (amplía `SilentGpuGuard`, D-025). Y con un modelo sin rostro (`faceFeatures: false`) no se exige ver la cara para grabar ni en el control de calidad en vivo.

## D-029 · Alcance aceptado del modelo de gestos y del arranque holístico · 04/11/2026
- Contexto: observaciones de la verificación independiente del Grupo 10B.
- Decisiones:
  1. **Muestras por seña:** A.8 pide ≥ 60 por seña; LSC-54 tiene 18 personas × 3 tomas y, tras el control de calidad, quedaron 45–55 por seña (hola 45, por favor 46, perdón 51, adiós 53, de nada 55; NINGUNA 159). Se acepta para esta versión: los aumentos (velocidad, rotación, escala, ruido, reflejo; 4 copias) multiplican los ejemplos de entrenamiento y la validación cruzada por persona da 89,7 %. Subir a ≥ 60 = grabar al equipo con `/admin/gestos`.
  2. **«hola» por debajo del 80 % (76 %)**: la meta de A.8 es la precisión global (89,7 %). «hola» se confunde con «adiós» (las dos se hacen con la mano abierta a la altura de la cara). Se publica igual: si no se reconoce, el ejercicio sigue ofreciendo la autoevaluación. La validación real con personas fuera de LSC-54 (A.7 regla 2) es la verificación manual del grupo.
  3. **Blendshapes faltantes solo avisan** (no hacen fallar el arranque, A.3.4): el modelo publicado no usa la expresión facial (`faceFeatures: false`, la cara se anula), así que fallar dejaría sin cámara a todos sin ganar nada. El aviso queda en la consola y la prueba de búsqueda por nombre (H4) sigue. Si un modelo futuro usa la cara, el arranque debe fallar: revisar esta decisión.
  4. **Exportación:** el modelo se exportó con el exportador propio (D-020); `published-model.test.ts` comprueba en cada `alas check` que el `meta.json`, `labels.json` y `model.json` publicados son válidos (holistic-v2, GRU `reset_after=false`, una salida por etiqueta). La paridad numérica Keras ↔ TensorFlow.js (diferencia máx. 1,2e-7) se midió al publicar.
  5. **Matriz de confusión** (validación cruzada por persona, 6 pliegues; filas = real, columnas = predicción):

| real \ predicción | NINGUNA | adiós | de nada | hola | perdón | por favor |
|---|---|---|---|---|---|---|
| NINGUNA | 148 | 1 | 1 | 1 | 5 | 3 |
| adiós | 3 | 43 | 1 | 6 | 0 | 0 |
| de nada | 0 | 0 | 53 | 0 | 2 | 0 |
| hola | 1 | 7 | 0 | 34 | 1 | 2 |
| perdón | 2 | 0 | 4 | 0 | 45 | 0 |
| por favor | 2 | 0 | 0 | 0 | 0 | 44 |

  6. **Retroalimentación de Tomi:** con un modelo sin rostro, Tomi solo da indicaciones de altura de la mano («Sube/Baja un poco la mano»); las de cara y cejas vuelven solas cuando se entrene con caras visibles.

## D-030 · Sección «Administración» solo para ADMIN · 04/11/2026
- Contexto: las herramientas de datos de la cámara (`/admin/gestos`, `/admin/importar`, `/admin/dataset`) solo se abrían escribiendo la dirección. El usuario pidió reunirlas en un apartado que solo vea el administrador.
- Decisión: enlace «Administración» al final de la barra lateral, visible solo con rol ADMIN, y página `/admin` con las tres herramientas y su explicación. Cada herramienta tiene «← Administración» para volver. Las páginas siguen comprobando el rol por su cuenta: ocultar el enlace no es la protección.
- La cuenta ADMIN se crea con `ADMIN_EMAIL` y `ADMIN_PASSWORD` del archivo `.env` (en la raíz) al ejecutar `uv run alas db seed`.

## D-031 · «Señas con movimiento» en Cámara beta · 04/11/2026
- Contexto: la especificación solo pide la cámara de gestos dentro de las lecciones (A.10). El usuario pidió poder practicar con las dos manos también en «Cámara beta».
- Decisión: dos pestañas en `/camara`. **«Alfabeto y números»** (por defecto) sigue igual: una mano y reconocimiento continuo. **«Señas con movimiento»** (`GesturePractice`) usa la misma cámara holística y el mismo modelo que las lecciones: lista las señas que conoce el modelo publicado, «Hacer la seña» con cuenta regresiva y 2 s, y muestra la seña reconocida con su confianza; si no es ninguna de esas señas lo dice («NINGUNA»). Cada seña reconocida se reporta como en el alfabeto (solo números, suma para «Ojo de colibrí»). Cambiar de pestaña desmonta el modo anterior y apaga su cámara (R8.5). Sin modelo publicado, la pestaña lo avisa.
- No se reemplazó la cámara del alfabeto por la holística: funcionan distinto (continuo frente a ventana de 2 s), el modelo del alfabeto se entrenó con `hand-v1` y la holística es más pesada.

## D-032 · Las 4 partes del proyecto sin mover carpetas · 04/11/2026
- Contexto: para la sustentación el equipo quiere ver el proyecto como 4 partes (Frontend, API, Backend, Base de datos). Mover las carpetas rompería la CI del kit (`ci.yml` busca `apps/api` y `apps/web` y no se puede reescribir), los hooks de `.claude/`, las rutas de la especificación protegida y los `import` del paquete `app`; el `LEEME-PRIMERO.md` del kit pide no moverlas.
- Decisión: no se mueve nada. `alas-de-senas.code-workspace` muestra en VS Code las 4 partes con nombres numerados (cada parte apunta a sus carpetas reales: Frontend `apps/web`; API `app/api` + `app/schemas`; Backend `app/domain` + `app/services`; Base de datos `app/infra` + `alembic`), más contenido, entrenamiento, documentación y la raíz para los comandos. `.vscode/settings.json` oculta lo que generan las herramientas (cachés, `node_modules`, entornos virtuales, `openapi.json`). `docs/ESTRUCTURA.md` explica las 4 partes, cómo se comunican (diagrama) y un ejemplo de punta a punta.

## D-033 · Tienda con accesorios de Tomi para gastar el néctar · 04/11/2026
- Contexto / problema: el néctar solo se gasta en el protector de racha (50, máximo 2, R5.9) y en recargar vidas (30, R5.14). La recarga solo se ofrece en el modal «Sin vidas». Quien ya tiene 2 protectores y casi nunca se queda sin vidas acumula néctar sin ningún uso. El mockup §3.1 ya tiene «🛍 Tienda» en la barra lateral, pero la especificación (§1, tabla de alcance) deja «Accesorios de Tomi en la tienda» **fuera de alcance**, en la hoja de ruta.
- Opciones consideradas:
  1. **Tienda con accesorios de Tomi** (cosméticos) + protector y recarga de vidas en el mismo lugar: ya está en el mockup y en la hoja de ruta; no toca evaluación, puntaje ni vidas. En contra: pide tabla nueva, migración y dibujos SVG.
  2. **Pistas en los ejercicios** (pagar para quitar una opción incorrecta): útil para aprender. En contra: toca la evaluación y el puntaje, que es la parte más delicada (D20, D23); abarata los retos y obliga a revisar que no se filtre la respuesta.
  3. **Temas de color de la ruta:** fácil. En contra: aporta poco y no usa a la mascota.
  4. **Contenido extra pagado:** no hay contenido listo (el Módulo 4 dice «Próximamente») y cobrar por aprender va en contra del objetivo de la plataforma.
  5. **No hacer nada:** cero riesgo. En contra: el néctar se acumula sin uso y la tienda del mockup no existe.
- Decisión: opción 1, como **Grupo 12 opcional, después del Grupo 11**, igual que se hizo con el 10B; no debe retrasar el cierre ni la entrega.
  1. **Catálogo en `content/shop.json`** (como las señas): `id` (slug), nombre, precio, `requiredModule` opcional y el dibujo. `alas content check` lo valida y `alas db seed` lo carga. Propuesta inicial, a ajustar por el equipo: gorra 40 · gafas 60 · bufanda 80 · flor 100 · birrete 120 (requiere terminar el Módulo 3) · corona 150.
  2. **Reglas en el dominio** (`domain/policies/shop.py`, Python puro y probado primero): no se compra dos veces (`ALREADY_OWNED`), hace falta néctar suficiente (`NOT_ENOUGH_NECTAR`, el mismo código del protector) y el módulo requerido (`ITEM_LOCKED`). Solo se pueden poner accesorios comprados. Tomi lleva **un accesorio a la vez**.
  3. **Compra** como la del protector (D-013.5): bloquea al usuario (`FOR UPDATE`), clave primaria compuesta en `user_items` con `ON CONFLICT DO NOTHING RETURNING`, y el néctar solo se descuenta si se insertó la fila (igual que los logros, B5). `purchased_at` lo fija el servicio con `clock.now()` (D22).
  4. **Recarga de vidas en la tienda** siempre que falten vidas (y `HEARTS_ENABLED`): la API ya lo permite (solo devuelve `HEARTS_FULL` con 5); cambia solo la interfaz.
  5. **Derechos de datos:** los accesorios comprados y el puesto entran en la exportación de la cuenta y se borran con ella.
- Consecuencias:
  - **Base de datos:** tablas `shop_items` y `user_items`, columna `users.equipped_item_id` (nula), una migración nueva.
  - **API:** `GET /shop`, `POST /shop/items/{id}/purchase`, el accesorio puesto en `PATCH /me` y `GET /me`; tipos regenerados con `alas gen-api`.
  - **Web:** página `/tienda`, enlace «Tienda» en la barra lateral (mockup §3.1) y `Tomi` con el accesorio en la ruta, la celebración y el perfil.
  - **Pruebas:** dominio, API (compra simultánea doble → un solo descuento, sin néctar, bloqueado, exportación) y Vitest.
  - Tareas en `docs/specs/tasks.md`, Grupo 12.
- Secciones afectadas de la especificación: **contradice la tabla de alcance de §1** («Accesorios de Tomi en la tienda» está fuera de alcance) y amplía §5 (modelos), §8 (API) y §9 (interfaz). La especificación está protegida: **el equipo debe aprobar este cambio** antes de empezar el Grupo 12. Si no se aprueba, se puede hacer solo el punto 4 (recarga de vidas visible siempre), que no contradice la especificación.

## D-034 · Detalles del cierre (Grupo 11) · 04/11/2026
- Contexto: el Grupo 11 deja ambigüedades: qué caché llevan los archivos de `dist/` que no son `assets/`, cómo entran a la imagen los archivos de MediaPipe (no están en git) y cómo cumplir el plan de §17.4 con las reglas reales del repaso.
- Opciones consideradas:
  - Caché de `dist/`: (a) solo `assets/` inmutable y el resto `no-cache` — los modelos y el WASM se republican con el mismo nombre; (b) caché larga para todo — un modelo nuevo no llegaría a los navegadores.
  - MediaPipe en Docker: (a) una etapa que ejecuta el mismo `alas camera-assets` — una sola fuente de URLs; (b) versionar `public/mediapipe/` (~70 MB) — repositorio pesado; (c) descargar con un script aparte — URLs duplicadas.
  - Repaso de hace 2 días en la demo: (a) un «Necesito repasar» (sin puntaje) hace 3 días en una letra que ese día sale en una sola lección; (b) un error con puntaje — contradice «3 errores ayer»; (c) saltarse el repaso — contradice §17.4.
- Decisión:
  1. **`SpaFiles` + `SpaMount`** (`app/core/spa.py`): `assets/` con `immutable`; `index.html`, modelos, WASM y demás con `no-cache` (revalidan con ETag). Las rutas sin archivo bajo `api`, `media`, `mediapipe`, `models` y `assets` dan 404 con el formato de error (un script o el modelo nunca reciben HTML). La exclusión es por segmento (`/apiario` sí es de la SPA). El montaje nunca atrapa `/api`: una ruta de la API agregada después de `create_app` sigue funcionando y un método equivocado da 405 con `Allow`. Sin `dist/` la app arranca y la SPA da 404.
  2. **Dockerfile en 5 etapas** (dependencias npm → API → `alas camera-assets` → compilar la SPA → imagen final). `uv` fijo en 0.13.6 (el que generó `uv.lock`). La imagen corre con un usuario sin privilegios. `.dockerignore` deja fuera `public/mediapipe/` local para que la imagen sea igual a la que construye Render desde git.
  3. **Demo (§17.4):** con todo acertado ninguna seña vence hace 2 días (cada lección del día refuerza la seña, §7.7), así que hace 3 días la demo pulsa «Necesito repasar» en la primera letra que ese día solo aparece en una lección y tiene «Produce la seña»; esa letra vence hace 2 días y entra al repaso. No es un error: no tiene puntaje ni quita vidas. Los **3 errores de ayer** van en el reto M1-N4-L4 (la última lección del día; en L3 la letra se reprogramaría al acertarla en L4 y saldría de la cola). El reto queda 9/12 = 75 % ≥ 70 %, aprobado. La prueba cuenta como «error» solo las respuestas con puntaje.
  4. **`alas e2e`**: compila, migra y siembra `alas_test` y arranca uvicorn con `APP_ENV=production` (sin `/api/docs`, cookie `Secure`) en un puerto libre de `localhost`, con un `JWT_SECRET` nuevo en cada ejecución. Instala Chromium y Firefox si faltan.
  5. **`data-testid`** de §15 en el frontend: `lesson-option-<n>`, `check-answer`, `continue`, `hearts`, `node-<id>`, más `lesson-<id>` y `active-exercise` (el ejercicio en curso, para no confundirlo con el video que se precarga oculto).
  6. **Actividades que la lección no trae** (p. ej. L1 sin «Usa lo aprendido»): la tarjeta dice «No incluida en esta lección», en gris y sin 🔒. Antes decía «🔒 Pendiente» hasta el final y parecía bloqueada (lo reportó el usuario).
  7. **Correcciones de la revisión (`revisor-codigo`):**
     - La SPA respondía `media/manifest.json` con rutas como `/x/..%2Fmedia%2Fmanifest.json` o `/MEDIA/manifest.json`, porque StaticFiles normaliza la ruta y en Docker el manifiesto está dentro de `dist/` (B54). Ahora:
       - una ruta con segmentos `.` o `..` da 404;
       - `api` y `media` dan 404 siempre dentro de la SPA;
       - las carpetas reservadas se comparan sin distinguir mayúsculas (en Windows el disco no las distingue).
     - La demo nunca borra una cuenta real (`is_demo = false`) que use `DEMO_EMAIL`, ni con `--reset`.
     - La demo valida `DEMO_PASSWORD` y que el contenido esté cargado antes de tocar la base. Si falla a mitad de camino, borra lo que alcanzó a crear.
     - `alas e2e` exige que `DATABASE_URL_TEST` termine en `_test`.
     - `.dockerignore` excluye los `.env` de todas las carpetas.
     - El código de la imagen queda de root: solo lectura para el proceso.
  8. `alas e2e` y las pruebas de API comparten `alas_test`: **no se ejecutan a la vez** (lo dice el `README.md`).
- Consecuencias: pruebas nuevas en `tests/unit/test_spa.py`, `tests/api/test_demo.py`, `tests/unit/test_demo_guard.py`, `tests/e2e/test_main_flow.py` y Vitest de las tarjetas de actividades.
- Secciones afectadas de la especificación: ninguna contradicha; §17.1 se amplía con la etapa de MediaPipe y §17.4 se cumple con el «Necesito repasar» del punto 3.

## D-035 · IP del cliente detrás del proxy (límites de inicio de sesión y registro) · 05/11/2026
- Contexto / problema: el arranque de §17.1 usa `uvicorn --proxy-headers --forwarded-allow-ips='*'`. Con `'*'`, uvicorn 0.54 toma el **primer** valor de `X-Forwarded-For` (`x_forwarded_for_hosts[0]`), que escribe el propio cliente. Un atacante cambiaría ese valor en cada intento y se saltaría el límite de inicio de sesión (5/min por IP + correo, §11) y el de registro (10/min por IP). Render no documenta con claridad su cadena de proxies: hay reportes de que no limpia el `X-Forwarded-For` del cliente y solo agrega la IP que ve al final.
- Opciones consideradas:
  1. **Confiar solo en los últimos N valores** (`TRUSTED_PROXY_HOPS`, que agregaron proxies de confianza) y, ante cualquier duda, en la conexión directa. No se puede falsificar y no depende de conocer las IP internas de Render. En contra: si delante hay otro proxy que no se contó (p. ej. Cloudflare), todos comparten su IP. El límite por IP + correo sigue funcionando; el de registro sería más estricto.
  2. **Restringir `--forwarded-allow-ips` a la red interna de Render.** Correcto en teoría. En contra: Render no publica esos rangos de forma estable.
  3. **Leer `True-Client-IP`.** En contra: no está confirmado que Render la reescriba siempre; si no lo hace, también se falsifica.
  4. **Dejar `'*'`, como está en §17.1.** Cero cambios. En contra: el límite de inicio de sesión no protege nada.
- Decisión: opción 1, con la 3 disponible de forma opcional.
  - `app/core/client_ip.py` (`resolve_client_ip`): `X-Forwarded-For` nunca se usa con `TRUSTED_PROXY_HOPS=0` (por defecto en local). Con N > 0 se usa el valor N contando desde el final. Si faltan valores o no es una IP válida, se usa la conexión directa.
  - `CLIENT_IP_HEADER` (opcional, p. ej. `True-Client-IP`) tiene prioridad solo si trae una IP válida. Se debe configurar únicamente después de comprobar en el despliegue que el proxy la reescribe.
  - La imagen arranca uvicorn con `--no-proxy-headers` (nunca reescribe la IP con lo que mande el cliente) y `TRUSTED_PROXY_HOPS=1`.
- Consecuencias: `Settings.trusted_proxy_hops` y `Settings.client_ip_header`, `deps.client_ip` usa la regla nueva. Pruebas en `tests/unit/test_client_ip.py` (17) y 2 de API en `test_auth.py`, que reproducen el ataque rotando `X-Forwarded-For`. Con la conexión HTTP interna, `request.url.scheme` queda en `http`; la app no arma URLs absolutas y la cookie `Secure` depende de `APP_ENV`, no del esquema.
- Secciones afectadas de la especificación: **cambia el comando literal de §17.1** (`--proxy-headers --forwarded-allow-ips='*'` → `--no-proxy-headers` + `TRUSTED_PROXY_HOPS=1`) y concreta §11 («leer la IP real de X-Forwarded-For solo desde el proxy de confianza»). La especificación está protegida: **el equipo debe aprobar este cambio**. La intención de §11 se cumple; lo que cambia es el mecanismo, porque el de §17.1 no la cumplía.
- Al desplegar: comprobar en los registros de Render que dos personas distintas reciben IP distintas. Si todas salen iguales, delante hay otro proxy y se debe subir `TRUSTED_PROXY_HOPS` a 2.

## D-036 · Transiciones de la interfaz · 05/11/2026
- Contexto: el usuario pidió transiciones en la interfaz. Hasta ahora solo se movían Tomi (framer-motion) y el corazón al perder una vida.
- Opciones consideradas:
  1. **CSS (keyframes de Tailwind 4 en `index.css`)**, solo donde la persona hace algo. Sin dependencias nuevas y cubierto por la regla global de «movimiento reducido». En contra: no anima la salida de lo que se desmonta.
  2. **framer-motion en todos los componentes**, con `AnimatePresence` para las salidas. En contra: más código y más JavaScript en cada pantalla para un efecto pequeño.
  3. **Entradas con fundido en cada sección y efecto al pasar el mouse por cada tarjeta.** En contra: es el efecto genérico de siempre, distrae y no explica nada.
- Decisión: opción 1. El movimiento responde a una acción y muestra qué cambió:
  - **Botones presionables:** los botones con borde inferior grueso (`border-b-4`) se hunden 2 px al pulsarlos. Es una sola regla en `index.css`.
  - **Lección:**
    - cada ejercicio entra desde la derecha (`animate-exercise-in`);
    - la barra de avance crece suave;
    - las opciones cambian de color con transición; la correcta hace un pulso y la incorrecta un temblor leve, nunca un regaño;
    - el mensaje de Tomi aparece subiendo.
  - **Abrir:** el detalle de una lección crece desde su origen, las lecciones de un nodo se despliegan, y la celebración y «Sin vidas» entran con fundido y escala.
  - **Cambio de sección:** fundido de 160 ms del contenido (`<main>` con `key` por ruta).
  - **«Aleteo» (el único movimiento sin clic):** la próxima lección por hacer flota como un colibrí suspendido, dos veces, y se detiene. Señala el siguiente paso y va con la mascota.
- Consecuencias:
  - Con «movimiento reducido» todo queda casi instantáneo por la regla global que ya existía (R10.5).
  - Prueba Vitest: solo la próxima lección tiene `animate-aleteo` y `data-next`.
  - `alas e2e` sigue en verde con las animaciones.
- Secciones afectadas de la especificación: ninguna contradicha. Amplía §9.5 (diseño); §9.3 ya pedía *scroll* suave y el corazón que late.

## D-037 · Registro de la autorización de tratamiento de datos · 06/11/2026
- Contexto / problema: la casilla «Acepto la política de tratamiento de datos (Ley 1581 de 2012)» era obligatoria, pero el servidor solo comprobaba que viniera marcada: no guardaba ni el sí ni la fecha. La Ley 1581 pide poder demostrar que cada persona autorizó el tratamiento de sus datos.
- Opciones consideradas:
  1. **Guardar la fecha y la versión de la política en `users`.** Simple y suficiente para demostrar la autorización. En contra: si la política cambia, solo queda la última aceptación.
  2. **Tabla de historial de autorizaciones.** Guarda todas las aceptaciones. En contra: más tablas y pantallas para un caso que hoy no existe (no hay re-aceptación).
  3. **Usar `created_at` como fecha de autorización.** Cero cambios. En contra: no dice qué versión se aceptó y mezcla dos conceptos.
- Decisión: opción 1.
  - Columnas `users.data_policy_accepted_at` (la fija el servidor con `clock.now()`, D22) y `users.data_policy_version`. Migración `8483232b2587`.
  - La versión es la fecha del texto de `/privacidad`, en `app/core/privacy.py` (`DATA_POLICY_VERSION = "2026-11-06"`). La página la muestra («Versión del 6 de noviembre de 2026»). Una prueba exige que las dos coincidan.
  - El cliente no puede enviar esos valores: `extra="forbid"` da 422.
  - La exportación de datos del perfil incluye la fecha y la versión.
  - Las cuentas anteriores quedan en NULL: aceptaron la casilla, pero no se registró cuándo, y no se inventa una fecha.
- Consecuencias: tipos de la API regenerados; pruebas en `test_auth.py`, `test_account.py` y `tests/unit/test_privacy.py`. Si cambia el texto de la política, hay que cambiar la versión en los dos lugares. Si algún día se pide volver a aceptar una política nueva, se pasa a la opción 2.
- Secciones afectadas de la especificación: amplía §5 (modelo `User`) y §11 (privacidad, Ley 1581). No contradice nada.

## D-038 · Optimizar la cámara beta para señas estáticas · 09/11/2026 (integrada el 11/11/2026)
- Estado: **implementada e integrada en `main`** por decisión del usuario (11/11/2026). Ver «Decisión» al final de esta entrada.
- Contexto / problema: la cámara beta tarda en reconocer las señas estáticas y se ve con pocos FPS. Quien la usa siente que va lenta.
- Objetivo: reconocer las señas estáticas más rápido y subir los FPS, **sin afectar el resto del proyecto**: mismo modelo y contrato de clasificación, mismas pruebas en verde y el Grupo 10B intacto.
- Primer paso propuesto: **medir antes de cambiar.** Hay que saber en qué se va el tiempo de cada cuadro (captura, `HandLandmarker`, normalización, clasificador de TensorFlow.js o dibujo en pantalla) y probarlo en 2 portátiles, uno de gama media. La meta de referencia es ≥ 12 FPS (anexo, H7 y 10B.5).
- Opciones a evaluar (sin decidir):
  1. Procesar en un *Web Worker* para no bloquear el dibujo de la interfaz.
  2. Bajar la resolución de entrada solo para la detección (`getUserMedia` 640×480 o menos) y saltar cuadros si el anterior sigue en proceso.
  3. Backend WebGL/WebGPU de TensorFlow.js y calentar el modelo al abrir la cámara.
  4. Para señas estáticas: decidir con pocos cuadros estables (umbral + ventana corta) en lugar de esperar una secuencia larga.
  5. Degradación escalonada si los FPS caen (anexo A.8.1).
- Restricciones: `@tensorflow/tfjs` exacto 4.22.0; no cambiar `ml/fixtures/` ni los nombres de los archivos del conversor; textos en español de Colombia.
- Secciones afectadas de la especificación: por definir. Probablemente §cámara (HandLandmarker) y anexo A.8.1, para ampliarlos, sin contradecirlos.
- Decisión (11/11/2026), solo para la cámara del alfabeto (`hand-v1`); la de gestos del 10B no cambia:
  1. **Un cuadro de la cámara = un análisis:** `requestVideoFrameCallback` en `camera/frame-loop.ts`, con respaldo a `requestAnimationFrame` si el navegador no lo tiene. Antes MediaPipe analizaba a veces dos veces la misma imagen.
  2. **Modelo calculado en JavaScript** (`camera/dense.ts`): copia los pesos del modelo denso y lo calcula sin tfjs en cada cuadro. Misma salida que TensorFlow.js con el modelo real (diferencia < 1e-5, `dense.test.ts`). **No** cambia el backend global de tfjs, que sigue usando el modelo de gestos en la misma página. Si el modelo no es solo de capas densas, se usa tfjs como antes.
  3. **Reconocer por tiempo además de por cuadros:** el `Smoother` también acepta la seña si se mantiene 250 ms con al menos 3 votos y mayoría (ventana de 600 ms). A 30 FPS se comporta igual que antes (6 de 10). B37 se mantiene: nunca basta un cuadro aislado.
  4. Dibujo de la mano en un solo trazo.
  5. **Contador de FPS y ms por cuadro**, visible solo para quien administra.
- Pendiente: medir en vivo en 2 portátiles (meta ≥ 12 FPS) y anotar las cifras aquí.

## D-039 · PROPUESTA (pendiente) · Animaciones tipo GIF para módulos, diccionario y repaso · 09/11/2026
- Estado: **idea registrada, sin implementar.** No se toca código hasta que el equipo la apruebe.
- Contexto / problema: grabar un video real por seña limita cuántas señas se pueden mostrar, y los videos ocupan espacio en el repositorio y en el despliegue.
- Propuesta: en **módulos, diccionario y repaso**, mostrar las señas como animaciones en bucle (tipo GIF). Eso amplía el repertorio y consume menos espacio. **Para entrenar la cámara se siguen usando videos de personas reales** (`ml/` y `video-extract.ts` no cambian).
- Advertencia técnica, a revisar antes de decidir: un GIF suele pesar **más** que un MP4 H.264 de la misma duración, por limitaciones del formato (256 colores y compresión débil). Para ahorrar espacio de verdad conviene evaluar:
  1. **MP4 corto en bucle** (`<video autoplay muted loop playsinline>`): se ve igual que un GIF y pesa menos. Ya encaja con D7/D19; bastaría bajar la resolución o subir el CRF.
  2. **WebP o AVIF animado:** formatos de imagen animada mucho más livianos que el GIF.
  3. **GIF clásico:** el más compatible, pero el más pesado.
- Puntos por resolver:
  - origen y **licencia** de las animaciones si no son propias;
  - validación de cada seña con el intérprete (`docs/validacion-interprete.md`);
  - cambios en `alas content videos` y en `media/manifest.json` (nuevo `source`);
  - accesibilidad: con «movimiento reducido» (R10.5) la animación debe poder pausarse.
- Secciones afectadas de la especificación: **cambiaría D7 y D19** (formato de los videos) y el §6.4 (procesamiento de contenido). La especificación está protegida: requiere aprobación del equipo.

## D-040 · Cámara: 2 = V y 3 = W como señas equivalentes · 10/11/2026
- Contexto: el usuario notó que la cámara del alfabeto a veces muestra «V» al hacer el 2 y «W» al hacer el 3, y que el 1 a veces se reconoce y a veces no.
- Evidencia (modelo publicado sobre su propio dataset, LSC70 + LSC-54; en vivo es algo peor):

  | Seña | Acierto | Con confianza ≥ 0,70 | Confusión principal |
  |---|---|---|---|
  | 3 | 56 % | 36 % | W 12,5 % (62 de las «W» son 3) |
  | 2 | 65 % | 46 % | NINGUNA 8,6 %, R 6,4 %, V 4,9 % (24 de las «V» son 2) |
  | 1 | 82 % | 73 % | sin una confusión dominante (NINGUNA 4 %) |
  | B (referencia, D-027) | 81 % | 67 % | 4 en el 12,2 % |

- Decisión: mismo mecanismo que B = 4 (D-027). Se añaden `numero-2,letra-v` y `numero-3,letra-w` a `content/camera-equivalences.csv`. En una lección cuenta cualquiera del par; en `/camara` se muestran las dos («2 / V», «3 / W»). No hace falta reentrenar.
- El 1 **no** recibe un par: no se confunde con otra seña, sino que su confianza queda cerca del umbral de 0,70. La solución es reentrenar con más muestras de los números (grabar al equipo en `/admin/dataset`), como ya pedía D-024.
- Pendiente con el intérprete: confirmar los dos pares. 2 y V tienen la misma forma de mano. El 3 y la W pueden diferir en LSC según el dedo (pulgar o anular): si el intérprete dice que no son iguales, se quita la fila y se reentrena con más datos del 3.
- Secciones afectadas de la especificación: ninguna; amplía D-027.

## D-041 · Cámara: sumar las probabilidades de las señas equivalentes · 10/11/2026
- Contexto: el usuario pidió mejorar el reconocimiento con los datos que ya hay, sin grabar nuevas muestras.
- Experimento 1, reentrenar (validación cruzada por persona, 5 pliegues, 40 épocas, misma semilla; con TensorFlow.js 4.22.0 en Node, porque TensorFlow no instala en Windows, D-020):

  | Configuración | Acierto | Pasan 0,70 | Seña equivocada | NINGUNA como seña |
  |---|---|---|---|---|
  | A · como hoy | 82,3 % | 75,7 % | 7,2 % | 3,4 % |
  | B · clases equilibradas | 81,5 % | 76,2 % | 8,0 % | 7,4 % |
  | C · aumento (rotación ±20°, ruido) | 82,4 % | 74,6 % | 6,7 % | 2,9 % |
  | D · B + C | 80,9 % | 74,1 % | 7,4 % | 5,5 % |

  Ninguna mejora de forma clara: las diferencias son de alrededor de 1 punto. B duplica las falsas alarmas y C empeora el 2. **El modelo publicado se queda.** El límite está en los datos: 2, 3 y NINGUNA solo los hicieron 18 personas (LSC-54).
- Experimento 2, sin reentrenar: sumar las probabilidades de cada par de `camera-equivalences.csv` antes de aplicar el umbral. Medido con el modelo publicado sobre su dataset (cifras absolutas optimistas; la comparación es justa):
  - pasan 0,70: 3 de 40,8 % a 60,0 %; B de 74,1 % a 88,8 %; 2 de 48,0 % a 58,3 %; V, W y 4 suben entre 7 y 10 puntos;
  - total de 76,1 % a 78,6 %; seña equivocada de 3,6 % a 3,7 %; NINGUNA como seña de 2,9 % a 3,8 %.
- Decisión (integrada en `main` el 11/11/2026 por decisión del usuario): `bestWithEquivalents` en `equivalences.ts`. El `DenseClassifier` suma cada par y lo devuelve siempre con la misma etiqueta (la primera en orden alfabético), para que los votos del suavizado no se repartan entre las dos. El umbral sigue en 0,70 (R8.2), pero se aplica a la suma del par.
- Consecuencias: en `/camara` se ve «W / 3» en lugar de «3 / W». El registro de reconocimientos (Ojo de colibrí) guarda la etiqueta del par.
- Secciones afectadas de la especificación: interpretación de R8.2 (la confianza es la del par cuando hay equivalencias). La especificación está protegida: **el equipo debe ratificar esta interpretación**.

## D-042 · Iconos propios para la racha, el néctar y las vidas · 11/11/2026
- Contexto: el usuario entregó tres ilustraciones (llama, flor y corazón) para reemplazar los emojis 🔥, 🌸 y ❤️, que se ven distintos en cada sistema operativo.
- Decisión: PNG de 128 px con fondo transparente en `apps/web/src/assets/icons/` (`racha.png`, `nectar.png`, `vida.png`), sacados de las ilustraciones originales sin el fondo crema ni los destellos. Se muestran con `StreakIcon`, `NectarIcon` y `HeartIcon` (`components/icons/GameIcon.tsx`): son decorativos (`alt=""`) porque el texto de al lado ya dice qué son, y los `aria-label` («Racha: 5 días», «Vidas: 4») no cambian. Vite les agrega un hash al nombre (12–16 KB cada uno).
- Dónde: barra superior, panel «Tu día», celebración de la lección, resultado del repaso y contador de vidas de la lección (conserva el latido de D-036).
- Secciones afectadas de la especificación: ninguna contradicha. Ajusta lo visual de §9.5 y de los mockups.

## D-043 · Ampliar la cámara de movimiento con más señas de LSC-54 · 12/11/2026
- Contexto: el modelo de gestos (`lsc-gestos`) usa 5 señas de LSC-54 (409 muestras, 18 personas). El inventario de LSC-54 S2 tiene 1.740 videos de 43 señas, y 13 de ellas están en el currículo y hoy se practican solo con autoevaluación. Análisis de factibilidad del plan `docs/plan-mejora-camara-movimiento.md` (12/11/2026): el límite es de personas y datos, no de herramientas.
- Datos: LSC-54 V4 (Science Data Bank, DOI 10.57760/sciencedb.25639, **CC BY-NC 4.0**). Se descargaron `Videos Courtesy.zip` y `Videos Numbers.zip` (MD5 verificado) a `Downloads\LSC-54\`, **fuera del repositorio** (la licencia no permite redistribuirlos). Se convirtieron de AVI a MP4 (H.264, misma resolución, 30 FPS) con nombres `Etiqueta__lsc54-s2-NN__toma.mp4` y un `_manifiesto.csv` con el origen de cada archivo. Se excluyó `Videos Courtesy/*/Números/*`, copia de `Videos Numbers.zip`, como en el repositorio de LSC-54. Resultado: 1.740 videos, 0 errores, 43 señas, 18 personas.
- Decisión: `content/dataset-mapping.csv` agrega Como esta → `como-estas`, Si → `si`, No → `no`, Permiso → `con-permiso` y Seis…Diez → `numero-6`…`numero-10`. Con el mapeo, el importador toma **1.005 videos de 19 clases**:
  - **18 personas:** hola, adiós, de nada, perdón, por favor, buenos días, buenas tardes, buenas noches y números 6–10 (51–57 videos cada una);
  - **9 personas:** gracias, ¿cómo estás?, sí, no, con permiso (26–29 videos cada una);
  - NINGUNA: 159.

  Los números 1–5 quedan fuera, porque son del modelo del alfabeto.
- Regla para publicar: se entrena con todas. Una seña entra al modelo publicado solo si alcanza la meta del anexo con **personas no vistas** (≥ 80 %, A.8 y 10B.10). Las que no la alcancen siguen con autoevaluación, sin empeorar a las demás. El modelo actual se conserva para poder revertir.
- Pendiente (humano): importar en `/admin/importar` (MediaPipe corre en el navegador), reentrenar en Colab y comparar por seña contra el modelo actual con validación por persona.
- LSC70W (70 personas, secuencias de 6 fotos) y LSC50 quedan sin usar por ahora: el primero solo se probaría para «hola», y del segundo falta confirmar el vocabulario antes de descargar 6,2 GB.
- Secciones afectadas de la especificación: ninguna contradicha. Amplía el anexo A (de 3–5 señas a más) siguiendo su regla A.7.

## D-044 · Importador de datasets: registro de licencias, botones, reanudar y origen de cada muestra · 12/11/2026
- Contexto: el usuario no podía abrir el selector de archivos en `/admin/importar` (el navegador integrado de VS Code no lo permite), pidió un botón visible y poder continuar una importación tras apagar el equipo. Además, la licencia de cada fuente estaba escrita en el código y solo conocía LSC-54, y las muestras exportadas no guardaban de qué video salían: no se podían quitar las de «Ayudar» de NINGUNA sin volver a importar todo.
- Decisión:
  1. **`content/datasets.csv`** (`fuente,licencia,enlace,cita`; la cita va entre comillas si tiene comas) con LSC-54 y LSC70. `alas content check` exige que cada fuente de `dataset-mapping.csv` esté registrada con licencia, enlace `https://` y cita, sin repetidas. La página de importación toma la licencia de ahí (ya no se escribe a mano) y `/creditos` lista los datasets registrados.
  2. **Página `/admin/importar`:** botones «Elegir archivos» y «Elegir carpeta» (`webkitdirectory`), zona para arrastrar y soltar, y resumen al elegir: «N archivos · N se importarán · N fuera del mapeo · N con nombre inválido». Solo se procesan los archivos con una seña del mapeo (antes, los demás contaban como «descartados»).
  3. **Progreso guardado en el navegador** (IndexedDB, `camera/holistic/import-progress.ts`): cada resultado se guarda al procesarse. Si se apaga el equipo o se cierra la pestaña, la página avisa «Tienes una importación sin terminar: N de M procesados»; al volver a elegir los mismos archivos se salta lo ya hecho (`planImport`, función pura con pruebas). «Descartar progreso» lo borra. Sin IndexedDB (ventana privada) funciona igual, solo que sin poder continuar después. Nada sale del equipo.
  4. **Origen de cada muestra:** `HolisticSample.origin = { file, sourceLabel }` (campo opcional y adicional; `train_sequence.py` lee los campos con `.get()` y no se afecta). Permite filtrar después, por ejemplo quitar una seña de NINGUNA, sin volver a importar.
  5. **NINGUNA** (`dataset-mapping.csv`): sale «Ayudar», que ≈ «Ayuda» del currículo (M3-N4). Entran 15 señas de LSC-54 fuera del currículo: apoyar, bienvenido, con gusto, esperar, excelente, invitar, lo siento, más o menos, muy bien, muy mal, necesitar, perfecto, presentar, sentarse y tranquilo (más bien y mal). «Baño» (M3-N2) y «Muchas gracias» (contiene «gracias») quedan fuera. Resultado: 516 videos de 17 señas. **Al entrenar hay que equilibrar NINGUNA**, que queda unas 10 veces más grande que cada seña.
- Consecuencia: el `dataset-lsc-54-holistic-v2.json` exportado el 12/11/2026 (946 muestras) se hizo con el mapeo anterior. Su NINGUNA incluye «Ayudar» y sus muestras no tienen `origin`. Para aplicar este cambio hay que volver a importar.
- Secciones afectadas de la especificación: ninguna contradicha. Amplía el anexo A.7 (importador y licencias).

## D-045 · Cámara de movimiento: versión reducida del plan de mejora (captura manual, guía de grabación y evaluación con el umbral) · 12/11/2026
- Contexto: el usuario pidió ejecutar `docs/plan-mejora-camara-movimiento.md`, pero solo los puntos más factibles. El análisis previo le dio al plan completo 52/100 y a esta versión reducida 80/100. Lo que limita la mejora son las personas (unos 18 a 20 señantes, todos de LSC-54), no las herramientas. Además, TensorFlow no instala en Windows (D-020).
- Decisión:
  1. **Captura manual (etapa 6, primera parte)** en Cámara beta (`GesturePractice`) y en el colector `/admin/gestos`: «Yo marco el inicio y el fin», con «Terminar» (recibe el foco, así que funciona con Enter o espacio) y «Cancelar». Dura entre 0,5 y 4 s (`camera/holistic/capture.ts`, `MANUAL_CAPTURE`). El modo de 2 s sigue siendo el **predeterminado**, y las lecciones (`GestureCheck`) no cambian. Las dos capturas terminan en la misma secuencia de 30 cuadros recortada al tramo con mano, igual que en el importador, así que **el modelo publicado no cambia y no hace falta un contrato nuevo**. Si se pulsa «Terminar» antes de 0,5 s, el mensaje es «captura incompleta», distinto de «no reconocida». Una captura cancelada o interrumpida nunca se clasifica. El inicio y el final automáticos quedan **fuera** del alcance: hay que validarlos antes.
  2. **Guía de grabación (etapa 4, herramientas):** `docs/guia-grabacion-gestos.md`. Cubre la autorización y el alias fijo; las prioridades: hola/adiós y NINGUNA primero, luego sí, no, gracias, ¿cómo estás? y con permiso, que tienen pocas muestras; las variaciones; qué es y qué no es NINGUNA; y una tabla de balance. Además, el colector ofrece ahora todas las señas del mapeo, no solo saludos y cortesía. **Las grabaciones dependen de personas y no se inventan.**
  3. **Evaluación con la decisión real de la aplicación (etapa 5, procedimiento):**
     - `train_sequence.py` mide, en la validación cruzada por persona, el acierto **con el umbral 0,70**: igual que `decide`, por debajo pasa a NINGUNA («no reconocida»).
     - Reporta por seña el acierto, la precisión, las no reconocidas y las confusiones, y las falsas detecciones de NINGUNA.
     - Calcula las señas **publicables**: ≥ 80 % y ≥ 10 muestras (D-043). Opciones `--min-recall` y `--min-samples`.
     - Todo queda en `reporte-gestos.json`.
     - `--balance` aplica pesos por clase, calculados solo con el entrenamiento de cada pliegue.
     - Sin opciones nuevas, el entrenamiento es el de antes; `cvAccuracy` sigue siendo el *argmax*, para poder comparar.
  4. **Cuaderno `ml/notebooks/entrenamiento-gestos.ipynb`:**
     - Entrena dos candidatos en carpetas aparte: las 5 señas actuales, para comparar seña por seña, y todas las señas.
     - Nunca escribe sobre `apps/web/public/models/lsc-gestos/`.
     - La publicación es manual: se guarda una copia del modelo anterior, se publican solo las señas publicables y se prueba con personas no vistas.
- Ajustes tras la revisión de código:
  - en cada pliegue, la **parada temprana** usa personas del propio entrenamiento y nunca las evaluadas (`fold_split`); antes, el acierto «con personas no vistas» salía optimista, también en el modelo publicado (89,7 %);
  - `--out` es **obligatorio** en `train_sequence.py`, para que un entrenamiento de prueba no sobrescriba el modelo publicado;
  - el umbral se compara en doble precisión, como en TypeScript.
- Fuera de alcance por ahora: el visor de fotogramas y el recorte editable (etapas 2 y 3), que solo valen la pena si el reentrenamiento muestra que el problema son los datos; y una representación nueva (`holistic-v3`, etapa 5b).
- Pendiente (personas): grabar al equipo, entrenar en Colab y probar con personas que no grabaron. **No hay un modelo nuevo entrenado ni una mejora de precisión medida**: la interfaz por sí sola no lo demuestra.
- Secciones afectadas de la especificación: ninguna contradicha. El anexo A.4 fija ventanas de 2 s para la captura, y ese modo sigue siendo el predeterminado; el manual es una alternativa en Cámara beta y en el colector. **El equipo debe aprobar** esta interpretación.

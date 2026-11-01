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

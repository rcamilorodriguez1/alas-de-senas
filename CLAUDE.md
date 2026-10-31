# Alas de Señas — instrucciones para Claude Code

Plataforma web estilo Duolingo para aprender Lengua de Señas Colombiana (LSC). Mascota: Tomi, un colibrí.
Proyecto académico de Ingeniería de Sistemas. Entrega: portátil y PC (no celulares).

## Fuentes de verdad (léelas en este orden)
1. `docs/specs/requirements.md` — QUÉ debe hacer el sistema (criterios EARS).
2. `docs/specs/design.md` — CÓMO se cumple, en resumen.
3. `docs/especificacion.md` — detalle técnico completo (v3.3). Manda sobre los demás en lo técnico.
4. `docs/anexo-camara-holistica.md` — solo para el Grupo 10B.
5. `docs/mockups.md` — referencia visual (ignorar las vistas móviles).
6. `docs/specs/tasks.md` — QUÉ HACER AHORA. Una tarea a la vez.
7. `docs/harness.md` — cómo funcionan los hooks, comandos y subagentes de este repositorio.

Los documentos de especificación están protegidos contra edición. Si algo debe cambiar, usa `/decision` y avísame.

## Lenguajes
- **Python 3.12 (uv)** en todo lo que no corre en el navegador: API FastAPI, dominio, SQLAlchemy/Alembic, CLI `alas`, contenido, pruebas (pytest y Playwright para Python).
- **Python 3.11** en `ml/` (TensorFlow 2.15) para entrenar modelos.
- **TypeScript** SOLO en `apps/web`.

## Comandos (desde la raíz)
`uv run alas dev` · `uv run alas check` · `uv run alas gen-api` · `uv run alas db up|migrate|seed|reset` ·
`uv run alas content placeholders|videos|check|all` · `uv run alas camera-assets` · `uv run alas e2e` · `uv run alas start-prod`

## Reglas no negociables
- Reglas de negocio SOLO en `apps/api/app/domain` (Python puro, con pruebas). Sin imports de fastapi/sqlalchemy ahí.
- Pruebas primero en toda tarea con lógica. Nunca saltes, borres ni debilites pruebas.
- Prohibido: `Any` explícito, `type: ignore` sin código y motivo, `any`/`@ts-ignore` en TS, `round()` y `hash()` en reglas,
  `datetime.now()` en el dominio, SQL con f-strings, `shell=True`, tokens en localStorage, enviar respuestas correctas al cliente,
  escribir a mano tipos de respuestas de la API (se generan con `alas gen-api`), `pip install` (usar `uv add`, con permiso).
- `order_by` explícito en toda consulta ordenada. Completar lecciones y repasos en transacción SERIALIZABLE e idempotente.
- Tiempos de negocio (`started_at`, `answered_at`, `completed_at`…) los fija el servicio con `clock.now()`, nunca `server_default` (D22).
- El repaso lo evalúa el servidor: nunca un endpoint donde el cliente envíe sus aciertos (D23). Vidas: función pura derivada de `hearts_updated_at` (D24).
- `ml/`: versiones de `ml/pyproject.toml` fijas; `GRU(..., reset_after=False)`; no renombrar los archivos del conversor. `@tensorflow/tfjs` exacto 4.22.0.
- `.github/workflows/ci.yml` y `ml/fixtures/` vienen en el kit: no reescribirlos.
- Fechas de negocio con `to_local_day` (America/Bogota) y `Clock` inyectado.
- Textos de interfaz en español de Colombia; código en inglés; JSON de la API en camelCase.
- Nuevas dependencias o cambios de decisión → `docs/DECISIONES.md` (comando `/decision`).

## Harness (ver docs/harness.md)
- Hooks: bloquean comandos peligrosos y código que viola estas reglas; formatean cada archivo editado; no te dejan terminar el turno si ruff, mypy o las pruebas unitarias fallan. **Si un hook te bloquea, corrige la causa; no intentes rodearlo.**
- Comandos del usuario: `/fase N`, `/verificar [N]`, `/estado`, `/decision <texto>`, `/riesgos [alcance]`.
- Subagentes: `escritor-pruebas` (pruebas desde la especificación), `revisor-codigo` (solo lectura), `verificador-fase` (verificación independiente).

## Al terminar cada grupo de tareas
`uv run alas check` en verde → revisión de `verificador-fase` y `revisor-codigo` → `docs/PROGRESS.md` actualizado → commit `feat(grupo-N): …` → decirle al usuario qué debe verificar a mano.

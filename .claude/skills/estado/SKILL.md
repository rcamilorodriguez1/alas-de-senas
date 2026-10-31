---
name: estado
description: Resume el avance del proyecto según tasks.md, PROGRESS.md y git.
disable-model-invocation: true
---

Dame el estado del proyecto en menos de 15 líneas:

- Grupos terminados y grupo actual (según los `[x]` de `docs/specs/tasks.md`).
- Siguiente tarea pendiente.
- Pendientes de verificación manual anotados en `docs/PROGRESS.md`.
- Decisiones recientes de `docs/DECISIONES.md`.
- Cambios sin commit (`git status --short`) y último commit.
- Riesgos o bloqueos abiertos.

No modifiques ningún archivo.

---
name: fase
description: Implementa un grupo de tareas (fase) de docs/specs/tasks.md siguiendo el protocolo de Spec-Driven Development del proyecto.
argument-hint: [número de grupo, por ejemplo 0, 5 o 10B]
disable-model-invocation: true
---

Implementa el **Grupo $ARGUMENTS** de `docs/specs/tasks.md`. Sigue este protocolo sin saltarte pasos:

1. **Contexto.** Lee en `docs/specs/tasks.md` todas las tareas del Grupo $ARGUMENTS. Para cada una, lee los requisitos que cita en `docs/specs/requirements.md` y las secciones correspondientes de `docs/specs/design.md` y `docs/especificacion.md`. Si el grupo es 10B, lee también `docs/anexo-camara-holistica.md`.
2. **Precondición.** Comprueba en `docs/PROGRESS.md` que el grupo anterior está terminado. Si no lo está, detente y dímelo.
3. **Plan.** Escribe en `docs/PROGRESS.md` una sección `## Grupo $ARGUMENTS — <nombre>` con el plan: archivos a crear o cambiar y pruebas a escribir. Muéstrame el plan en 5–10 líneas antes de seguir.
4. **Una tarea a la vez**, en orden:
   - Si la tarea tiene lógica, delega primero en el subagente `escritor-pruebas` para escribir las pruebas a partir de la especificación (deben fallar antes de implementar).
   - Implementa lo mínimo para que pasen, respetando las capas (§4) y las reglas (§0.1).
   - Si un hook te bloquea, lee el motivo y corrige la causa; no intentes rodearlo.
   - Marca la tarea como `[x]` en `docs/specs/tasks.md` solo cuando sus pruebas pasen.
5. **Verificación.** Al terminar el grupo:
   - Ejecuta `uv run alas check` (cuando ya exista) y corrige hasta que pase.
   - Delega en el subagente `verificador-fase` la revisión independiente del grupo.
   - Delega en el subagente `revisor-codigo` la revisión contra el catálogo de riesgos (§14).
   - Corrige lo que reporten como bloqueante.
6. **Cierre.** Actualiza `docs/PROGRESS.md` (hecho, verificación manual pendiente para el usuario, riesgos) y haz commit `feat(grupo-$ARGUMENTS): <resumen>`.
7. **Reporte.** Dime en pocas líneas qué quedó hecho y **qué debo verificar a mano** (la línea «Verificar:» del grupo).

Si algo de la especificación es ambiguo o contradictorio, elige la opción más simple que cumpla los criterios, anótala en `docs/DECISIONES.md` y dímelo.

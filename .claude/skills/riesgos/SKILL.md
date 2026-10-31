---
name: riesgos
description: Revisa el código actual contra el catálogo de riesgos y bugs de la especificación (§14 y anexo H1–H11).
argument-hint: [grupo o carpeta a revisar, opcional]
disable-model-invocation: true
---

Delega en el subagente `revisor-codigo` una revisión de $ARGUMENTS (o de todo lo implementado si no indico nada) contra:

- El catálogo de riesgos §14 de `docs/especificacion.md` (B1–B95).
- Los riesgos H1–H11 de `docs/anexo-camara-holistica.md`, si ya existe código de la cámara holística.

Luego muéstrame una tabla con: riesgo, estado (cubierto / no cubierto / no aplica todavía), evidencia (archivo y prueba) y acción recomendada. Ordena primero los no cubiertos de mayor impacto. No modifiques código en este comando.

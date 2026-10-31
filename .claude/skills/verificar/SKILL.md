---
name: verificar
description: Ejecuta la verificación completa del proyecto y la lista de chequeo manual del grupo indicado.
argument-hint: [número de grupo, opcional]
disable-model-invocation: true
---

Verifica el estado del proyecto:

1. Ejecuta `uv run alas check` y muéstrame un resumen por paso (ruff, mypy, pytest, ESLint, tsc, Vitest, tipos de la API). Si algo falla, explica la causa raíz y propón la corrección; no la apliques sin confirmar si implica cambiar una decisión de la especificación.
2. Si indiqué un grupo ($ARGUMENTS), copia su línea **Verificar:** de `docs/specs/tasks.md` y conviértela en una lista de pasos concretos que yo pueda seguir en el navegador o la terminal, con el resultado esperado de cada uno.
3. Revisa la *Definición de terminado* (§0.3 de `docs/especificacion.md`) y marca cuáles puntos se cumplen y cuáles no.
4. No modifiques código en este comando, salvo que te lo pida después.

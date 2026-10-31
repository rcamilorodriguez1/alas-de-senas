---
name: decision
description: Registra una decisión técnica en docs/DECISIONES.md con problema, opciones y decisión.
argument-hint: [descripción breve de la decisión]
disable-model-invocation: true
---

Registra en `docs/DECISIONES.md` una nueva entrada sobre: $ARGUMENTS

Formato:

```
## D-<número siguiente> · <título corto> · <fecha de hoy>
- Contexto / problema:
- Opciones consideradas: (mínimo 2, con pros y contras en una línea cada una)
- Decisión:
- Consecuencias: (qué cambia en el código, las pruebas o la especificación)
- Secciones afectadas de la especificación:
```

Si la decisión contradice `docs/especificacion.md`, dímelo explícitamente: la especificación está protegida contra edición y el cambio debe aprobarlo el equipo.

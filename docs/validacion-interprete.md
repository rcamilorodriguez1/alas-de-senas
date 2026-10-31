# Validación con el intérprete — Alas de Señas

> Llevar esta hoja impresa a la **primera** reunión con el intérprete (semana 1). Cada respuesta se pasa a
> `content/signs.csv` o `content/conversations.yaml` y se ejecuta `uv run alas content check`.
> Mientras algo no esté confirmado, la app funciona igual con la propuesta inicial.

## 1. Alfabeto manual
| Pregunta | Respuesta del intérprete |
|---|---|
| ¿El alfabeto que vamos a enseñar incluye **CH**, **LL** y **RR** como letras propias? | ☐ Sí ☐ No ☐ Solo: ____ |
| ¿Se enseña la **Ñ** como letra aparte? | ☐ Sí ☐ No |
| ¿La K y la W se hacen con una seña propia? | ☐ Sí ☐ No |

Si incluye dígrafos: agregar filas `letra-ch` (después de C), `letra-ll` (después de L) y `letra-rr` (después de R) en `signs.csv`, con `category = alfabeto` y su `motion`. CH y LL van al nodo M1-N3; RR al M1-N4.

## 2. ¿Qué letras llevan movimiento?
Marcar **D** (dinámica: la mano se mueve) o **E** (estática: la mano queda quieta). Propuesta inicial: J, Ñ y Z dinámicas.

| A | B | C | D | E | F | G | H | I | J | K | L | M | N |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| E | E | E | E | E | E | E | E | E | **D** | E | E | E | E |

| Ñ | O | P | Q | R | S | T | U | V | W | X | Y | Z | CH · LL · RR |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| **D** | E | E | E | E | E | E | E | E | E | E | E | **D** | ¿? |

→ Columna `motion` de `signs.csv` (`static` / `dynamic`). Solo las **estáticas** se usan para entrenar la cámara del alfabeto.
→ ¿Hay letras estáticas que se parecen mucho entre sí (por ejemplo M/N, U/V)? Anotar: ____ (se evitan en las primeras 5–10 letras del modelo).

## 3. Lista de palabras
- [ ] Revisar las palabras de cada nodo (§6.2 de la especificación). Reemplazar las que no se usen en la región.
- [ ] Describir «cómo se hace» cada seña (columna `how_to`).
- [ ] Revisar las conversaciones marcadas con `# revisar` en `conversations.yaml` (¿la respuesta tiene sentido?).
- [ ] Revisar las palabras de deletreo (`spelling`) de M1-N3 y M1-N4.

## 4. Grabación
- [ ] Confirmar fechas de grabación por módulo (§18).
- [ ] Firmar la autorización de uso de imagen (Ley 1581 de 2012).

Fecha: ________  Intérprete: ______________________  Revisó (equipo): ______________________

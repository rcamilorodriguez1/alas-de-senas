# Guía de grabación: señas con movimiento

Plan de mejora de la cámara, paso B (D-045). Fecha: 12/11/2026.

## Para qué sirve

El modelo de señas con movimiento falla sobre todo con **personas que no vio**. Todas sus muestras vienen de LSC-54, unas 18 a 20 personas. Grabar al equipo suma personas nuevas, que es lo que más ayuda. Extraer más cuadros de los mismos videos no aporta nada.

Esta guía no reemplaza a un intérprete. Si una seña se hace distinto en otra región, eso lo decide una persona competente en LSC, no la cámara (ver `docs/validacion-interprete.md`).

## Antes de grabar

1. **Autorización.** Cada persona firma la autorización de uso de sus datos antes de grabar (anexo A.6). Sin firma no se graba. La casilla de `/admin/gestos` solo recuerda este paso; no reemplaza la firma.
2. **Alias, nunca el nombre.** Usa `equipo-01`, `equipo-02`… La misma persona usa **siempre el mismo alias**, en todas las sesiones y equipos. Así la validación por persona no la cuenta dos veces.
3. **Navegador.** Chrome o Edge en un portátil o PC, con una cuenta de administrador. No uses el navegador integrado de VS Code.
4. **Mano.** Configura en el perfil la mano con la que firmas. Si eres zurdo, el sistema refleja la imagen solo (D-028).
5. **Qué se guarda.** Solo números: la posición de las manos y de los hombros. Nunca la imagen. El archivo se descarga a tu equipo y **no se sube a ninguna parte**.

## Cómo grabar

1. Abre `/admin/gestos`, escribe tu alias y marca la autorización.
2. Elige **«Yo marco el inicio y el fin»** para las señas que duran más de 2 s, como «buenas noches», «¿cómo estás?» o «con permiso». Para las cortas, como «sí», «no» o los números, sirve cualquiera de los dos modos.
3. Elige la seña, pulsa «Grabar muestra» y espera el «3, 2, 1».
4. Haz la seña **completa**, empezando y terminando con las manos en reposo, abajo.
5. En el modo manual, pulsa «Terminar» (o Enter) en cuanto acabes. Si te equivocas, pulsa «Cancelar»: esa muestra no se guarda.
6. Si sale «Muestra descartada», lee el motivo (por ejemplo, la mano salió del cuadro o no se vieron los hombros) y repite.

## Qué grabar primero

Prioridades según cuántas muestras tiene hoy el dataset de LSC-54 (`ml/data/dataset-lsc-54-holistic-v2.json`) y lo que ya se vio en las pruebas:

| Prioridad | Seña | Muestras hoy | Motivo |
|---|---|---|---|
| 1 | hola, adiós | 42 y 54 | Se confunden entre sí (PROGRESS, 10B.10) |
| 1 | NINGUNA | 159 | Sin ella, la cámara «ve» señas que nadie hizo |
| 2 | sí, no | 17 y 16 | Muy pocas: no llegan al mínimo para publicarse |
| 2 | gracias, ¿cómo estás?, con permiso | 24, 26 y 28 | Pocas |
| 3 | el resto (por favor, de nada, perdón, buenos días, buenas tardes, buenas noches, 6 a 10) | 46 a 57 | Para sumar personas nuevas |

**Por persona y sesión** (unos 15 minutos):
- 5 tomas de cada seña de prioridad 1 y 2;
- 3 tomas de cada seña de prioridad 3;
- 10 de NINGUNA.

Mejor muchas personas con pocas tomas que pocas personas con muchas.

## Variar a propósito

Entre tomas cambia **una cosa a la vez**:

- **Velocidad:** normal, más lenta y más rápida, sin deformar la seña.
- **Distancia:** cerca (de la cintura para arriba) y lejos (con los hombros bien visibles).
- **Luz:** de día y de noche, con luz de frente; evita tener una ventana detrás.
- **Equipo:** al menos dos portátiles o cámaras distintas en total.
- **Ropa y fondo:** manga corta y larga; un fondo liso y uno con objetos.

## Qué es NINGUNA y qué no lo es

NINGUNA son **movimientos reales que no son una seña del modelo**:
- quedarse quieto con las manos abajo o sobre la mesa;
- acomodarse, rascarse, tocarse el pelo o la cara, ajustarse las gafas;
- entrar al cuadro y salir de él;
- alcanzar el mouse o el teclado, aplaudir, cruzar los brazos;
- otras señas de LSC que no están en el modelo.

No grabes como NINGUNA gestos que se parezcan a una seña del modelo; por ejemplo, agitar la mano para saludar se puede confundir con «hola» o «adiós». Si dudas, no la grabes.

**No** son NINGUNA los fallos de captura, como la cámara tapada, estar fuera de la silueta o la mano cortada por el borde. Esas muestras se descartan; no se etiquetan como NINGUNA.

## Después de grabar

1. Pulsa «Exportar dataset.json» y renombra el archivo: `dataset-equipo-<fecha>-<alias>.json`, por ejemplo `dataset-equipo-2026-11-15-equipo-01.json`.
2. Guárdalo en `ml/data/`. Esa carpeta está fuera de git (`.gitignore`), así que **no se sube al repositorio**.
3. Anota en la tabla de abajo cuántas tomas se hicieron.
4. Entrena con `ml/notebooks/entrenamiento-gestos.ipynb` en Colab (paso C). Sube el archivo de LSC-54 y los del equipo juntos.

## Balance de muestras (llenarlo al grabar)

| Alias | Fecha | Equipo / cámara | Luz | Señas y tomas | Notas |
|---|---|---|---|---|---|
| | | | | | |

## Lo que sigue dependiendo de personas

- **Grabar:** voluntarios del equipo con autorización firmada. Las grabaciones que no se hagan quedan pendientes; no se inventan.
- **Revisar las etiquetas y las variantes regionales:** un intérprete o una persona sorda usuaria de LSC.
- **Probar el modelo nuevo:** con personas que **no** grabaron. Si se prueba con quien grabó, el resultado sale inflado.

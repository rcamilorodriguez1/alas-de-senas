# 🐦 Alas de Señas — Kit de arranque para Claude Code

Esta carpeta **es el inicio de su repositorio**. Ya trae la especificación, los archivos de Spec-Driven Development y el *harness* (arnés) que controla a la IA. No muevan los archivos: cada uno está en la ruta donde Claude Code y los hooks lo buscan.

## 1. Orden de lectura (para el equipo y para la IA)

| # | Archivo | Qué es | Para quién |
|---|---|---|---|
| 1 | `LEEME-PRIMERO.md` | Este archivo: orden y primeros pasos | Equipo |
| 2 | `CLAUDE.md` | Instrucciones que Claude Code lee automáticamente en cada sesión | IA |
| 3 | `docs/specs/requirements.md` | **Qué** debe hacer el sistema (10 requisitos, criterios EARS) | Equipo + IA |
| 4 | `docs/specs/design.md` | **Cómo** se cumple cada requisito (resumen) | Equipo + IA |
| 5 | `docs/especificacion.md` | Especificación técnica completa v3.3 (Python + React) | IA (y consulta del equipo) |
| 6 | `docs/mockups.md` | Diseño visual de las pantallas (ignorar vistas móviles) | Equipo + IA |
| 7 | `docs/specs/tasks.md` | **Qué hacer ahora**: ≈ 80 tareas en 13 grupos, en orden | IA |
| 8 | `docs/anexo-camara-holistica.md` | Cámara de dos manos + rostro (Grupo 10B, opcional) | IA, solo en ese grupo |
| 9 | `docs/harness.md` | Cómo funcionan SDD, hooks, comandos y subagentes | Equipo |
| 10 | `docs/PROGRESS.md` · `docs/DECISIONES.md` | Bitácora y decisiones (las va llenando la IA) | Equipo + IA |

## 2. Estructura del kit

```
alas-de-senas/
├── LEEME-PRIMERO.md
├── CLAUDE.md
├── .gitattributes · .gitignore
├── .claude/
│   ├── settings.json              # permisos + hooks
│   ├── hooks/                     # guard_bash, guard_code, after_edit, quality_gate, session_start (Python)
│   ├── skills/                    # comandos /fase /verificar /estado /decision /riesgos
│   └── agents/                    # escritor-pruebas, revisor-codigo, verificador-fase
├── .github/workflows/ci.yml       # integración continua (se activa al subir a GitHub)
├── ml/                            # versiones de TensorFlow verificadas + modelos de prueba
│   ├── pyproject.toml · smoke_tfjs.py
│   └── fixtures/tfjs-smoke/
└── docs/
    ├── especificacion.md · anexo-camara-holistica.md · mockups.md · harness.md
    ├── validacion-interprete.md   # hoja para la primera reunión con el intérprete
    ├── plantillas/tfjs-compat.test.ts
    ├── PROGRESS.md · DECISIONES.md
    └── specs/ requirements.md · design.md · tasks.md
```

## 3. Primeros pasos (una sola vez por computador)

1. Instalar **uv** (gestor de Python; descarga Python 3.12 solo), **Node.js 22 LTS**, **Docker Desktop**, **Git** y **Visual Studio Code** con la extensión de Claude Code.
   Luego, en una terminal: `uv python install 3.12` (así los hooks no tienen que descargar Python la primera vez y no se quedan sin tiempo).
2. Descomprimir esta carpeta donde vayan a trabajar y abrirla en VS Code.
3. En la terminal de VS Code, dentro de la carpeta:
   ```bash
   git init
   git add .
   git commit -m "chore: kit de arranque de Alas de Señas"
   ```
   (Los hooks usan git para saber qué cambió.)
   Crear también un repositorio **privado** en GitHub y subirlo (`git remote add origin …` y `git push -u origin main`): así se activa la integración continua.
4. Abrir Docker Desktop (debe quedar abierto mientras trabajan).
5. Abrir Claude Code y escribir:
   ```
   /fase 0
   ```
6. Leer el plan que propone, aceptar los permisos que pida y, al final, hacer la verificación manual que indique.

Después: `/estado` para ver el avance y `/fase 1`, `/fase 2`… en orden. **Una fase por sesión** es lo recomendable.

## 4. Lo que hace el equipo (no la IA)

- Conseguir a la persona que sepa LSC y, **en la primera semana**, llenar con ella `docs/validacion-interprete.md` (letras, cuáles tienen movimiento, CH/LL/RR, palabras). Luego pasar las respuestas a `content/signs.csv` (se crea en el Grupo 2).
- Grabar los videos con la guía de la §18 de `docs/especificacion.md` (si no se puede grabar video, usar fotos con el plan B de la §18.1), copiarlos a `content/videos/raw/` y ejecutar `uv run alas content all`. (Los videos originales no se suben a git: guárdenlos también en una carpeta compartida.)
- Hacer las verificaciones manuales de cada grupo y anotarlas en `docs/PROGRESS.md`.
- Grabar las muestras para la cámara en `/admin/dataset` (Grupo 10).
- Aprobar cualquier cambio a la especificación (la IA no puede editarla).
- El día de la sustentación: `uv run alas db seed-demo --reset` (deja lista la cuenta de demostración con fechas de ese día).

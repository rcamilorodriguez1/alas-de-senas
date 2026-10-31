# 🐦 Alas de Señas — Especificación técnica v3.3 (Python + React)

> **Versión 3.2 · reemplaza por completo a las versiones anteriores.** La 3.1 incorporó las correcciones de la revisión técnica del 30/10/2026 (`docs/DECISIONES.md`, D-002); la 3.2 agrega las 7 mejoras aprobadas por el equipo (D-003): alfabeto en dos nodos, letras con movimiento, usuario de demostración, integración continua, repaso evaluado por el servidor que cuenta para la racha, vidas y versiones de TensorFlow verificadas. La 3.3 agrega el **plan B de imágenes** cuando no se puedan grabar videos (D-004, §6.4.1).
> Cambio principal frente a la v2: **todo lo que no corre en el navegador está en Python** (API, reglas de negocio, base de datos, herramientas de contenido, entrenamiento del modelo y pruebas de extremo a extremo). **TypeScript queda solo en el frontend**, porque el navegador no ejecuta Python de forma práctica y la cámara debe procesarse en el dispositivo del usuario.
> Los mockups (`docs/mockups.md`) siguen siendo la referencia visual, pero **si contradicen este documento, manda este documento** (Tomi es SVG, no Lottie; las **vidas** ❤️ sí existen (§7.10) aunque no aparecen en los mockups: se muestran junto a la racha y el néctar en la barra superior y en el panel derecho; para no confundir dos significados con el mismo ícono, **los favoritos del diccionario usan ⭐ (`Star` de lucide-react) en lugar del ❤ de los mockups**; **las vistas móviles no se implementan**: esta entrega es solo para portátil y PC, §9.7; **no se implementan** el botón «Continuar con Google», el enlace «¿Olvidaste tu contraseña?» ni la página «Tienda»: el protector de racha se compra desde la tarjeta de racha del panel derecho). La captura de dos manos y rostro está en `docs/anexo-camara-holistica.md` (fase 10B).

### Lenguajes del proyecto

| Lenguaje | Dónde | Por qué no se reemplaza con Python |
|---|---|---|
| **Python 3.12** | API, dominio, acceso a datos, CLI de contenido, entrenamiento de modelos, pruebas (unitarias, API y E2E) | — |
| **TypeScript** | Solo `apps/web` (interfaz, reproductor, cámara en el navegador) | El navegador ejecuta JavaScript; MediaPipe y TensorFlow.js deben correr ahí para la privacidad y el tiempo real. |
| **SQL** (generado por SQLAlchemy) | PostgreSQL | Es el lenguaje de la base de datos; no se escribe SQL a mano salvo casos indicados. |
| HTML/CSS (Tailwind) | Interfaz | Lenguajes nativos del navegador. |

**Eliminado frente a la v2:** NestJS, Prisma, Zod en el servidor, Jest/Supertest, `packages/domain` y `packages/shared` en TypeScript, tsup, scripts Node de contenido (`csv-parse`, `yaml`, `ffmpeg-static`), entrenador del modelo en el navegador y Playwright en TypeScript.

> **Convención de comandos:** `alas <comando>` significa `uv run alas <comando>` ejecutado desde la raíz del repositorio (CLI hecha con Typer, §19.3).

---

## 0. Cómo usar este documento (léelo primero, agente)

Eres el equipo de ingeniería de este proyecto. Este documento es la **fuente de verdad**. Fue escrito para que el sistema funcione completo **antes** de tener los videos reales: cuando el equipo grabe las señas, solo tendrá que copiar los archivos en una carpeta y ejecutar un comando.

> **Harness:** el repositorio trae `CLAUDE.md` y la carpeta `.claude/` (permisos, hooks, comandos `/fase`, `/verificar`, `/estado`, `/decision`, `/riesgos` y subagentes). Los hooks hacen cumplir automáticamente varias de las reglas de abajo. Detalle: `docs/harness.md`. **No modifiques `.claude/` ni estos documentos** (están protegidos).

### 0.1 Reglas de oro (no negociables)

1. **Trabaja por fases (§16), en orden.** No empieces una fase si la anterior no cumple su *Definición de terminado*.
2. **Antes de escribir código de una fase**, vuelve a leer las secciones que esa fase cita y escribe un plan corto en `docs/PROGRESS.md`.
3. **Nunca marques una fase como terminada** si `alas check` falla. Nunca borres, saltes (`@pytest.mark.skip`, `.skip`) ni debilites una prueba para que pase: arregla el código.
4. **No cambies decisiones de este documento en silencio.** Si encuentras un problema real, documenta la alternativa en `docs/DECISIONES.md` (problema → opciones → decisión) y continúa con la opción más simple que respete la arquitectura.
5. **No agregues dependencias** fuera de §3 sin justificarlo en `docs/DECISIONES.md`.
6. **Verifica la versión instalada antes de usar una API** (`uv pip show <paquete>`, `apps/web/node_modules/<paquete>/package.json`) y usa la documentación de esa versión mayor. No mezcles APIs de versiones distintas (SQLAlchemy 1.x vs 2.0, Pydantic v1 vs v2, Tailwind v3 vs v4, `@mediapipe/hands` legado vs `@mediapipe/tasks-vision`).
7. **Tipado estricto**: Python con `mypy --strict` (prohibido `Any` explícito y `# type: ignore` sin código y justificación); TypeScript con `strict` (prohibido `any`, `@ts-ignore`, `as unknown as`).
8. **Toda regla de negocio vive en `apps/api/app/domain`** como funciones o clases puras de Python con pruebas, sin importar FastAPI ni SQLAlchemy. El frontend nunca las reimplementa: solo muestra lo que devuelve la API.
9. **Textos de interfaz en español de Colombia; código (nombres de variables, clases, archivos) en inglés.** Python sigue PEP 8 (`snake_case`); la API expone JSON en `camelCase` (alias de Pydantic).
10. **Si una instrucción es ambigua**, elige la interpretación más simple que cumpla los criterios de aceptación y anótala en `docs/DECISIONES.md`.

### 0.2 Protocolo por fase

```
1. Leer las secciones citadas por la fase.
2. Escribir plan breve en docs/PROGRESS.md (qué archivos, qué pruebas).
3. Escribir primero las pruebas de la lógica (cuando la fase tenga lógica).
4. Implementar.
5. Ejecutar: alas check  → debe pasar sin errores ni advertencias nuevas.
6. Ejecutar la verificación manual de la fase (§16) y anotar el resultado.
7. Actualizar docs/PROGRESS.md (hecho / pendiente / decisiones).
8. Commit con Conventional Commits:  feat(fase-N): ...
```

### 0.3 Definición de terminado (aplica a todas las fases)

- [ ] `alas check` pasa: `ruff check`, `ruff format --check`, `mypy --strict`, `pytest` (backend), ESLint + `tsc --noEmit` + Vitest (frontend) y verificación de que los tipos de la API generados están al día (§8.4).
- [ ] Los criterios de aceptación de la fase se verificaron a mano y están anotados.
- [ ] No quedan `print()` ni `console.log` de depuración ni código comentado.
- [ ] Los textos visibles están en español, sin errores de tildes (revisar `ñ`, `á`, `é`, `í`, `ó`, `ú`, `¿`, `¡`).
- [ ] Funciona en pantallas de portátil y PC: **1280×720, 1366×768 y 1920×1080**, en Chrome, Edge y Firefox (§9.7).
- [ ] `docs/PROGRESS.md` actualizado.

---

## 1. Visión y alcance

**Alas de Señas** es una plataforma web para aprender **Lengua de Señas Colombiana (LSC)** con una experiencia gamificada estilo Duolingo. Mascota: **Tomi, un colibrí**.

### 1.1 Alcance de esta entrega (MVP académico, < 1 mes)

| Incluido ✅ | Fuera de alcance ❌ (hoja de ruta) |
|---|---|
| Módulo introductorio sin cuenta + mini-quiz | Login con Google |
| Registro / login / cierre de sesión | Recuperación de contraseña por correo |
| **Módulos 1, 2 y 3 completos** (contenido real) | Contenido del Módulo 4 (se muestra como "Próximamente") |
| Ruta de nodos, 4 lecciones por nodo, desbloqueo | Tabla de clasificación entre usuarios |
| XP, rachas, néctar, protector de racha, logros, **vidas** (§7.10) | Accesorios de Tomi en la tienda |
| Progreso: historial, % avance, señas por repasar, resultados por unidad; **sesión de repaso evaluada por el servidor** que cuenta para la racha | Señas dinámicas (con movimiento) en la cámara |
| Diccionario: búsqueda, filtros, ficha, favoritos, enlace a lección | Panel web para editar contenido |
| Cámara (beta): alfabeto estático, colector de datos en el navegador y entrenamiento en Python | Notificaciones push / correo |
| Despliegue en un solo servicio · integración continua (GitHub Actions) · usuario de demostración | **Versión para celulares y tabletas** (diseño adaptable y app nativa) |
| **Solo portátil y PC** (navegador de escritorio, ancho ≥ 1024 px) | |

> El Módulo 4 existe en el currículo con `published: false`: se ve en la ruta con el sello "Próximamente" y nunca bloquea nada.

### 1.2 Flujo del usuario

```mermaid
flowchart LR
    A[Visitante] --> B[Intro: 6 señas<br/>sin cuenta]
    B --> C[Mini-quiz 3 preguntas]
    C --> D[Registro / Login]
    D --> E[Ruta de aprendizaje]
    E --> F[Lección: 4 actividades]
    F --> G[Celebración: XP, racha,<br/>néctar, logros]
    G --> E
    E --> H[Diccionario]
    E --> I[Cámara beta]
    E --> J[Progreso y repaso]
```

---

## 2. Decisiones de arquitectura (y el bug que cada una evita)

Estas decisiones son la razón por la que el sistema será estable. **No las reviertas.**

| # | Decisión | Por qué / qué bug evita |
|---|---|---|
| D1 | **Un solo origen en producción**: FastAPI sirve la SPA compilada y la API bajo `/api`. En desarrollo, Vite hace *proxy* de `/api` a `localhost:8000`. | Elimina CORS y el bloqueo de cookies de terceros (Safari/Chrome) que rompe el *refresh token* cuando front y back están en dominios distintos. |
| D2 | **El servidor evalúa todas las respuestas** mediante *sesiones de lección*. El cliente nunca recibe la respuesta correcta antes de contestar. | Evita trampas de XP y puntajes inventados por el cliente. |
| D3 | **El estado de desbloqueo se calcula, no se guarda.** Solo se guardan hechos (sesiones completadas y puntajes); una función pura deriva qué está bloqueado. | Evita inconsistencias al agregar contenido nuevo y lecciones "bloqueadas para siempre". |
| D4 | **IDs estables y legibles para el contenido** (`M1`, `M1-N2`, `M1-N2-L3`, slug `gracias`). La carga de contenido es *upsert* idempotente (`INSERT … ON CONFLICT DO UPDATE`). | Recargar el contenido no duplica datos ni borra el progreso. |
| D5 | **El contenido vive en archivos** (`content/`) y un validador estricto en Python los revisa antes de cargarlos. | Errores de contenido se detectan con un mensaje claro, no como pantallas rotas. |
| D6 | **Videos de relleno generados automáticamente**; los reales los reemplazan con el mismo nombre. | Toda la app funciona y se prueba sin videos reales. |
| D7 | **Videos como archivos estáticos** normalizados con ffmpeg (incluido vía `imageio-ffmpeg`: MP4 H.264, sin audio, `faststart`). | Sin servicios externos; compatibles con todos los navegadores; no hay que instalar ffmpeg a mano. |
| D8 | **Versión lenta con `playbackRate = 0.5`.** | No hay que grabar una segunda versión. |
| D9 | **Ejercicios generados automáticamente** con `random.Random(semilla)` determinista. | No se escriben preguntas a mano; IDs estables. |
| D10 | **Reglas de negocio en `app/domain`** (Python puro: `dataclasses`, `Protocol`, `Clock` inyectable). | Se prueban en milisegundos con `pytest`, incluidas las fechas límite de medianoche en Bogotá. |
| D11 | **Extracción de puntos de la cámara solo en el navegador; entrenamiento en Python.** El colector del navegador exporta los vectores ya normalizados (`dataset.json`) y Python (TensorFlow/Keras) entrena sobre esos números; el modelo se convierte a TensorFlow.js. | Python nunca recalcula los puntos, así que no hay discrepancia entre MediaPipe de Python y de JavaScript. |
| D12 | **Clase "NINGUNA"** en los modelos de la cámara. | Evita reconocer una letra cuando no hay ninguna seña. |
| D13 | **Las actividades de cámara y autoevaluación no suman puntaje.** | Lo que no se puede verificar en el servidor no infla el XP. |
| D14 | **Tomi es un SVG animado con Framer Motion.** | Sin archivos Lottie pendientes. |
| D15 | **Fuentes e íconos como paquetes** (`@fontsource`, `lucide-react`). | Sin dependencia de CDN durante la demo. |
| D16 | **Contrato de la API generado desde FastAPI**: los modelos Pydantic producen `openapi.json` y de ahí se generan los tipos TypeScript del frontend (`openapi-typescript`). | Una sola fuente de verdad para los contratos; `alas check` falla si los tipos quedan desactualizados. |
| D17 | **SQLAlchemy síncrono** (endpoints `def`, no `async def`). | Evita los errores típicos de SQLAlchemy asíncrono (cargas perezosas fuera del contexto, `MissingGreenlet`). FastAPI ejecuta los endpoints síncronos en un *pool* de hilos, suficiente para este proyecto. |
| D18 | **`uv`** para gestionar Python (versión, entorno virtual y *lockfile*). | Instalación reproducible y rápida en Windows, Mac y Linux. |
| D19 | **Videos procesados con nombre por contenido** (`/media/v/<hash>.mp4`) y un **manifiesto versionado** (`media/manifest.json`: slug → archivo, póster, si es de relleno, duración). Los videos procesados y el manifiesto **se suben a git**; los originales (`content/videos/raw/`) no. | Al reemplazar un video de relleno por el real, el navegador no muestra la versión vieja guardada en caché (el nombre cambia); el despliegue tiene los videos sin pasos extra; `alas db seed` sabe qué videos son de relleno sin depender de archivos locales ignorados; la URL del video no revela la palabra. |
| D20 | **Opciones opacas en los ejercicios**: el cliente nunca recibe IDs de seña en las opciones, sino *tokens* `HMAC(secreto, sesión:ejercicio:lado:seña)` de 10 caracteres. | Si las opciones usaran el ID (slug) de la seña, la respuesta correcta se vería directamente en el JSON (el ID del video coincidiría con el de una opción). |
| D21 | **El cierre de lección usa una sesión de base de datos propia en modo SERIALIZABLE**, distinta de la sesión de la petición. | En PostgreSQL el nivel de aislamiento solo se puede fijar antes de la primera consulta de la transacción; la sesión de la petición ya consultó al usuario. |
| D22 | **Los tiempos de negocio los fija el servicio con el `Clock` inyectado** (`started_at`, `answered_at`, `completed_at`, `unlocked_at`), no `server_default=func.now()`. | Con dos relojes (el de la BD y el de la app) la duración puede salir negativa y no se pueden probar la expiración de 24 h, las vidas ni el usuario de demostración con un reloj simulado. |
| D23 | **El repaso es una sesión evaluada por el servidor** (mismos evaluadores y tokens que las lecciones), no una lista de resultados que envía el cliente. | Como el repaso cuenta para la racha y devuelve vidas, si el cliente pudiera decir «acerté» se podría sumar racha sin practicar. |
| D24 | **Las vidas se calculan a partir de la fecha de la última actualización** (función pura), sin tareas programadas. | El plan gratuito de Render no garantiza procesos en segundo plano; un cálculo derivado nunca se desincroniza. |
| D25 | **Plan B de imágenes: una o varias fotos se convierten en un clip MP4** con el mismo formato que los videos. | El reproductor, los ejercicios, el diccionario, el manifiesto y las pruebas no cambian; una foto se reemplaza después por un video sin tocar código. |

---

## 3. Stack tecnológico (versiones fijadas)

| Área | Tecnología | Notas |
|---|---|---|
| Python | **Python 3.12** gestionado con **uv** | `.python-version` = `3.12`; `uv.lock` versionado. |
| API | **FastAPI** + **Uvicorn** | Endpoints síncronos (D17). Documentación automática en `/api/docs`. |
| Validación | **Pydantic v2** + **pydantic-settings** | Esquemas de entrada/salida con alias `camelCase`; configuración desde `.env`. |
| ORM y migraciones | **SQLAlchemy 2.0** (estilo `Mapped[]`) + **Alembic** | Driver **psycopg 3** (`psycopg[binary]`). |
| Base de datos | **PostgreSQL 16** | Docker en desarrollo; **Neon** en producción. Sin extensiones obligatorias. |
| Autenticación | **PyJWT** + **bcrypt** | `bcrypt` trae binarios para Windows (no compila). |
| Límite de peticiones | **slowapi** | 5/min en login y registro. |
| Zona horaria | `zoneinfo` + **tzdata** | `tzdata` es obligatorio: Windows no trae la base de zonas horarias. |
| CLI | **Typer** | Comando `alas` (§19.3). |
| Contenido | `csv` (stdlib, `utf-8-sig`), **PyYAML**, **imageio-ffmpeg**, **Pillow** | ffmpeg incluido como paquete de Python; Pillow dibuja las imágenes de los videos de relleno. |
| Pruebas backend | **pytest**, **pytest-cov**, `httpx`/`TestClient` de FastAPI | BD de prueba `alas_test`. |
| E2E | **Playwright para Python** (`pytest-playwright`) | Mismo lenguaje que el resto de pruebas. |
| Calidad Python | **ruff** (lint + formato) · **mypy --strict** | |
| Entrenamiento de modelos | **TensorFlow 2.15.1 (Keras 2)** + **tensorflowjs 4.22.0** + **numpy < 2** + **scikit-learn** + **setuptools < 81** en un entorno separado `ml/` (Python **3.11**; `ml/pyproject.toml` ya viene en el kit) | Versiones verificadas: instalación limpia, conversión y carga en TensorFlow.js con salidas idénticas (D-003). TF 2.15 porque el conversor falla con Keras 3; `setuptools` porque tensorflowjs lo importa y uv no lo instala. Alternativa sin instalar nada: Google Colab con el mismo cuaderno. |
| Frontend | **React + Vite + TypeScript** (npm) | Única parte en TypeScript. |
| Ruteo / datos | React Router · **TanStack Query** · **Zustand** (solo sesión y estado visual de la lección) | `retry` desactivado para 4xx. |
| Formularios | React Hook Form + **Zod** (solo en el cliente) | La validación definitiva siempre la hace el servidor (Pydantic). |
| Tipos de la API | **openapi-typescript** | Genera `apps/web/src/lib/api-types.ts` (D16). |
| Estilos | **Tailwind CSS** + componentes propios | Seguir la guía de la versión instalada. |
| Animación / gráficos | Framer Motion · canvas-confetti · Recharts | `prefers-reduced-motion`. |
| Íconos / fuentes | lucide-react · `@fontsource-variable/nunito` · `@fontsource-variable/inter` | |
| Cámara | **`@mediapipe/tasks-vision`** · **`@tensorflow/tfjs` 4.22.0** (versión exacta, igual a `tensorflowjs` de `ml/`) | Archivos de MediaPipe servidos desde `/public`; carga diferida. |
| Pruebas frontend | **Vitest** + Testing Library | |
| Despliegue | **Docker** (imagen multi-etapa) en **Render** + **Neon** | §17. |
| Integración continua | **GitHub Actions** (`.github/workflows/ci.yml`, ya incluido en el kit) | §15.1. |

---

## 4. Arquitectura en capas

```mermaid
flowchart TB
    subgraph P["1 · Presentación — apps/web (React + TypeScript)"]
        P1[Páginas y componentes]
        P2[TanStack Query · Zustand]
        P3[Cliente API con tipos generados · módulo de cámara]
    end
    subgraph A["2 · Aplicación — apps/api/app/api + services (FastAPI)"]
        A1[Routers + esquemas Pydantic + dependencias de seguridad]
        A2[Servicios = casos de uso]
    end
    subgraph D["3 · Dominio — apps/api/app/domain (Python puro)"]
        D1[Políticas: puntaje, XP, desbloqueo, racha, repaso, logros]
        D2[Generador de ejercicios · normalización de texto]
        D3[Protocolos de repositorio · Clock]
    end
    subgraph I["4 · Persistencia e infraestructura — apps/api/app/infra"]
        I1[Modelos SQLAlchemy + repositorios]
        I2[(PostgreSQL)]
        I3[Archivos estáticos: SPA, videos, modelos]
    end
    P -- "HTTP JSON /api + JWT" --> A
    A --> D
    I -. implementa .-> D3
    I1 --> I2
```

| Capa | Responsabilidad | Prohibido |
|---|---|---|
| Presentación | Mostrar, capturar interacción, cámara, llamar a la API. | Calcular XP, puntajes, rachas o desbloqueos. |
| Aplicación | Validar entrada (Pydantic), autenticar, orquestar casos de uso, transacciones. | SQL en los routers; reglas de negocio propias. |
| Dominio | Reglas de negocio puras y deterministas. | Importar `fastapi`, `sqlalchemy` o usar `datetime.now()` directo (usar `Clock`). Una prueba (`tests/test_architecture.py`) verifica con `ast` que `app/domain` no importa esos paquetes. |
| Persistencia | Acceso a BD y archivos. | Reglas de negocio. |

**Inyección de dependencias:** con `Depends()` de FastAPI. Los servicios reciben repositorios que cumplen `Protocol`s del dominio; en las pruebas se sustituyen por implementaciones en memoria.

### 4.1 Estructura del repositorio

```
alas-de-senas/
├── pyproject.toml                # workspace de uv (miembro: apps/api) + configuración de ruff/mypy
├── uv.lock · .python-version
├── CLAUDE.md                     # reglas para el agente (§19.1)
├── docs/                         # especificacion.md, anexo, specs/, PROGRESS.md, DECISIONES.md
├── content/                      # ← el equipo trabaja aquí (§6)
│   ├── curriculum.json · signs.csv · conversations.yaml · intro.json
│   └── videos/raw/
├── apps/
│   ├── api/                      # Python
│   │   ├── pyproject.toml        # dependencias y script `alas = "app.cli:app"`
│   │   ├── alembic.ini · alembic/versions/
│   │   ├── app/
│   │   │   ├── main.py           # crea FastAPI, monta /api y la SPA
│   │   │   ├── cli.py            # comandos `alas` (Typer)
│   │   │   ├── core/             # config (pydantic-settings), security, errors, clock
│   │   │   ├── api/              # routers: auth, curriculum, lessons, gamification, progress, reviews, dictionary, recognition, health
│   │   │   ├── schemas/          # modelos Pydantic de entrada/salida
│   │   │   ├── services/         # casos de uso
│   │   │   ├── domain/           # reglas puras (policies/, exercises/, content/, text.py, dates.py)
│   │   │   ├── infra/            # db.py, models.py (SQLAlchemy), repositories/
│   │   │   └── content/          # pipeline de contenido (csv, validación, videos, seed)
│   │   └── tests/                # unit/, api/, e2e/, test_architecture.py
│   └── web/                      # React + TypeScript (npm)
│       ├── public/media/v/ · public/media/p/ · public/media/manifest.json   # generados, versionados (D19)
│       ├── public/mediapipe/ · public/models/
│       └── src/ (app, pages, components, features, lib/api-types.ts, camera/)
├── ml/                           # entorno Python separado (TensorFlow 2.15.1, Python 3.11)
│   ├── pyproject.toml · smoke_tfjs.py   # ya vienen en el kit (versiones verificadas)
│   ├── fixtures/tfjs-smoke/      # modelos de prueba convertidos + salida esperada (prueba de compatibilidad)
│   ├── train_static.py · train_sequence.py · evaluate.py · export_tfjs.py
│   ├── notebooks/entrenamiento.ipynb   # mismo flujo para Google Colab
│   └── data/                     # dataset.json exportados del navegador (ignorado en git)
├── docker-compose.yml            # PostgreSQL 16 en el puerto 5433
├── docker/init-test-db.sql       # crea la base alas_test al iniciar el contenedor
├── .github/workflows/ci.yml      # integración continua (ya incluido en el kit)
└── Dockerfile                    # multi-etapa: Node compila la SPA → imagen Python final
```

---

## 5. Modelo de datos (`apps/api/app/infra/models.py`, SQLAlchemy 2.0)

Principios: **IDs de contenido estables**, **guardar hechos y derivar estados**, `order_by` explícito en toda consulta que dependa del orden, tiempos en UTC (`DateTime(timezone=True)`) y días de negocio como texto `YYYY-MM-DD` en hora de Bogotá.

```python
from __future__ import annotations
import enum, uuid
from datetime import datetime
from sqlalchemy import (Boolean, DateTime, Enum, ForeignKey, Index, Integer, String, Text,
                        UniqueConstraint, func)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class Role(enum.StrEnum): LEARNER = "LEARNER"; ADMIN = "ADMIN"
class LessonType(enum.StrEnum): LEARN = "LEARN"; RECOGNIZE = "RECOGNIZE"; PRACTICE = "PRACTICE"; CHALLENGE = "CHALLENGE"
class NodeKind(enum.StrEnum): STANDARD = "STANDARD"; ALPHABET = "ALPHABET"; NUMBERS = "NUMBERS"
class ActivityKind(enum.StrEnum): OBSERVE = "OBSERVE"; SELECT = "SELECT"; PRODUCE = "PRODUCE"; USE = "USE"
class ExerciseType(enum.StrEnum):
    OBSERVE = "OBSERVE"; VIDEO_TO_MEANING = "VIDEO_TO_MEANING"; MEANING_TO_VIDEO = "MEANING_TO_VIDEO"
    MEMORY_MATCH = "MEMORY_MATCH"; PRODUCE = "PRODUCE"; CONVERSATION = "CONVERSATION"; SPELLING = "SPELLING"


# ---------- Contenido (cargado desde content/, IDs estables) ----------
class Module(Base):
    __tablename__ = "modules"
    id: Mapped[str] = mapped_column(String(8), primary_key=True)            # "M1"
    order: Mapped[int] = mapped_column(Integer, unique=True)
    title: Mapped[str] = mapped_column(String(120))
    description: Mapped[str] = mapped_column(Text)
    published: Mapped[bool] = mapped_column(Boolean, default=True)

class Node(Base):
    __tablename__ = "nodes"
    __table_args__ = (UniqueConstraint("module_id", "order"),)
    id: Mapped[str] = mapped_column(String(16), primary_key=True)           # "M1-N2"
    module_id: Mapped[str] = mapped_column(ForeignKey("modules.id"))
    order: Mapped[int]
    title: Mapped[str] = mapped_column(String(120))
    kind: Mapped[NodeKind] = mapped_column(Enum(NodeKind, name="node_kind"), default=NodeKind.STANDARD)

class Lesson(Base):
    __tablename__ = "lessons"
    __table_args__ = (UniqueConstraint("node_id", "order"),)
    id: Mapped[str] = mapped_column(String(24), primary_key=True)           # "M1-N2-L3"
    node_id: Mapped[str] = mapped_column(ForeignKey("nodes.id"))
    order: Mapped[int]                                                       # 1..4
    type: Mapped[LessonType] = mapped_column(Enum(LessonType, name="lesson_type"))
    title: Mapped[str] = mapped_column(String(120))

class Category(Base):
    __tablename__ = "categories"
    id: Mapped[str] = mapped_column(String(32), primary_key=True)           # "saludos"
    name: Mapped[str] = mapped_column(String(64))
    order: Mapped[int]

class Sign(Base):
    __tablename__ = "signs"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)           # slug
    word: Mapped[str] = mapped_column(String(120))
    normalized_word: Mapped[str] = mapped_column(String(120), index=True)   # §7.8
    meaning: Mapped[str] = mapped_column(Text)
    how_to: Mapped[str | None] = mapped_column(Text)
    usage_example: Mapped[str] = mapped_column(Text)
    category_id: Mapped[str] = mapped_column(ForeignKey("categories.id"), index=True)
    node_id: Mapped[str | None] = mapped_column(ForeignKey("nodes.id"))
    introduced_in_lesson_id: Mapped[str | None] = mapped_column(ForeignKey("lessons.id"))
    order: Mapped[int] = mapped_column(default=0)
    motion: Mapped[str | None] = mapped_column(String(8))                   # solo letras: "static" | "dynamic" (§6.2)
    video_path: Mapped[str] = mapped_column(String(255))                    # "/media/v/3f9a1c0b7e21d4aa.mp4" (D19)
    poster_path: Mapped[str] = mapped_column(String(255))
    is_placeholder: Mapped[bool] = mapped_column(default=True)
    media_source: Mapped[str] = mapped_column(String(12), default="placeholder")  # "video" | "images" | "placeholder" (D25)

class Exercise(Base):
    __tablename__ = "exercises"
    __table_args__ = (UniqueConstraint("lesson_id", "order"),)
    id: Mapped[str] = mapped_column(String(32), primary_key=True)           # "M1-N2-L2-04"
    lesson_id: Mapped[str] = mapped_column(ForeignKey("lessons.id", ondelete="CASCADE"))
    order: Mapped[int]
    activity: Mapped[ActivityKind] = mapped_column(Enum(ActivityKind, name="activity_kind"))
    type: Mapped[ExerciseType] = mapped_column(Enum(ExerciseType, name="exercise_type"))
    sign_id: Mapped[str | None] = mapped_column(ForeignKey("signs.id"))
    scored: Mapped[bool]
    payload: Mapped[dict[str, object]] = mapped_column(JSONB)               # validado con Pydantic (§7.6)


# ---------- Usuarios y sesión ----------
class User(Base):
    __tablename__ = "users"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(80))
    email: Mapped[str] = mapped_column(String(254), unique=True)            # minúsculas y sin espacios
    password_hash: Mapped[str] = mapped_column(String(100))
    role: Mapped[Role] = mapped_column(Enum(Role, name="role"), default=Role.LEARNER)
    daily_goal_minutes: Mapped[int] = mapped_column(default=10)
    dominant_hand: Mapped[str] = mapped_column(String(5), default="right")  # para el Anexo A
    total_xp: Mapped[int] = mapped_column(default=0)
    nectar: Mapped[int] = mapped_column(default=0)
    recognitions_correct: Mapped[int] = mapped_column(default=0)
    hearts: Mapped[int] = mapped_column(default=5)                          # vidas guardadas (§7.10)
    hearts_updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    is_demo: Mapped[bool] = mapped_column(default=False)                    # usuario de demostración (§17.4)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

class RefreshToken(Base):
    __tablename__ = "refresh_tokens"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)        # SHA-256, nunca el token
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


# ---------- Aprendizaje (hechos) ----------
class LessonSession(Base):
    __tablename__ = "lesson_sessions"
    __table_args__ = (Index("ix_sessions_user_lesson", "user_id", "lesson_id"),
                      Index("ix_sessions_user_completed", "user_id", "completed_at"))
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    lesson_id: Mapped[str] = mapped_column(ForeignKey("lessons.id"))
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))  # lo fija el servicio con Clock (D22)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    hearts_lost: Mapped[int] = mapped_column(default=0)
    score: Mapped[int | None]; correct: Mapped[int | None]; total: Mapped[int | None]
    passed: Mapped[bool | None]; xp_earned: Mapped[int | None]; nectar_earned: Mapped[int | None]
    duration_sec: Mapped[int | None]

class SessionAnswer(Base):
    __tablename__ = "session_answers"                                       # PK compuesta: cuenta el PRIMER intento
    session_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("lesson_sessions.id", ondelete="CASCADE"), primary_key=True)
    exercise_id: Mapped[str] = mapped_column(ForeignKey("exercises.id", ondelete="CASCADE"), primary_key=True)
    answer: Mapped[dict[str, object]] = mapped_column(JSONB)
    correct: Mapped[bool]
    answered_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))  # Clock (D22)

class ReviewSession(Base):                                                  # D23, §8.5
    __tablename__ = "review_sessions"
    __table_args__ = (Index("ix_review_sessions_user", "user_id", "started_at"),)
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    items: Mapped[list[dict[str, object]]] = mapped_column(JSONB)           # ejercicios con respuesta (solo servidor)
    correct: Mapped[int | None]; total: Mapped[int | None]; hearts_gained: Mapped[int | None]

class ReviewAnswer(Base):
    __tablename__ = "review_answers"                                        # PK compuesta: primer intento
    session_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("review_sessions.id", ondelete="CASCADE"), primary_key=True)
    item_id: Mapped[str] = mapped_column(String(8), primary_key=True)      # "R-01"
    answer: Mapped[dict[str, object]] = mapped_column(JSONB)
    correct: Mapped[bool]
    answered_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))

class DailyActivity(Base):
    __tablename__ = "daily_activity"
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    day: Mapped[str] = mapped_column(String(10), primary_key=True)          # "2026-11-03" (Bogotá)
    seconds: Mapped[int] = mapped_column(default=0)
    xp: Mapped[int] = mapped_column(default=0)
    lessons: Mapped[int] = mapped_column(default=0)
    reviews: Mapped[int] = mapped_column(default=0)

class Streak(Base):
    __tablename__ = "streaks"
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    current: Mapped[int] = mapped_column(default=0)
    longest: Mapped[int] = mapped_column(default=0)
    last_active_day: Mapped[str | None] = mapped_column(String(10))
    freezes_available: Mapped[int] = mapped_column(default=0)

class SignReview(Base):
    __tablename__ = "sign_reviews"
    __table_args__ = (Index("ix_reviews_user_next", "user_id", "next_review_day"),)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    sign_id: Mapped[str] = mapped_column(ForeignKey("signs.id"), primary_key=True)
    strength: Mapped[int] = mapped_column(default=0)                        # 0..5
    next_review_day: Mapped[str] = mapped_column(String(10))
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))

class Achievement(Base):
    __tablename__ = "achievements"
    id: Mapped[str] = mapped_column(String(32), primary_key=True)           # "FIRST_FLAP"
    title: Mapped[str] = mapped_column(String(80)); description: Mapped[str] = mapped_column(Text)
    icon: Mapped[str] = mapped_column(String(40)); nectar_reward: Mapped[int]; order: Mapped[int]

class UserAchievement(Base):
    __tablename__ = "user_achievements"                                     # PK compuesta: imposible duplicar
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    achievement_id: Mapped[str] = mapped_column(ForeignKey("achievements.id"), primary_key=True)
    unlocked_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))  # Clock (D22)

class Favorite(Base):
    __tablename__ = "favorites"
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    sign_id: Mapped[str] = mapped_column(ForeignKey("signs.id"), primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
```

Notas para el agente:
- `order` es palabra reservada de SQL: SQLAlchemy la cita automáticamente; no escribir SQL crudo con esa columna.
- Las migraciones se generan con `alembic revision --autogenerate` y **se revisan a mano** antes de aplicarlas (Alembic no detecta todo, por ejemplo cambios de `Enum`).
- `SessionAnswer` y `Exercise` usan `ondelete="CASCADE"` para que regenerar ejercicios no deje respuestas huérfanas.
- Los módulos con `published = false` se cargan con sus nodos (para mostrarlos como «Próximamente») pero **sin lecciones ni ejercicios**.
- **D22:** ningún tiempo de negocio usa `server_default=func.now()`; el servicio pasa `clock.now()`. Solo `created_at` (auditoría) usa la hora de la BD.

---

## 6. Contenido: currículo, señas y videos

> **Objetivo de esta sección:** que el contenido sea un trabajo de llenar una hoja de cálculo y copiar videos, nada más.

### 6.1 `content/curriculum.json`

```json
{
  "modules": [
    { "id": "M1", "order": 1, "title": "Fundamentos de la LSC", "description": "Saludos, cortesía, presentaciones y alfabeto manual.", "published": true,
      "nodes": [
        { "id": "M1-N1", "order": 1, "title": "Saludos y cortesía", "kind": "STANDARD" },
        { "id": "M1-N2", "order": 2, "title": "Presentaciones", "kind": "STANDARD" },
        { "id": "M1-N3", "order": 3, "title": "Alfabeto A–M", "kind": "ALPHABET" },
        { "id": "M1-N4", "order": 4, "title": "Alfabeto N–Z", "kind": "ALPHABET" } ] },
    { "id": "M2", "order": 2, "title": "Personas y vida cotidiana", "description": "Familia, emociones, números y actividades diarias.", "published": true,
      "nodes": [
        { "id": "M2-N1", "order": 1, "title": "Familia", "kind": "STANDARD" },
        { "id": "M2-N2", "order": 2, "title": "Emociones", "kind": "STANDARD" },
        { "id": "M2-N3", "order": 3, "title": "Números", "kind": "NUMBERS" },
        { "id": "M2-N4", "order": 4, "title": "Actividades diarias", "kind": "STANDARD" } ] },
    { "id": "M3", "order": 3, "title": "Entorno y necesidades", "description": "Alimentos, lugares, transporte, objetos y necesidades básicas.", "published": true,
      "nodes": [
        { "id": "M3-N1", "order": 1, "title": "Alimentos", "kind": "STANDARD" },
        { "id": "M3-N2", "order": 2, "title": "Lugares", "kind": "STANDARD" },
        { "id": "M3-N3", "order": 3, "title": "Transporte y objetos", "kind": "STANDARD" },
        { "id": "M3-N4", "order": 4, "title": "Necesidades básicas", "kind": "STANDARD" } ] },
    { "id": "M4", "order": 4, "title": "Primeras conversaciones", "description": "Preguntas frecuentes, ubicación, actividades y diálogos.", "published": false,
      "nodes": [
        { "id": "M4-N1", "order": 1, "title": "Preguntas frecuentes", "kind": "STANDARD" },
        { "id": "M4-N2", "order": 2, "title": "Ubicación", "kind": "STANDARD" },
        { "id": "M4-N3", "order": 3, "title": "Actividades y diálogos", "kind": "STANDARD" },
        { "id": "M4-N4", "order": 4, "title": "Comprensión visual", "kind": "STANDARD" } ] }
  ]
}
```

Las 4 lecciones de cada nodo **no se escriben**: se generan (`<nodo>-L1` Aprende, `-L2` Reconoce, `-L3` Practica, `-L4` Reto final).

> **Por qué el alfabeto está en dos nodos (v3.2):** con un solo nodo de 27 letras, la lección 1 tenía unos 36 ejercicios (más de 20 minutos). En dos nodos cada lección tiene 4–5 letras (≈ 20 ejercicios) y se conserva la estructura 4 módulos × 4 nodos × 4 lecciones. Para que M1 siga teniendo 4 nodos, «Saludos» y «Cortesía» se unieron (§6.2).

### 6.2 `content/signs.csv` (prellenado — el agente lo crea con estas filas)

Columnas: `slug,word,meaning,how_to,usage_example,category,node,order,motion`
- `slug`: minúsculas, sin tildes, guiones (`buenos-dias`, `letra-n-tilde`). Es el nombre del archivo de video.
- `how_to`: **vacío** hasta que el intérprete lo describa (la app muestra "Descripción en revisión").
- `node`: vacío = seña solo de diccionario.
- `motion` (**solo letras**, obligatorio en ellas y vacío en las demás): `static` (la mano queda quieta; la cámara del alfabeto puede reconocerla) o `dynamic` (lleva movimiento; en «Produce la seña» se usa autoevaluación). Propuesta inicial, **a confirmar con el intérprete** (`docs/validacion-interprete.md`): `dynamic` para J, Ñ y Z; `static` para las demás.
- `meaning` y `usage_example`: el agente los redacta en español claro (1 frase cada uno).

> ⚠️ **La lista de palabras es una propuesta.** El equipo debe confirmarla con el intérprete: puede reemplazar palabras, pero debe respetar las reglas de §6.6.

| Nodo | Señas (slug → palabra) |
|---|---|
| M1-N1 Saludos y cortesía (9) | `hola` Hola · `buenos-dias` Buenos días · `buenas-tardes` Buenas tardes · `buenas-noches` Buenas noches · `como-estas` ¿Cómo estás? · `adios` Adiós · `gracias` Gracias · `por-favor` Por favor · `de-nada` De nada |
| M1-N2 Presentaciones (9) | `nombre` Nombre · `yo` Yo · `tu` Tú · `mucho-gusto` Mucho gusto · `sordo` Sordo · `oyente` Oyente · `si` Sí · `no` No · `perdon` Perdón |
| M1-N3 Alfabeto A–M (13) | `letra-a` … `letra-m` — orden alfabético |
| M1-N4 Alfabeto N–Z (14) | `letra-n`, `letra-n-tilde` (Ñ), `letra-o` … `letra-z` — orden alfabético |
| M2-N1 Familia (7) | `familia` · `mama` Mamá · `papa` Papá · `hermano` · `hermana` · `hijo` · `abuelo` |
| M2-N2 Emociones (6) | `feliz` · `triste` · `enojado` · `cansado` · `miedo` · `amor` |
| M2-N3 Números (10) | `numero-1` Uno … `numero-10` Diez |
| M2-N4 Actividades (7) | `comer` · `beber` · `dormir` · `trabajar` · `estudiar` · `jugar` · `banarse` Bañarse |
| M3-N1 Alimentos (7) | `agua` · `pan` · `arroz` · `fruta` · `carne` · `cafe` Café · `leche` |
| M3-N2 Lugares (7) | `casa` · `colegio` · `universidad` · `hospital` · `tienda` · `parque` · `bano` Baño |
| M3-N3 Transporte y objetos (7) | `bus` · `carro` · `moto` · `bicicleta` · `celular` · `dinero` · `computador` |
| M3-N4 Necesidades (6) | `ayuda` · `hambre` · `sed` · `dolor` · `medico` Médico · `emergencia` |
| Solo diccionario (7) | `con-permiso` Con permiso (categoría `cortesia`) · `perro` · `gato` · `pajaro` Pájaro · `vaca` · `caballo` · `pez` (categoría `animales`) |

**Total: 109 clips** (82 palabras + 27 letras). Las letras son rápidas de grabar.

> **Dígrafos (CH, LL, RR):** si el intérprete confirma que el alfabeto LSC que van a enseñar los incluye, se agregan como `letra-ch`, `letra-ll`, `letra-rr` justo después de C, L y R (CH y LL en M1-N3, RR en M1-N4). El reparto por lección (§6.7) y el deletreo (§6.5) ya los soportan sin cambiar código.

Categorías (`content` las crea con este orden): `saludos` Saludos · `presentaciones` Presentaciones · `cortesia` Cortesía · `alfabeto` Alfabeto · `familia` Familia · `emociones` Emociones · `numeros` Números · `actividades` Actividades · `alimentos` Alimentos · `lugares` Lugares · `transporte` Transporte y objetos · `necesidades` Necesidades · `animales` Animales.

### 6.3 `content/intro.json`

```json
{ "cards": ["hola", "gracias", "por-favor", "si", "no", "adios"],
  "quiz": [ { "sign": "gracias" }, { "sign": "hola" }, { "sign": "no" } ] }
```
El intro **reutiliza los videos** de esas señas (en bucle, sin controles). No hay imágenes ni GIF aparte.

### 6.4 Flujo de videos (lo único que hará el equipo)

```mermaid
flowchart LR
    A[Grabar seña] --> B[Nombrar slug.mp4<br/>ej. gracias.mp4]
    B --> C[Copiar a<br/>content/videos/raw/]
    C --> D[alas content videos]
    D --> E[apps/web/public/media/<br/>v/ · p/ · manifest.json]
    E --> F[alas content check]
    F --> G[alas db seed]
    G --> H[✅ Video real en la app]
    A2[Plan B: tomar 1–3 fotos] --> B2[Nombrar slug.jpg o<br/>slug__1.jpg, slug__2.jpg]
    B2 --> C
```

**Comandos (código en `apps/api/app/content/`, con pruebas en `tests/unit/content/`):**

| Comando | Qué hace |
|---|---|
| `alas content placeholders` | Para cada seña **sin** video en `raw/`, genera un video de 3 s (fondo `#0E2A2F`, palabra en blanco centrada, texto "Video en preparación") y su póster. La imagen se dibuja con **Pillow** (fuente incluida en el repositorio, `content/fonts/`) y ffmpeg la convierte en video en bucle: **no usar el filtro `drawtext`**, que depende de fuentes del sistema y falla en Windows. Nunca reemplaza un video real. Escribe el archivo con nombre por contenido (D19) y lo registra en el manifiesto con `placeholder: true`. |
| `alas content videos` | Para cada archivo en `raw/` (videos `.mp4 .mov .webm .m4v` o imágenes `.jpg .jpeg .png .webp` — plan B, §6.4.1 —, cualquier mayúscula/minúscula): valida que el nombre coincide con un slug del CSV (si no, error con sugerencia del slug más parecido), lo normaliza con ffmpeg (ruta obtenida con `imageio_ffmpeg.get_ffmpeg_exe()`, ejecutado con `subprocess.run([...], check=True)` sin `shell=True`) y genera el póster del segundo 1. Guarda el resultado como `media/v/<hash>.mp4` y `media/p/<hash>.jpg` (`hash` = primeros 16 caracteres del SHA-256 del video procesado), actualiza `media/manifest.json` (`placeholder: false`, `source: "video"` o `"images"`, duración) y borra los archivos que ya no referencia el manifiesto. Procesa solo los originales que cambiaron (caché local `content/videos/.cache.json`, ignorada en git). |
| `alas content check` | Valida todo el contenido (§6.6) e imprime un **reporte**: señas con video real / de relleno por módulo, señas sin `how_to`, errores. Sale con código 1 si hay errores. |
| `alas db seed` | Ejecuta `alas content check --skip-raw`; si pasa, hace *upsert* de categorías, módulos, nodos, lecciones, señas, ejercicios y logros. Toma `video_path`, `poster_path`, `is_placeholder` y `media_source` del **manifiesto** (`MEDIA_DIR/manifest.json`), nunca de la carpeta `raw/`, para funcionar igual en producción. Idempotente. |
| `alas content all` | `placeholders` → `videos` → `check` → `seed`. |

**Comando ffmpeg de normalización** (dentro del script):
```
ffmpeg -y -i <entrada> -an -vf "scale=-2:720:flags=lanczos,fps=30,format=yuv420p"
  -c:v libx264 -profile:v high -preset veryfast -crf 23 -movflags +faststart <salida>.mp4
ffmpeg -y -ss 1 -i <salida>.mp4 -frames:v 1 -q:v 4 <poster>.jpg
```
- `-an` quita el audio (la LSC no lo necesita; evita bloqueos de reproducción automática).
- `yuv420p` + H.264 = compatible con todos los navegadores (incluido Safari).
- `+faststart` = el video empieza a reproducirse antes de descargarse completo.
- Si el video dura más de 8 s, el script advierte (los clips deben ser cortos).
- **Git:** se versionan `apps/web/public/media/**` (≈ 109 clips de 2–4 s a 720p, del orden de 30–60 MB) y el manifiesto; `content/videos/raw/` está ignorado (los originales se guardan en una carpeta compartida del equipo).
- `alas content check` sin opciones revisa también `raw/`; con `--skip-raw` (producción, CI) solo valida el contenido y el manifiesto.

### 6.4.1 Plan B: señas con imágenes en lugar de video (D25)

Si por razones externas no se puede grabar video, el equipo puede usar **fotos** (de una persona que sepa LSC). `alas content videos` las convierte en un clip corto con el mismo formato que los videos (720p, H.264 `yuv420p`, sin audio, `+faststart`), así que **el resto del sistema no cambia**. Se pueden mezclar: unas señas con video y otras con imágenes; para pasar después a video, basta con copiar el video y borrar las imágenes de esa seña.

**Nombres de archivo** (en `content/videos/raw/`):
- Una imagen: `<slug>.jpg` → `letra-a.jpg`, `numero-1.jpg`. Para posturas quietas (letras estáticas, números).
- Secuencia de 2 a 4 imágenes: `<slug>__<n>.jpg` (**dos guiones bajos**) → `gracias__1.jpg`, `gracias__2.jpg`. Para señas con movimiento: inicio → (intermedio) → final.
- Se usan dos guiones bajos porque los slugs pueden terminar en número (`numero-1`): `numero-1.jpg` es la seña «uno» con una sola imagen, nunca el cuadro 1 de una seña «numero». Los slugs no pueden contener `_` (§6.6), así que no hay ambigüedad.

**Conversión** (`apps/api/app/content/images.py`, Pillow + ffmpeg de `imageio-ffmpeg`, prototipo verificado el 30/10/2026):
1. Abrir con Pillow y aplicar `ImageOps.exif_transpose` (las fotos de celular traen la rotación en los metadatos; sin esto salen de lado).
2. Convertir a RGB y reducir con `thumbnail((1280, 720))` **antes** de procesar (una foto de 12 MP ocupa ~36 MB en memoria por cuadro).
3. Centrar sobre un lienzo fijo de 1280×720 con fondo `#F5FAF7` (así las medidas siempre son pares, como exige `yuv420p`).
4. Generar los cuadros a 30 fps en una carpeta temporal: una imagen = 3 s fija; secuencia = cada imagen 1,2 s con fundido de 0,4 s (`Image.blend`) entre una y otra.
5. `ffmpeg -framerate 30 -i %05d.png -vf format=yuv420p -c:v libx264 -profile:v high -preset veryfast -crf 23 -movflags +faststart -an` (con `subprocess.run([...], check=True)`, sin `shell=True`). Póster = primera imagen.
6. Mismo nombre por contenido, manifiesto (`source: "images"`, `frames: n`) y caché que los videos (la caché usa el SHA-256 de todas las imágenes de la seña).

**Reglas** (las verifica `alas content check`, cada una con prueba):
- Si una seña tiene video **e** imágenes → se usa el video y se advierte.
- Secuencias numeradas desde 1, sin huecos, máximo 4 (`gracias__1.jpg` y `gracias__3.jpg` sin `__2` → error).
- `.heic` (iPhone) no es compatible → error: «Exporta la foto como JPG (en el iPhone: Ajustes → Cámara → Formatos → Más compatible)».
- Imagen de menos de 480 px de alto → advertencia (se verá borrosa).
- Seña con imágenes y `how_to` vacío → **advertencia destacada**: sin movimiento visible, la descripción escrita es la que explica cómo se hace.

**En la interfaz:** si `mediaSource = "images"`, el reproductor muestra la etiqueta «Secuencia de imágenes» y oculta el botón de velocidad lenta (no aporta nada); repetir y pausar siguen igual. La ficha del diccionario muestra `how_to` de forma más visible.

**Derechos de autor:** las imágenes deben ser **propias** (tomadas por el equipo). Si se usa material de terceros (por ejemplo, de un diccionario de LSC), se necesita permiso escrito y la fuente se cita en `content/creditos.md` y en la página `/creditos`. `alas content check` no lo puede verificar: es responsabilidad del equipo.

### 6.5 `content/conversations.yaml`

Conversaciones de 2–3 turnos construidas **solo con señas ya grabadas**. Cada turno: la "Persona A" muestra un clip y el usuario elige la respuesta correcta entre 3 clips.

```yaml
M1-N1:
  - turns:
      - prompt: hola
        answer: hola
        distractors: [adios, buenas-noches]
      - prompt: como-estas
        answer: buenos-dias      # reemplazar por la respuesta que indique el intérprete
        distractors: [adios, buenas-noches]
```

Reglas (las verifica `alas content check`):
- Cada nodo STANDARD o NUMBERS necesita **al menos 2 conversaciones**, y al menos **una de 3 turnos** (para el Reto final).
- Todas las señas usadas deben pertenecer a ese nodo o a nodos anteriores.
- La conversación de **L2** solo puede usar señas introducidas en L1–L2 del nodo o en nodos anteriores; si no existe ninguna así, error: `M1-N2 necesita una conversación que use solo señas de L1–L2 o de nodos anteriores.`
- El generador elige siempre la primera conversación válida para cada lección (determinista). El agente redacta las conversaciones con lógica comunicativa sencilla (saludo → saludo; pregunta → respuesta) y las marca para revisión del intérprete con un comentario `# revisar`. Los nodos **ALPHABET no usan conversaciones**: su actividad 4 es un ejercicio de **deletreo** (`SPELLING`, §7.6), definido así:

```yaml
M1-N3:
  spelling: [CADA, BEBE, HADA, FE, DEBE, DIGA, CAMA, LIMA, MALA, DAME]     # L2 solo puede usar A–I
M1-N4:
  spelling: [SOL, LUNA, NIDO, OSO, PAN, NIÑO, SAPO, VASO, TAXI, ZAPATO]  # pueden usar las letras de M1-N3
```

Se muestran en orden los clips de las letras de la palabra y el usuario elige la palabra escrita entre 4 opciones (las otras 3 se toman de la misma lista). Las palabras van sin tildes; la Ñ se escribe `Ñ` y usa `letra-n-tilde`. **Separación en letras:** coincidencia más larga primero con las letras que existen en el CSV (si existe `letra-ll`, «LLAVE» = LL·A·V·E; si no, L·L·A·V·E). Cada palabra solo puede usar letras ya enseñadas **en esa lección o antes** (incluidos los nodos anteriores), según el reparto real de §6.7; `alas content check` lo verifica. Mínimo 6 palabras por nodo ALPHABET y al menos 4 válidas para su L2.

### 6.6 Validaciones del contenido (`alas content check`) — cada una con prueba

| Regla | Mensaje de error (ejemplo) |
|---|---|
| CSV leído con `encoding="utf-8-sig"` (elimina el BOM) y `csv.DictReader`; si aparece `Ã`, `Â` o `�` → error | `signs.csv parece guardado con codificación incorrecta (se ve "Ã¡"). Guárdalo como "CSV UTF-8" o expórtalo desde Google Sheets.` |
| `slug` único, formato `^[a-z0-9]+(-[a-z0-9]+)*$` (sin `_`: el doble guion bajo marca los cuadros del plan B) | `Slug repetido: "gracias" (filas 12 y 40).` |
| `category` existe | `Categoría "saludo" no existe. ¿Quisiste decir "saludos"?` |
| `node` existe en `curriculum.json` | |
| Nodo STANDARD: 5–9 señas · NUMBERS: 5–10 · ALPHABET: 12–16 | `M1-N2 tiene 4 señas; mínimo 5.` |
| Letras (`category = alfabeto`): `motion` es `static` o `dynamic`; en las demás señas, vacío | `letra-j: falta la columna motion (static o dynamic).` |
| Si existe `public/models/lsc-alfabeto/labels.json`: ninguna etiqueta es una letra `dynamic` y todas existen como slug | `El modelo del alfabeto incluye letra-z, que tiene movimiento: el modelo estático no puede reconocerla.` |
| Módulos publicados: los 4 nodos tienen señas | |
| `order` único dentro del nodo | |
| `word`, `meaning`, `usage_example` no vacíos | |
| Conversaciones: slugs existen y ya fueron aprendidos en ese nodo o antes | |
| Cada lección generada tiene **≥ 4 ejercicios con puntaje** (con menos, un solo error reprueba la lección) | `M1-N1-L1 tiene 2 ejercicios con puntaje; mínimo 4.` |
| Los módulos con `published = false` no generan lecciones (sus nodos pueden no tener señas) | |
| Palabras de deletreo: solo letras aprendidas hasta esa lección (según el reparto de §6.7) | `«LUZ» usa la letra Z, que aún no se ha enseñado en M1-N4-L2.` |
| `media/manifest.json` tiene una entrada para cada seña y cada archivo existe | `Falta el video de «gracias». Ejecuta alas content all.` |
| Cada video en `raw/` corresponde a un slug | `raw/Gracia.mp4 no corresponde a ninguna seña. ¿Quisiste decir "gracias"?` |
| Imágenes del plan B: nombre válido, secuencia sin huecos (máx. 4), sin `.heic`, video e imágenes a la vez → advertencia (§6.4.1) | `Faltan imágenes en la secuencia de «gracias»: hay __1 y __3, falta __2.` |
| Advertencias (no fallan): `how_to` vacío, video de relleno, video > 8 s | Se listan en el reporte. |

### 6.7 Generador de ejercicios (`apps/api/app/domain/content/generator.py`)

Función **pura y determinista**: `generate_exercises(curriculum, signs, conversations) -> list[ExerciseSpec]`. Usa `random.Random(f"alas:{lesson_id}")` (semilla de texto, estable entre ejecuciones; **nunca `hash()`**); misma entrada ⇒ misma salida (IDs estables `"<lessonId>-<NN>"`).

**Reparto de señas por lección** (señas del nodo ordenadas por `order`, `n` = cantidad):
- L1 Aprende: primeras `a = n ≥ 7 ? 3 : 2`.
- L2 Reconoce: siguientes `b = n ≥ 6 ? 3 : 2` (sin pasarse de `n − 1`).
- L3 Practica: las restantes (siempre ≥ 1).
- L4 Reto final: todas.
- Nodo ALPHABET (por **posición**, no por letra, para soportar dígrafos): L1 = primeras `a = ⌈n/3⌉`, L2 = siguientes `b = ⌈(n − a)/2⌉`, L3 = el resto, L4 = todas. Con el contenido base: M1-N3 (13) → A–E · F–I · J–M; M1-N4 (14) → N–Q (con Ñ) · R–V · W–Z. Nodo NUMBERS: L1 = 1–3, L2 = 4–6, L3 = 7–10.
- Con 9 señas (máximo de un nodo STANDARD): 3 · 3 · 3.

**Ejercicios por tipo de lección** (corresponden a las 4 actividades de la interfaz):

| Lección | Por cada seña nueva | Al final de la lección |
|---|---|---|
| L1 Aprende | `OBSERVE` (act. 1) → `VIDEO_TO_MEANING` (act. 2) → `PRODUCE` (act. 3, sin puntaje) | `MEANING_TO_VIDEO` de cada seña nueva (repaso rápido, act. 2) |
| L2 Reconoce | `OBSERVE` → `VIDEO_TO_MEANING` → `MEANING_TO_VIDEO` | `CONVERSATION` 2 turnos (act. 4) |
| L3 Practica | `OBSERVE` → `VIDEO_TO_MEANING` → `MEANING_TO_VIDEO` → `PRODUCE` | `MEMORY_MATCH` (hasta 6 pares de señas **ya aprendidas** del nodo) + `CONVERSATION` (o `SPELLING` en ALPHABET) |
| L4 Reto final | — | `q = min(10, max(8, 2n))` preguntas mezcladas `VIDEO_TO_MEANING`/`MEANING_TO_VIDEO` de todo el nodo (recorriendo las señas en ciclo) + `MEMORY_MATCH` + `CONVERSATION` de 3 turnos (o `SPELLING` en ALPHABET) |

- L2 de ALPHABET usa `SPELLING` en lugar de `CONVERSATION`. Los módulos no publicados no generan nada.
- En ALPHABET, `PRODUCE` incluye `cameraLabel` solo si la letra es `static`; las `dynamic` siempre usan autoevaluación.
- En L4 los ejercicios no se agrupan por seña (la interfaz los muestra en secuencia).

**Distractores** (opciones incorrectas): 3 por pregunta, elegidos con esta prioridad: misma lección → mismo nodo → misma categoría → señas de nodos anteriores. Nunca repetidos, nunca la respuesta correcta, nunca dos opciones con el mismo `word`. Las opciones se identifican por el `sign_id`, nunca por posición (así se pueden barajar sin romper la evaluación).

---

## 7. Capa de dominio (`apps/api/app/domain`) — reglas exactas

Todo es Python puro y determinista. Cada regla tiene **casos de prueba obligatorios** en `tests/unit/` (escríbelos antes de implementar). Las estructuras son `@dataclass(frozen=True, slots=True)`; los contratos con la infraestructura son `typing.Protocol`.

### 7.1 `Clock` y fechas (`domain/dates.py`)

```python
from datetime import date, datetime, timedelta
from typing import Protocol
from zoneinfo import ZoneInfo

TZ = ZoneInfo("America/Bogota")          # requiere el paquete tzdata en Windows

class Clock(Protocol):
    def now(self) -> datetime: ...       # siempre con zona horaria (UTC)

def to_local_day(moment: datetime, tz: ZoneInfo = TZ) -> str:
    if moment.tzinfo is None:
        raise ValueError("Se requiere un datetime con zona horaria")
    return moment.astimezone(tz).date().isoformat()          # "YYYY-MM-DD"

def add_days(day: str, n: int) -> str:
    return (date.fromisoformat(day) + timedelta(days=n)).isoformat()

def diff_days(a: str, b: str) -> int:
    return (date.fromisoformat(b) - date.fromisoformat(a)).days
```
Pruebas: `2026-11-04T04:59:00Z` → `"2026-11-03"`; `2026-11-04T05:00:00Z` → `"2026-11-04"`; `add_days("2026-12-31", 1)` → `"2027-01-01"`; `diff_days` entre fin de febrero y marzo en año bisiesto; un `datetime` sin zona horaria lanza `ValueError` (evita mezclar horas locales y UTC).

### 7.2 Puntaje (`domain/policies/scoring.py`)

```python
@dataclass(frozen=True, slots=True)
class SessionScore:
    correct: int
    total: int
    score: int
    passed: bool

def score_session(correct: int, total: int, lesson_type: LessonType) -> SessionScore:
    passing = 70 if lesson_type is LessonType.CHALLENGE else 60
    score = 100 if total == 0 else round_half_up(correct * 100, total)
    passed = correct * 100 >= passing * total          # comparación entera, sin flotantes
    return SessionScore(correct, total, score, passed)
```
`round_half_up(a, b) = (2*a + b) // (2*b)`: **no usar `round()`**, que en Python redondea al par más cercano (`round(2.5) == 2`) y daría puntajes distintos a los esperados.
Pruebas: 3/5 → 60 y aprueba L1–L3; 7/10 aprueba el reto; 6/10 no aprueba el reto; 2/3 → 67; 1/8 → 13; total 0 → 100.

### 7.3 XP y néctar (`domain/policies/rewards.py`)

```
si no aprobó                       → xp = 0
base = 20 si es reto, si no 10
bono_precisión = round_half_up(score * 5, 100)
bono_perfecto = 5 si score == 100, si no 0
xp = base + bono_precisión + bono_perfecto
si ya había aprobado esta lección  → xp = ceil(xp / 2)   (usar -(-xp // 2), sin flotantes)
néctar = 5 si aprobó, si no 0;  +10 la primera vez que aprueba el reto del nodo
```
Pruebas: L1 con 100 % primera vez = 20 XP; repetida = 10; reto con 70 % = 24 XP; no aprobada = 0.

### 7.4 Desbloqueo derivado (`domain/policies/progress.py`)

Entrada: currículo ordenado (solo módulos publicados) + mejor puntaje por lección + lecciones aprobadas. Salida: estado por lección, nodo y módulo.

```
Orden global = módulos publicados por order → nodos por order → lecciones 1..4.
La primera lección del orden global siempre está AVAILABLE.
Una lección está AVAILABLE si la anterior en el orden global está aprobada.
Estado de lección: COMPLETED si aprobada; GOLDEN si es reto con mejor puntaje 100; si no, AVAILABLE o LOCKED.
Estado de nodo: LOCKED si su L1 está bloqueada; COMPLETED si su L4 está aprobada; GOLDEN si L4 es GOLDEN; si no, IN_PROGRESS.
Módulos con published = False: estado COMING_SOON, nunca bloquean ni cuentan para porcentajes.
```
Pruebas: usuario nuevo → solo `M1-N1-L1` disponible; aprobar L4 de M1-N4 desbloquea `M2-N1-L1`; **agregar un módulo nuevo al currículo no cambia el estado de lo ya aprobado**; reprobar no desbloquea.

### 7.5 Racha (`domain/policies/streak.py`)

Un día cuenta como activo si el usuario, ese día en hora de Bogotá, **completa al menos una lección (aprobada o no) o una sesión de repaso** (§8.5, todas sus preguntas respondidas). El repaso no se puede repetir para inflar la racha: solo contiene señas vencidas y, al terminarlo, todas quedan programadas para un día posterior. La meta diaria en minutos es una barra aparte y no afecta la racha.

```
apply_activity(streak, today) -> nueva racha (inmutable):
  si last_active_day == today → sin cambios
  gap = diff_days(last_active_day, today)
  si gap < 0 → sin cambios (fecha anterior a la última actividad: reloj o zona horaria inconsistentes)
  si last_active_day es None o gap > 1 + freezes_available → current = 1
  si gap == 1 → current += 1
  si 2 ≤ gap ≤ 1 + freezes_available → se consumen (gap − 1) protectores, current += 1
  longest = max(longest, current); last_active_day = today

display_streak(streak, today) -> int      # solo lectura, NO modifica
  si last_active_day es None → 0
  si last_active_day es hoy o ayer → current
  si gap − 1 ≤ freezes_available → current (protegida)
  si no → 0
```
`at_risk` (para Tomi «dormido» y el aviso del panel) = `last_active_day == ayer` (aún no ha practicado hoy).
Protector: cuesta **50 néctar**, máximo **2** guardados.
Pruebas: actividad a las 23:59 y a las 00:01 de Bogotá cuenta como dos días; dos lecciones el mismo día no suben la racha dos veces; una lección y un repaso el mismo día tampoco; un día perdido con 1 protector conserva la racha y consume 1; dos días perdidos con 1 protector reinicia a 1. (La función es la misma para lecciones y repasos: quien la llama es `GamificationService.register_activity`.)

### 7.6 Evaluación de ejercicios (polimorfismo, `domain/exercises/`)

El `payload` se valida con **modelos Pydantic discriminados por `type`** (`Annotated[Union[...], Field(discriminator="type")]`). Al leer un ejercicio de la BD siempre se valida; si falla, error 500 con el ID del ejercicio (contenido corrupto).

```python
class ExerciseEvaluator(ABC):
    type: ClassVar[ExerciseType]
    scored: ClassVar[bool]
    @abstractmethod
    def evaluate(self, payload: ExercisePayload, answer: AnswerPayload) -> bool: ...
    @abstractmethod
    def to_public(self, payload: ExercisePayload, catalog: SignCatalog) -> PublicExercise: ...

EVALUATORS: dict[ExerciseType, ExerciseEvaluator] = {e.type: e for e in (
    ObserveEvaluator(), VideoToMeaningEvaluator(), MeaningToVideoEvaluator(),
    MemoryMatchEvaluator(), ProduceEvaluator(), ConversationEvaluator(), SpellingEvaluator())}
```

**Tokens de opción (D20).** El cliente nunca recibe IDs de seña en las opciones. Cada opción se identifica con
`token(lado, sign_id) = HMAC_SHA256(clave, f"{session_id}:{exercise_id}:{lado}:{sign_id}")[:10]` (hex), donde `clave` se deriva de `JWT_SECRET` (`sha256(b"option-tokens:" + secreto)`). El cálculo es determinista y no requiere guardar nada: para evaluar, el servidor recalcula los tokens de las opciones del ejercicio y busca el que envió el cliente. `lado` distingue videos (`v`) de palabras (`w`) en `MEMORY_MATCH`. La función de tokens vive en `app/services` (usa el secreto); el dominio recibe una función `tokenize` inyectada.

| Tipo | `payload` (servidor) | Lo que ve el cliente | `answer` | Evaluación |
|---|---|---|---|---|
| OBSERVE | `{ signId }` | `{ video, word, howTo, usageExample }` | `{ watched: true }` | siempre correcta, sin puntaje |
| VIDEO_TO_MEANING | `{ signId, optionIds[4], correctId }` | `{ video, options:[{token, word}] }` barajadas | `{ optionToken }` | token de `correctId` |
| MEANING_TO_VIDEO | `{ signId, optionIds[4], correctId }` | `{ word, options:[{token, video}] }` | `{ optionToken }` | igual |
| MEMORY_MATCH | `{ signIds[] }` | `{ videoCards:[{token, video}], wordCards:[{token, word}] }` barajadas por separado | `{ attempts: [{videoToken, wordToken}] }` | correcta si todos los pares terminan emparejados y los errores ≤ número de pares |
| PRODUCE | `{ signId }` | `{ video, word, cameraLabel }` (`cameraLabel` = slug, para el modelo) | `{ method: "camera" \| "self", ok, confidence? }` | sin puntaje; `ok = false` programa repaso |
| CONVERSATION | `{ turns:[{promptId, optionIds, correctId}] }` | `{ turns:[{prompt: video, options:[{token, video}]}] }` | `{ choices: list[str] }` (tokens) | correcta si todos los turnos son correctos |
| SPELLING | `{ word, letterIds[], optionWords[4] }` | `{ letters:[video…], options:[{token, word}] }` | `{ optionToken }` | token de `word` (con `lado = "s"`) |

`video` = `{ src, poster }` con las rutas por contenido de D19. **`to_public()` nunca incluye `correctId`, `signId` ni slugs en las opciones**; una prueba recorre todos los ejercicios generados del contenido real y verifica que ningún valor público de opción coincida con un slug. El barajado usa `random.Random(f"{session_id}:{exercise_id}")` (estable dentro de la sesión). La respuesta de `answers` devuelve `correctToken` (y `correctWord` cuando aplica) para que la interfaz marque la opción correcta.

> **Límite conocido (documentado):** el diccionario es público y muestra el video de cada palabra, así que alguien decidido podría comparar videos para hacer trampa. El objetivo de D2/D20 es impedir la trampa **trivial** (ver la respuesta en la red) y que el cliente invente puntajes; no se busca seguridad contra un atacante. Las recompensas son simbólicas.

### 7.7 Repaso espaciado (`domain/policies/review.py`)

Intervalos en días: `(1, 2, 4, 7, 15, 30)`. Acierto → `strength = min(5, strength + 1)`; error o «Necesito repasar» → `strength = 0`. `next_review_day = add_days(today, INTERVALS[strength])`. Cola: `next_review_day <= today`, máximo 15, menor `strength` primero.

### 7.8 Normalización de texto (`domain/text.py`)

Busca sin importar tildes ni mayúsculas, **conservando la ñ** (si no, «año» y «ano» serían iguales):
```python
import re, unicodedata

_PUNCT = re.compile(r"[¿?¡!.,;:]")
_SPACES = re.compile(r"\s+")

def normalize_text(s: str) -> str:
    s = unicodedata.normalize("NFD", s.strip().lower())
    s = s.replace("n\u0303", "\u00f1")                       # protege la ñ (escapes explícitos: no los reemplaces por el carácter)
    s = "".join(ch for ch in s if unicodedata.category(ch) != "Mn")  # quita las demás tildes
    s = _PUNCT.sub("", s)
    return _SPACES.sub(" ", s).strip()
```
Pruebas: `"  GRACÍAS "` → `"gracias"`; `"¿Cómo estás?"` → `"como estas"`; `"Año"` → `"año"`; `"BAÑO"` → `"baño"`.
Distancia de Levenshtein para sugerencias: función propia en `domain/text.py` (≈ 15 líneas) con pruebas; no se agrega dependencia.

### 7.9 Logros (`domain/policies/achievements.py`)

| ID | Título | Condición | Néctar |
|---|---|---|---|
| FIRST_FLAP | Primer aleteo | Completó el intro (enviado al registrarse) | 10 |
| FIRST_LESSON | Primeras alas | Primera lección aprobada | 10 |
| STREAK_3 | Aleteo constante | Racha ≥ 3 | 15 |
| STREAK_7 | Vuelo de una semana | Racha ≥ 7 | 30 |
| NODE_DONE | Nodo superado | Primer reto aprobado | 15 |
| GOLDEN_NODE | Nodo dorado | Un reto con 100 % | 20 |
| MODULE_1 | Fundamentos dominados | Todas las lecciones de M1 aprobadas | 40 |
| SIGNS_50 | Manos que hablan | 50 señas distintas respondidas correctamente | 40 |
| HUMMINGBIRD_EYE | Ojo de colibrí | 20 reconocimientos correctos por cámara | 30 |

Los logros se evalúan en cuatro momentos: al completar una lección (`GamificationService.apply_completion`), al completar un repaso (STREAK_3 y STREAK_7 pueden cumplirse ahí), al registrar un reconocimiento correcto de la cámara (`RecognitionService`, para HUMMINGBIRD_EYE) y al registrarse con el intro completo (FIRST_FLAP). Cada logro es una clase que implementa `AchievementRule` (`id`, `nectar_reward`, `is_satisfied(stats) -> bool`). `evaluate_achievements(stats, already_unlocked) -> list[str]` es pura. La inserción usa `insert(...).on_conflict_do_nothing()` de PostgreSQL: aunque se ejecute dos veces a la vez, nunca hay duplicados ni se paga néctar doble (el néctar se suma solo por las filas realmente insertadas, usando `RETURNING`).

### 7.10 Vidas (`domain/policies/hearts.py`)

Mecánica estilo Duolingo, pensada para **no dejar nunca a nadie atascado**. Se puede desactivar con `HEARTS_ENABLED=false` (por ejemplo, si molesta en la sustentación) sin tocar código: entonces no se muestran ni se descuentan.

```
MAX_HEARTS = 5 · REFILL_EVERY = 4 h · REFILL_COST = 30 néctar
Estado guardado: (hearts, updated_at)       # updated_at = None ⇒ lleno

current(state, now) -> (hearts, next_heart_at):        # pura; nunca escribe
  si hearts >= MAX o updated_at es None → (MAX, None)
  gained = max(0, now − updated_at) // REFILL_EVERY
  h = min(MAX, hearts + gained)
  next_heart_at = None si h == MAX, si no updated_at + (gained + 1) · REFILL_EVERY

lose_one(state, now) -> state:     # materializa y resta 1; nunca baja de 0
  (h, _) = current(state, now)
  si h == 0 → estado materializado sin cambios
  si h == MAX → (MAX − 1, now)                         # empieza a contar la recarga
  si no → (h − 1, updated_at + gained · REFILL_EVERY)   # conserva el avance de la recarga en curso

gain_one(state, now) / refill(now) -> state            # +1 (tope 5) / (MAX, None)
```

Reglas de uso (en los servicios, no en el dominio):
- Se pierde **1 vida por cada primer intento incorrecto en un ejercicio con puntaje** de las lecciones **Reconoce, Practica y Reto final**. **Aprende (L1) y el repaso nunca quitan vidas** (son para aprender).
- La vida se descuenta solo si la respuesta **realmente se insertó** (`INSERT … ON CONFLICT DO NOTHING RETURNING`): un reintento de red no descuenta dos veces. La fila del usuario se bloquea con `SELECT … FOR UPDATE` en esa misma transacción.
- Con 0 vidas: `POST /lessons/{id}/sessions` de L2–L4 responde 403 `NO_HEARTS` con `nextHeartAt`. **Siempre** se pueden hacer lecciones Aprende y el repaso. Una lección ya empezada **siempre se puede terminar**, aunque las vidas lleguen a 0 en medio.
- Formas de recuperar: esperar (1 cada 4 h), completar un repaso con ≥ 80 % de aciertos (+1) o recargar todas por 30 de néctar (`POST /gamification/hearts-refill`; 409 `NOT_ENOUGH_NECTAR` / `HEARTS_FULL`).
- Las vidas **no afectan** XP, puntaje ni aprobación.

Pruebas: 5 vidas → un error → 4 y `next_heart_at = now + 4 h`; a las 3 h 59 min sigue en 4, a las 4 h vuelve a 5; con 3 vidas y 5 h transcurridas, perder una deja 3 y conserva 1 h de avance; con 0 no baja de 0; `updated_at` en el futuro (reloj atrasado) no suma vidas; `gain_one` con 5 no pasa de 5.

---

## 8. Capa de aplicación (FastAPI) y API

### 8.1 Servicios (`app/services/`)

| Servicio | Métodos | Notas |
|---|---|---|
| `AuthService` | `register`, `login`, `refresh`, `logout`, `me` | Correo normalizado; refresh con rotación (§11). |
| `CurriculumService` | `get_learning_path(user_id)`, `get_node(user_id, node_id)` | Usa `compute_progress`. Carga el currículo con `selectinload` en una sola consulta (evita N+1). |
| `LessonSessionService` | `start`, `answer`, `complete` | Ver §8.3. Descuenta vidas (§7.10). |
| `GamificationService` | `apply_completion(session, …)`, `register_activity(user, day, seconds, kind)`, `get_stats`, `buy_streak_freeze`, `refill_hearts`, `grant_intro` | Siempre dentro de la transacción del llamador. `register_activity` es el único punto que actualiza racha y actividad diaria (lecciones y repasos). |
| `ProgressService` | `get_summary`, `get_history(page)`, `get_units` | |
| `ReviewService` | `get_queue`, `start`, `answer`, `complete` | Sesión evaluada por el servidor (§8.5, D23). El repaso no da XP; cuenta para la racha y puede devolver 1 vida. |
| `DemoSeeder` (`app/content/demo.py`) | `run(clock, reset)` | Crea el usuario de demostración usando los servicios reales (§17.4). |
| `DictionaryService` | `search(q, category, page)`, `get_sign(user_id, slug)`, `get_categories`, `list_favorites`, `add_favorite`, `remove_favorite` | Categorías vacías no se devuelven. |
| `RecognitionService` | `register_result(user_id, data)` | Solo números; nunca imágenes. |

Los routers (`app/api/*.py`) solo: validan con Pydantic, obtienen el usuario con `Depends(current_user)`, llaman al servicio y devuelven el esquema de salida. **No contienen lógica ni consultas.**

### 8.2 Contratos de la API (prefijo `/api`)

Errores: siempre `{ "statusCode": 400, "code": "LESSON_LOCKED", "message": "Texto en español para el usuario" }`, mediante una excepción propia `AppError(status, code, message)` y manejadores globales. Los errores de validación de Pydantic se transforman a este formato con `code: "VALIDATION_ERROR"` y mensajes en español por campo (`fields: { email: "Correo no válido" }`).

| Método | Ruta | Auth | Respuesta / notas |
|---|---|---|---|
| GET | `/health` | — | `{ ok: true, db: true }` |
| GET | `/intro` | — | `{ cards:[{word, video}], quiz:[{video, options:[{word, correct}]}] }` desde `content/intro.json`. Incluye la respuesta porque el intro no da XP. |
| POST | `/auth/register` | — | Body: `name, email, password (8–72 bytes UTF-8), dailyGoalMinutes (5|10|15|20), acceptedDataPolicy: true, introCompleted?` → `{ accessToken, user }` + cookie `rt` |
| POST | `/auth/login` | — | `{ accessToken, user }` + cookie. Error genérico «Correo o contraseña incorrectos». 5/min por IP. |
| POST | `/auth/refresh` | cookie | Rota el token. 401 si no es válido. |
| POST | `/auth/logout` | cookie | Revoca y borra la cookie. Siempre 204. |
| GET · PATCH | `/me` | ✅ | PATCH solo `name`, `dailyGoalMinutes`, `dominantHand`. |
| GET | `/learning-path` | ✅ | Módulos → nodos → lecciones con `status`, `bestScore`, `estimatedXp`. |
| GET | `/nodes/{node_id}` | ✅ | Nodo + 4 lecciones + señas. |
| POST | `/lessons/{lesson_id}/sessions` | ✅ | 403 `LESSON_LOCKED` si no está disponible; 403 `NO_HEARTS` (con `nextHeartAt`) si no tiene vidas y la lección no es Aprende; 404 `LESSON_NOT_FOUND` si no existe o su módulo no está publicado → `{ sessionId, lesson, exercises, hearts }` (públicos, §7.6). |
| POST | `/lesson-sessions/{id}/answers` | ✅ | `{ exerciseId, answer }` → `{ correct, correctToken, correctWord?, alreadyAnswered, hearts: { current, nextHeartAt } }`. Si ya respondió, devuelve la evaluación original. 409 `SESSION_COMPLETED` si la sesión ya se cerró; 410 `SESSION_EXPIRED` si tiene más de 24 h. |
| POST | `/lesson-sessions/{id}/complete` | ✅ | **Idempotente** → `LessonCompletionResult`. 409 `SESSION_INCOMPLETE` si falta responder algún ejercicio (evita «completar» lecciones vacías para sumar racha); 410 `SESSION_EXPIRED`. |
| GET | `/gamification/stats` | ✅ | `{ totalXp, nectar, streak: {current, longest, freezesAvailable, atRisk}, today: {seconds, goalSeconds, xp}, hearts: {enabled, current, max, nextHeartAt} }` |
| GET | `/gamification/achievements` | ✅ | Todos, con `unlockedAt` o `null`. |
| POST | `/gamification/streak-freeze` | ✅ | 409 `NOT_ENOUGH_NECTAR` / `MAX_FREEZES`. |
| POST | `/gamification/hearts-refill` | ✅ | Recarga las 5 vidas por 30 de néctar. 409 `NOT_ENOUGH_NECTAR` / `HEARTS_FULL`. |
| GET | `/progress/summary` · `/progress/history?page=1` · `/progress/units` | ✅ | `% avance` = lecciones aprobadas ÷ lecciones de módulos publicados (global y por módulo); `señas aprendidas` = señas introducidas en lecciones aprobadas; precisión por unidad = respuestas correctas ÷ respuestas con puntaje. Historial de 20 por página, más recientes primero. |
| GET | `/reviews/queue` | ✅ | `{ due: n, signs: [{ word }] }` (hasta 15, para el panel). |
| POST | `/reviews/sessions` | ✅ | Crea (o devuelve la abierta de hoy) una sesión de repaso → `{ sessionId, exercises }` con tokens opacos. 409 `NO_REVIEWS_DUE` si no hay señas vencidas. |
| POST | `/review-sessions/{id}/answers` | ✅ | Igual que en lecciones: `{ exerciseId, answer }` → `{ correct, correctToken, correctWord?, alreadyAnswered }`. |
| POST | `/review-sessions/{id}/complete` | ✅ | Idempotente; 409 `SESSION_INCOMPLETE` → `{ correct, total, score, streak: {current, extended}, heartsGained, newAchievements }`. |
| GET | `/dictionary/signs?q=&category=&page=` | opcional | `ILIKE` sobre `normalized_word` con el término normalizado (escapando `%` y `_`); si hay 0 resultados, sugerencias por Levenshtein ≤ 2. |
| GET | `/dictionary/signs/{slug}` | opcional | Ficha + `relatedLesson: { id, title, status }` (`null` si la seña es solo de diccionario) + `isFavorite`. |
| GET | `/dictionary/categories` | — | Solo categorías con señas. |
| GET · POST · DELETE | `/dictionary/favorites[/{slug}]` | ✅ | POST/DELETE idempotentes. |
| POST | `/recognition/results` | ✅ | `{ signId, correct, confidence }` con `signId` existente y `0 ≤ confidence ≤ 1` (60/min por usuario). Solo cuenta para el logro si `correct` y `confidence ≥ 0,7`, como máximo una vez por seña cada 10 s. |

**`LessonCompletionResult`:**
```json
{ "score": 90, "correct": 9, "total": 10, "passed": true, "xpEarned": 24, "nectarEarned": 15,
  "streak": { "current": 6, "extended": true }, "newAchievements": [{ "id": "STREAK_3", "title": "Aleteo constante" }],
  "unlocked": [{ "type": "LESSON", "id": "M1-N3-L1" }], "mascotMood": "cheer", "mascotMessage": "¡Vas volando!" }
```

### 8.3 Sesión de lección (el corazón del sistema)

```mermaid
sequenceDiagram
    actor U as Usuario
    participant W as LessonPage (React)
    participant C as Router lessons (FastAPI)
    participant S as LessonSessionService
    participant D as Dominio
    participant R as Repositorios (SQLAlchemy)
    U->>W: Abre la lección
    W->>C: POST /api/lessons/M1-N2-L2/sessions
    C->>S: start(user_id, lesson_id)
    S->>D: compute_progress → ¿disponible?
    S->>R: crear LessonSession
    S-->>W: ejercicios públicos (sin respuestas)
    loop Cada ejercicio
        U->>W: Responde
        W->>C: POST /api/lesson-sessions/{id}/answers
        C->>S: answer(...)
        S->>D: EVALUATORS[type].evaluate(payload, answer)
        S->>R: INSERT … ON CONFLICT DO NOTHING
        S-->>W: { correct, correctToken, hearts }
    end
    W->>C: POST /api/lesson-sessions/{id}/complete
    C->>S: complete(...)
    S->>R: sesión propia SERIALIZABLE (reintento ×3)
    S->>D: score_session · rewards · streak · review · achievements
    S->>R: resultado, XP, néctar, racha, actividad diaria, repasos, logros
    S-->>W: LessonCompletionResult
    W->>U: Celebración con Tomi 🐦
```

Reglas de `complete`:
1. Verifica que la sesión sea del usuario (si no: 404, no 403, para no revelar que existe).
2. Si `completed_at` ya existe → devuelve el resultado guardado (idempotencia; protege contra el doble clic y el doble montaje de React StrictMode).
3. Ejecuta todo en una **sesión de base de datos propia** creada con `serializable_session()` (un `sessionmaker` sobre `engine.execution_options(isolation_level="SERIALIZABLE")`), no en la sesión de la petición (D21). Si PostgreSQL lanza `psycopg.errors.SerializationFailure` (envuelta por SQLAlchemy en `OperationalError`), cierra esa sesión y reintenta hasta 3 veces con una sesión nueva y espera corta.
4. Dentro de la transacción, `SELECT … FOR UPDATE` sobre la sesión antes de comprobar `completed_at`.
5. `duration_sec = max(0, min(now − started_at, 15 min))` con `now = clock.now()` (D22).
6. Sesiones sin completar de más de 24 h expiran: `answers` y `complete` responden 410 `SESSION_EXPIRED` (no se borran).
7. `complete` exige que todos los ejercicios de la sesión tengan respuesta (409 `SESSION_INCOMPLETE`).
8. Si el contenido se recargó mientras la sesión estaba abierta (los ejercicios cambiaron), la sesión responde 410 `SESSION_EXPIRED` y la interfaz ofrece empezar de nuevo.
9. `answer` (en la sesión de la petición): bloquea la fila del usuario (`FOR UPDATE`), inserta la respuesta con `RETURNING` y, solo si se insertó, es incorrecta, tiene puntaje y la lección no es Aprende, aplica `lose_one` y suma `hearts_lost` (§7.10).

### 8.4 Contrato tipado entre Python y TypeScript

- FastAPI genera `openapi.json` a partir de los modelos Pydantic (con `response_model` en cada endpoint y alias `camelCase` vía `alias_generator=to_camel`, `populate_by_name=True`).
- `alas gen-api` exporta `openapi.json` y ejecuta `npx openapi-typescript openapi.json -o apps/web/src/lib/api-types.ts`.
- El cliente del frontend usa esos tipos (`paths[...]`); **prohibido escribir a mano interfaces de respuestas de la API**.
- `alas check` (mediante `alas gen-api --check`) regenera los tipos en una carpeta temporal y falla si difieren del archivo versionado («Los tipos de la API están desactualizados: ejecuta `alas gen-api`»).


### 8.5 Sesión de repaso (D23)

Reutiliza los evaluadores, los tokens opacos (D20) y el patrón de `LessonSessionService`, con estas diferencias:
- `start`: toma la cola (`next_review_day <= hoy`, máximo 15, menor `strength` primero). Si está vacía → 409 `NO_REVIEWS_DUE`. Si ya hay una sesión de repaso abierta de hoy, la devuelve (protege del doble montaje de StrictMode). Genera un ejercicio por seña con `build_review_items` (función pura en `domain/content/review_builder.py`): alterna `VIDEO_TO_MEANING` y `MEANING_TO_VIDEO`, distractores con la misma prioridad de §6.7 pero **solo entre señas que el usuario ya vio**, semilla `f"review:{session_id}"`. Los ejercicios (con su respuesta) se guardan en `review_sessions.items`, nunca se envían completos. IDs `R-01`, `R-02`…
- `answer`: igual que en lecciones (primer intento, `review_answers` con PK compuesta). **No quita vidas.**
- `complete` (sesión SERIALIZABLE propia, idempotente, 409 `SESSION_INCOMPLETE`, 410 a las 24 h): aplica `ReviewScheduler` a cada seña (acierto → sube; error → mañana), llama a `GamificationService.register_activity(kind="review")` (racha y `daily_activity.reviews`), da +1 vida si `correct · 100 ≥ 80 · total`, evalúa logros de racha. No da XP ni néctar.
- La autoevaluación «Necesito repasar» de las lecciones sigue programando repasos como antes (se procesa en el `complete` de la lección).

---

## 9. Capa de presentación (React + TypeScript — única parte que no es Python)

### 9.1 Rutas

| Ruta | Página | Acceso |
|---|---|---|
| `/` | Redirige: con sesión → `/aprender`; sin sesión y sin intro → `/bienvenida`; sin sesión con intro → `/ingresar` | — |
| `/bienvenida` | Intro + mini-quiz | Público |
| `/ingresar` · `/registro` | Login / registro | Solo sin sesión |
| `/aprender` | Ruta de aprendizaje | Protegida |
| `/leccion/:lessonId` | Lección (pantalla completa, sin barra lateral) | Protegida |
| `/repaso` | Sesión de repaso | Protegida |
| `/diccionario` · `/diccionario/:slug` | Diccionario y ficha | Público (favoritos requieren sesión) |
| `/camara` | Reconocimiento (lazy) | Protegida |
| `/progreso` · `/logros` · `/perfil` | | Protegida |
| `/admin/dataset` | Colector de muestras para entrenar el modelo (lazy). El entrenamiento se hace en Python (§10.5). | Solo ADMIN |
| `*` | 404 con Tomi | — |

### 9.2 Sesión en el cliente
- Cliente HTTP en `src/lib/api.ts` tipado con `api-types.ts` generado desde FastAPI (§8.4).
- `accessToken` **solo en memoria** (Zustand), nunca en `localStorage`.
- Al cargar la app: `POST /auth/refresh`; mientras tanto se muestra una pantalla de carga (no parpadeo de login).
- `ApiClient`: si recibe 401, hace **un solo** refresh compartido entre peticiones simultáneas (*single-flight*), reintenta una vez y, si vuelve a fallar, cierra sesión y redirige a `/ingresar?volver=<ruta>`.

### 9.3 Pantalla de lección (diseño en columna de los mockups §4.1)

Componentes: `LessonPage` → `LessonHeader` (`MÓDULO 1 · NODO 2 — LECCIÓN 2 · RECONOCE`, `+N XP` estimado, barra de progreso, "Seña 1 de 3") → `SignVideoPlayer` → lista de `ActivityCard` (Observa · Selecciona · Produce · Usa lo aprendido).

Comportamiento:
- Los ejercicios se agrupan por seña; las actividades se habilitan en secuencia (🔒 → activa → ✔) con *scroll* suave a la activa.
- **Actividad 2**: "Comprobar respuesta" deshabilitado hasta elegir; luego verde/rojo con la correcta marcada y mensaje de Tomi; botón "Continuar".
- Al terminar todos los ejercicios: `complete` → `CelebrationModal` → volver a `/aprender` (invalidar queries de ruta y estadísticas).
- Botón ✕: confirmar "¿Salir de la lección? Perderás el avance de esta sesión." También aviso `beforeunload` si hay respuestas.
- Si la sesión falla al iniciar con `LESSON_LOCKED`, mostrar mensaje y volver a la ruta.
- Lecciones sin cámara disponible: `PRODUCE` muestra autoevaluación ("¿Te salió igual al video?" `[Sí, me salió]` `[Necesito repasar]`).
- `PRODUCE` usa cámara **solo si** el `cameraLabel` está en `labels.json` del modelo **y** el usuario pulsa «Activar cámara» y da permiso; si no, autoevaluación. MediaPipe y TensorFlow.js se cargan **solo al pulsar ese botón** (no al abrir la lección).
- En desarrollo, React StrictMode monta dos veces: iniciar la sesión con una referencia que evite el doble `POST …/sessions` (si ocurre, la sesión sobrante simplemente expira).
- **Vidas:** el encabezado de la lección muestra ❤️ N (excepto en Aprende, donde muestra «Sin vidas en juego»). Al perder una, el corazón late una vez (respetando movimiento reducido) y Tomi dice algo amable, nunca un regaño. Si llegan a 0 en medio de la lección, se sigue normalmente y al final se avisa.
- **Sin vidas** (`NO_HEARTS`): modal con Tomi y tres opciones: «Repasar para ganar una vida» (si hay repaso pendiente), «Recargar por 30 de néctar» y «Esperar» (cuenta regresiva hasta `nextHeartAt`); además, recordatorio de que las lecciones Aprende están siempre disponibles.
- **Repaso** (`/repaso`): misma tarjeta de lección con solo la actividad 2; al terminar, celebración pequeña con racha y vida ganada.
- Ante `SESSION_EXPIRED`: mensaje «Esta lección se actualizó o pasó mucho tiempo. Empecemos de nuevo» y botón para reiniciar.

### 9.4 `SignVideoPlayer`
```tsx
<video src={videoPath} poster={posterPath} muted playsInline loop={loop} preload="metadata"
       aria-label={`Video de la seña ${word}`} />
```
- Controles propios: ▶/⏸, 🔁 repetir (`currentTime = 0; play()`), 🐢 `playbackRate` 0.5 / 1.
- `play()` devuelve una promesa: **siempre** con `.catch(() => {})` y botón de reproducir visible si el navegador bloquea la reproducción.
- Precargar el video del siguiente ejercicio (`<link rel="preload" as="video">` no es confiable: crear un `<video preload="auto">` oculto).
- Si `onError` → tarjeta "No pudimos cargar este video" con botón reintentar (nunca pantalla rota).
- Si `isPlaceholder` → etiqueta discreta "Video en preparación".

### 9.5 Diseño
- Tokens (CSS variables): `--primary #10B981` · `--primary-dark #047857` (texto verde sobre fondo claro, contraste AA) · `--secondary #06B6D4` · `--accent #7C3AED` · `--nectar #FACC15` · `--flower #EC4899` · `--locked #CBD5E1` · `--bg #F5FAF7` · `--surface #FFFFFF` · `--ink #0E2A2F` · `--muted #45606A`.
- Tipografía: Nunito (títulos) e Inter (texto), desde `@fontsource`.
- Estados bloqueados: siempre ícono 🔒 + texto, no solo color.

### 9.6 Tomi (SVG, sin archivos externos)

```tsx
// components/mascot/Tomi.tsx — moods: happy | cheer | sad | thinking | sleeping
export function TomiSvg({ size = 120 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 400 400" role="img" aria-label="Tomi, el colibrí">
      <path d="M165 245 L70 320 L118 298 L88 368 L178 270 Z" fill="#0E9F6E" />
      <path className="tomi-wing" d="M190 205 C 220 90, 310 40, 370 52 C 335 110, 275 170, 215 218 Z" fill="#06B6D4" />
      <path d="M200 210 C 235 130, 290 105, 335 108 C 300 150, 255 192, 212 222 Z" fill="#67E8F9" opacity="0.85" />
      <ellipse cx="205" cy="228" rx="82" ry="54" transform="rotate(-30 205 228)" fill="#10B981" />
      <ellipse cx="252" cy="200" rx="26" ry="18" fill="#EC4899" />
      <circle cx="278" cy="160" r="38" fill="#10B981" />
      <path d="M308 150 L396 126 L312 168 Z" fill="#E8F4EF" />
      <circle cx="290" cy="152" r="8" fill="#0E2A2F" />
      <circle cx="293" cy="149" r="3" fill="#F5FAF7" />
    </svg>
  );
}
```
Animaciones con Framer Motion por *mood*: `happy` flota suave; `cheer` salto + giro corto; `sad` baja y se inclina (nunca regaña); `thinking` se balancea; `sleeping` ojos cerrados (reemplazar círculos por una línea) — racha en riesgo. Con `prefers-reduced-motion`, sin movimiento. El componente `Mascot` acepta `mood` y `message` (burbuja de texto).

### 9.7 Plataforma objetivo: solo portátil y PC

- **No se implementa diseño para celulares en esta entrega.** Ignorar las secciones "Móvil" de `docs/mockups.md` (barra inferior, versión de 390 px, etc.).
- Ancho mínimo soportado: **1024 px**. Diseñar para **1366×768** (el portátil más común) y comprobar en 1280×720 y 1920×1080.
- Layout de la pantalla principal: barra lateral fija (≈ 240 px) + ruta central (máx. 720 px) + panel derecho (≈ 320 px). Entre 1024 y 1279 px el panel derecho baja debajo de la barra superior o se oculta tras un botón; nunca *scroll* horizontal.
- Lección: tarjeta centrada `max-w-3xl`; en 1366×768 el video, el título de la actividad y las opciones de la Actividad 2 deben caber sin *scroll* (video máx. 360 px de alto). El botón "Comprobar respuesta" puede quedar fijo al pie del área de la lección.
- **Pantallas menores a 1024 px**: mostrar una pantalla amable con Tomi: «Alas de Señas está pensada por ahora para portátil o computador. ¡Pronto llegará la versión para celular!». No bloquea el diccionario si se quiere ver, pero no se optimiza.
- Navegación con teclado: `Tab` recorre las opciones; teclas `1`–`4` eligen opción y `Enter` comprueba/continúa en la lección (atajo de escritorio útil y accesible).
- Navegadores soportados: Chrome y Edge (recomendados, mejor rendimiento de cámara), Firefox; Safari en Mac como bonus.
- Las decisiones técnicas que ya facilitan el móvil (videos H.264 `yuv420p`, `muted`, `playsInline`) se mantienen: no cuestan nada y dejan lista la futura versión.

## 10. Reconocimiento por cámara (beta)

> **Extensión:** la captura de **dos manos + rostro + hombros** para señas con movimiento está especificada en `docs/anexo-camara-holistica.md` (fase **10B**, opcional y posterior a la fase 10). Esta sección describe el modelo del alfabeto (una mano, estático), que debe seguir funcionando igual.

### 10.1 Archivos (servidos localmente)
- `alas camera-assets` (Python) copia `node_modules/@mediapipe/tasks-vision/wasm/*` a `apps/web/public/mediapipe/wasm/` y descarga `hand_landmarker.task` a `apps/web/public/mediapipe/`. Si la descarga falla, imprime la URL oficial para descargarlo a mano.
- Modelo propio: `apps/web/public/models/lsc-alfabeto/{model.json, group1-shard*.bin, labels.json, meta.json}` (el conversor nombra así los pesos; `model.json` los referencia, por eso se sirve la carpeta completa y nunca se renombran).

### 10.2 Pipeline (todo en el navegador)

```mermaid
flowchart LR
    A[getUserMedia<br/>640x480, cámara web] --> B[HandLandmarker<br/>VIDEO, numHands 1]
    B --> C[normalizeLandmarks<br/>63 valores]
    C --> D[MLP TensorFlow.js]
    D --> E[Suavizado: mayoría en<br/>últimos 10 resultados]
    E --> F{Confianza ≥ 0.70<br/>y clase ≠ NINGUNA?}
    F -- sí --> G[Seña detectada ✅]
    F -- no --> H[Tomi: acerca la mano<br/>o inténtalo de nuevo]
```

### 10.3 `normalizeLandmarks` (una sola función para recolectar, entrenar e inferir)
1. Tomar los 21 puntos `(x, y, z)`.
2. Si la mano reportada es izquierda, reflejar `x → 1 − x` (un solo modelo para ambas manos).
3. Restar la muñeca (punto 0) a todos los puntos.
4. Dividir entre la distancia muñeca–base del dedo medio (punto 9); si es < 1e-6, descartar el cuadro.
5. Aplanar → 63 números. Con prueba unitaria (entrada conocida → salida conocida; invariante a traslación y escala).

### 10.4 Errores que el módulo debe manejar (cada uno con mensaje en español)

| Situación | Manejo |
|---|---|
| Permiso denegado (`NotAllowedError`) | "Necesitamos permiso para usar la cámara" + cómo habilitarlo + usar autoevaluación. |
| Sin cámara (`NotFoundError`) / ocupada (`NotReadableError`) | Mensaje específico + autoevaluación. |
| Página sin HTTPS (no `localhost`) | Aviso: la cámara solo funciona con HTTPS. |
| Timestamps repetidos en `detectForVideo` | Usar `performance.now()` y saltar el cuadro si no es mayor que el anterior. |
| Doble inicialización (React StrictMode) | Inicializar en un *singleton* con promesa en caché; nunca dos instancias. |
| Cámara sigue encendida al salir | En el *cleanup*: `track.stop()` de todas las pistas, cancelar `requestAnimationFrame`, `landmarker.close()`. |
| Pestaña oculta | Pausar el bucle con `visibilitychange`. |
| Fugas de memoria de tfjs | Toda predicción dentro de `tf.tidy()`; liberar tensores. |
| Modelo aún no entrenado | `MockClassifier` (devuelve NINGUNA) y aviso "Modelo en entrenamiento" para ADMIN. |
| Vista espejo | Mostrar el video reflejado (como un espejo) solo con CSS `transform: scaleX(-1)`; los puntos se dibujan con el mismo reflejo. |

### 10.5 Colector (navegador) y entrenamiento (Python)

**Colector `/admin/dataset` (navegador, solo ADMIN):** elegir etiqueta — **siempre el slug de la seña** (`letra-a`, `letra-b`…) o `NINGUNA`, para que `labels.json` coincida con `cameraLabel` —, cuenta regresiva de 3 s, grabación de 10 s a ~10 muestras/s. Muestra el conteo por clase. Exporta `dataset.json` con los vectores **ya normalizados** por `normalizeLandmarks` y los metadatos `featureVersion: "hand-v1"`, `featureSize: 63`, `collector` (alias), `tasksVision` (versión). Python **nunca** recalcula puntos: solo entrena sobre estos números (D11).

**Entrenamiento `ml/train_static.py` (Python 3.11, TensorFlow 2.15):**
```
uv run --project ml python ml/train_static.py --data ml/data/*.json --out apps/web/public/models/lsc-alfabeto
```
1. Carga y valida todos los `dataset.json` (misma `featureVersion` y `featureSize`; si no, error).
2. Separa entrenamiento/validación **por persona** (`collector`) cuando hay ≥ 3 personas (`GroupShuffleSplit` de scikit-learn); si no, 80/20 estratificado y lo advierte.
3. Entrena MLP `Dense(128, relu) → Dropout(0.3) → Dense(64, relu) → Dense(n, softmax)`, `adam`, hasta 60 épocas con `EarlyStopping`.
4. Imprime precisión por clase y guarda la **matriz de confusión** (`ml/reports/confusion.png`).
5. Exporta con `tensorflowjs.converters.save_keras_model` y escribe `labels.json` y `meta.json` (`featureVersion`, `featureSize`, `threshold: 0.7`, fecha) **en el mismo paso**, para que el orden de etiquetas siempre coincida con el modelo.
6. Semillas fijas (`numpy`, `tensorflow`, `random`) para que el resultado sea reproducible.

- `ml/notebooks/entrenamiento.ipynb` hace lo mismo en **Google Colab** (si TensorFlow da problemas en el computador).
- Meta: ≥ 300 muestras por letra, de ≥ 3 personas, y ≥ 600 de `NINGUNA`.
- **Solo letras con `motion = static`** confirmadas por el intérprete (`train_static.py` rechaza etiquetas `dynamic` leyendo `signs.csv`). Empezar por 5–10 letras.
- Prueba en el navegador (Vitest): cargar un modelo de ejemplo exportado y verificar que `labels.json` tiene tantas etiquetas como salidas el modelo.
- **Compatibilidad Python ↔ TensorFlow.js (desde la fase 0):** `ml/fixtures/tfjs-smoke/` trae dos modelos ya convertidos con las arquitecturas reales (MLP del alfabeto y GRU del anexo) y la salida esperada para una entrada fija. `docs/plantillas/tfjs-compat.test.ts` (copiado a `apps/web/src/camera/`) los carga con `@tensorflow/tfjs` y compara (tolerancia 1e-4). Si se cambia la versión de TensorFlow o de tensorflowjs, regenerar con `uv run --project ml python ml/smoke_tfjs.py`: si la prueba falla, **no se actualiza** la versión.

---

## 11. Seguridad y privacidad

- **Refresh token**: `secrets.token_urlsafe(32)`; se guarda solo su SHA-256 (`hashlib.sha256`). Cookie `rt`: `httponly=True`, `samesite="lax"`, `secure=True` en producción, `path="/api/auth"`, 7 días. Cada uso lo **rota** (revoca el anterior y emite uno nuevo).
- **Access token**: JWT (PyJWT, HS256) de 15 min con `sub` y `role`; se valida `exp` y el algoritmo explícitamente (`algorithms=["HS256"]`). Secreto de ≥ 32 caracteres validado al arrancar.
- **Contraseñas**: `bcrypt` (costo 12). Longitud de **8 a 72 bytes en UTF-8** (no caracteres: «ñ» ocupa 2 bytes; bcrypt rechaza más de 72 bytes). Comparación con `bcrypt.checkpw`; en login con correo inexistente se compara contra un hash ficticio para no revelar por tiempo qué correos existen.
- **Límite de peticiones** (slowapi): login 5/min por **IP + correo**; registro 10/min por IP; rutas autenticadas 240/min **por usuario** (no por IP: en la universidad muchos equipos comparten la misma IP pública y se bloquearían entre sí). Detrás del proxy de Render, leer la IP real de `X-Forwarded-For` solo desde el proxy de confianza (`--proxy-headers --forwarded-allow-ips`).
- **Validación**: todo cuerpo con Pydantic `model_config = ConfigDict(extra="forbid")` (rechaza campos desconocidos).
- **Cabeceras de seguridad** (middleware propio) y **CSP** compatible con MediaPipe y TensorFlow.js:
  `default-src 'self'; script-src 'self' 'wasm-unsafe-eval'; worker-src 'self' blob:; img-src 'self' data: blob:; media-src 'self' blob:; connect-src 'self'; style-src 'self' 'unsafe-inline'; font-src 'self'` + `X-Content-Type-Options: nosniff`, `Referrer-Policy: strict-origin-when-cross-origin`, `Permissions-Policy: camera=(self)`.
  La CSP se aplica a la SPA y a la API **excepto** `/api/docs` y `/api/redoc` (usan recursos de CDN y solo existen fuera de producción). Archivos de `/media/v`, `/media/p` y `/assets`: `Cache-Control: public, max-age=31536000, immutable`; `index.html` y `manifest.json`: `no-cache`.
- **Autorización**: toda consulta filtra por el `user_id` del token (nunca por un id enviado en el cuerpo). La documentación `/api/docs` solo se publica fuera de producción.
- **SQL**: solo mediante SQLAlchemy con parámetros; prohibido construir SQL con f-strings.
- **Privacidad (Ley 1581 de 2012)**: casilla obligatoria de tratamiento de datos en el registro con enlace a `/privacidad`; la cámara nunca envía ni guarda imágenes. **Autorización escrita de uso de imagen** de las personas que aparecen en los videos.
- **Administrador**: `alas db seed` lo crea a partir de `ADMIN_EMAIL` y `ADMIN_PASSWORD` del `.env` (si existen).

---

## 12. Diagrama UML de clases (dominio y aplicación)

```mermaid
classDiagram
    direction LR
    class Clock { <<Protocol>> +now() datetime }
    class ExerciseEvaluator {
      <<abstract>>
      +type: ExerciseType
      +scored: bool
      +evaluate(payload, answer) bool
      +to_public(payload, catalog) PublicExercise
    }
    class VideoToMeaningEvaluator
    class MeaningToVideoEvaluator
    class MemoryMatchEvaluator
    class ConversationEvaluator
    class ObserveEvaluator
    class ProduceEvaluator
    ExerciseEvaluator <|-- VideoToMeaningEvaluator
    ExerciseEvaluator <|-- MeaningToVideoEvaluator
    ExerciseEvaluator <|-- MemoryMatchEvaluator
    ExerciseEvaluator <|-- ConversationEvaluator
    ExerciseEvaluator <|-- ObserveEvaluator
    ExerciseEvaluator <|-- ProduceEvaluator

    class SessionScore { <<dataclass>> +correct +total +score +passed }
    class RewardPolicy { +calculate(lesson_type, score, previously_passed) Reward }
    class ProgressCalculator { +compute(curriculum, facts) ProgressMap }
    class StreakPolicy { +apply_activity(streak, today) Streak +display(streak, today) int }
    class ReviewScheduler { +schedule(review, correct, today) SignReview }
    class AchievementRule { <<abstract>> +id +nectar_reward +is_satisfied(stats) bool }
    class ExerciseGenerator { +generate(curriculum, signs, conversations) list~Exercise~ }

    class LessonSessionService {
      +start(user_id, lesson_id)
      +answer(user_id, session_id, exercise_id, answer)
      +complete(user_id, session_id) LessonCompletionResult
    }
    class GamificationService { +apply_completion(db, data) +get_stats(user_id) +buy_streak_freeze(user_id) }
    class LessonRepository { <<Protocol>> }
    class ProgressRepository { <<Protocol>> }
    class SqlLessonRepository
    class SqlProgressRepository
    LessonRepository <|.. SqlLessonRepository
    ProgressRepository <|.. SqlProgressRepository

    LessonSessionService --> ExerciseEvaluator
    LessonSessionService --> ProgressCalculator
    LessonSessionService --> SessionScore : crea
    LessonSessionService --> RewardPolicy
    LessonSessionService --> GamificationService
    LessonSessionService --> LessonRepository
    GamificationService --> StreakPolicy
    GamificationService --> AchievementRule
    GamificationService --> ReviewScheduler
    GamificationService --> ProgressRepository
    StreakPolicy --> Clock
```

---

## 13. Patrones GRASP y principios SOLID (solo los necesarios)

| Patrón / principio | Dónde | Beneficio concreto |
|---|---|---|
| **Controlador** (GRASP) | Routers de FastAPI (`app/api/*.py`) | Un punto de entrada por caso de uso. |
| **Experto en información** (GRASP) | `SessionScore`, `StreakPolicy`, cada `ExerciseEvaluator` | Cada uno calcula con sus propios datos. |
| **Creador** (GRASP) | `LessonSessionService` crea `LessonSession` y `SessionScore` | Tiene todos los datos para crearlos. |
| **Fabricación pura** (GRASP) | `RewardPolicy`, `ProgressCalculator`, `ReviewScheduler`, `ExerciseGenerator` | Reglas sin entidad natural, aisladas y fáciles de probar. |
| **Polimorfismo** (GRASP) | `ExerciseEvaluator` (clase abstracta) y su registro; `AchievementRule`; en el front, mapa `type → componente` | Sin cadenas largas de `if/elif` por tipo. |
| **Bajo acoplamiento / alta cohesión** (GRASP) | Paquetes por funcionalidad + `Protocol`s de repositorio | Cambiar SQLAlchemy no toca el dominio. |
| **S** — Responsabilidad única | Servicios separados: sesión, gamificación, repaso, diccionario | Cambios localizados. |
| **O** — Abierto/cerrado | Nuevo tipo de ejercicio o logro = nueva clase registrada | Sin tocar los servicios existentes. |
| **L** — Sustitución de Liskov | Cualquier `ExerciseEvaluator` o `AchievementRule` es intercambiable | Pruebas uniformes. |
| **D** — Inversión de dependencias | Servicios dependen de `Protocol`s (`LessonRepository`, `Clock`) inyectados con `Depends` | Dominio probado sin BD ni reloj real. |

> I (Segregación de interfaces) no se fuerza: los `Protocol`s ya son pequeños.

---

## 14. Catálogo de riesgos y bugs prevenidos

> Cada fila es un error real que suele aparecer en proyectos así. La columna **Prueba** indica cómo se garantiza que no ocurra.

### 14.1 Lógica y datos

| # | Riesgo | Síntoma | Prevención | Prueba |
|---|---|---|---|---|
| B1 | Respuestas correctas visibles en la red | Alguien saca 100 % siempre | `to_public()` quita `correctId` (§7.6) | Unit: ningún ejercicio público contiene `correctId` |
| B2 | Doble envío de «completar» | XP duplicado | `complete` idempotente + transacción + `FOR UPDATE` | API: llamar 2 veces → mismo resultado, XP sumado una vez |
| B3 | Reintentar una pregunta hasta acertar | Puntaje inflado | PK `(session_id, exercise_id)` + `ON CONFLICT DO NOTHING` | API: segunda respuesta no cambia `correct` |
| B4 | Racha calculada en UTC | La racha se rompe a las 7 p. m. | `to_local_day` con `America/Bogota` + `Clock` | Unit: 23:59 / 00:01 Bogotá |
| B5 | Logro otorgado dos veces | Néctar duplicado | PK compuesta + `on_conflict_do_nothing` + `RETURNING` | API: dos completados simultáneos |
| B6 | Progreso guardado como estado | Lecciones bloqueadas al agregar contenido | Estado derivado (§7.4) | Unit |
| B7 | Volver a cargar el contenido borra progreso | Usuarios pierden avances | IDs estables + upsert | `alas db seed` ×2 → mismos conteos, sesiones intactas |
| B8 | Orden aleatorio de nodos/lecciones | Ruta desordenada | `order_by` explícito | API: orden de `/learning-path` |
| B9 | División entre cero en el puntaje | Error 500 | `total == 0 → 100` y validador (≥ 2 con puntaje) | Unit |
| B10 | Redondeo bancario de Python | 2,5 → 2 en puntajes y XP | `round_half_up` con enteros; prohibido `round()` en reglas | Unit: 1/8 → 13, bono de 50 % → 3 |
| B11 | Búsqueda sin tildes rompe la ñ | «año» = «ano» | `normalize_text` protege la ñ | Unit |
| B12 | CSV guardado por Excel en otra codificación | «GrÃ¡cias» en la app | Lectura `utf-8-sig` + detección de mojibake | Unit del lector |
| B13 | Distractor igual a la respuesta | Dos opciones correctas | Generador excluye la correcta y palabras repetidas | Unit sobre todo el contenido |
| B14 | Nodo con pocas señas | Lección vacía o sin distractores | Validaciones §6.6 | Unit |
| B15 | Payload JSON corrupto | Pantalla rota | Pydantic discriminado al leer | Unit |
| B16 | Pestaña abierta toda la noche | Meta diaria inflada | Duración tope 15 min | Unit |
| B17 | Correo con mayúsculas o espacios | Cuenta duplicada o no encontrada | `strip().lower()` en registro y login | API |
| B18 | Categoría sin señas en el filtro | Filtro vacío | Solo categorías con señas | API |
| B19 | Generador no determinista | Los IDs de ejercicios cambian en cada carga | `random.Random(str_semilla)`; **prohibido `hash()`** (cambia en cada ejecución por `PYTHONHASHSEED`) | Unit: dos ejecuciones en procesos distintos → mismo resultado |
| B20 | `%` o `_` en la búsqueda actúan como comodines | Resultados extraños | Escapar comodines en `ILIKE` | API |

### 14.2 Autenticación y red

| # | Riesgo | Prevención | Prueba |
|---|---|---|---|
| B21 | Cookies de terceros bloqueadas | Un solo origen (D1) | E2E en producción local (`alas start-prod`) |
| B22 | Varias peticiones con 401 a la vez → varios refresh → sesión cerrada | Refresh *single-flight* en el cliente | Vitest con 3 peticiones simultáneas |
| B23 | Token de acceso en `localStorage` | Solo en memoria | Revisión de código |
| B24 | Parpadeo de la pantalla de login al recargar | Pantalla de carga hasta resolver `refresh` | E2E |
| B25 | TanStack Query reintenta errores 4xx | `retry` solo para 5xx | Vitest |
| B26 | Rutas de la SPA dan 404 en producción al recargar | FastAPI devuelve `index.html` para rutas que no empiezan por `/api`, `/media`, `/mediapipe`, `/models` o `/assets` | E2E: recargar `/diccionario/gracias` |
| B27 | Contraseña de más de 72 bytes | bcrypt la rechaza (500) | Validar en bytes UTF-8 antes de cifrar | Unit |
| B28 | Enumeración de correos por tiempo de respuesta | Comparación contra hash ficticio | Revisión |

### 14.3 Video y navegador

| # | Riesgo | Prevención |
|---|---|---|
| B29 | El navegador no reproduce el video | H.264 `yuv420p` + `muted` + `playsInline` |
| B30 | `play()` lanza error por reproducción automática | `.catch()` + botón de reproducir |
| B31 | Video tarda en empezar | `+faststart`, clips de 2–4 s, 720p, precarga del siguiente |
| B32 | Nombre de archivo con mayúsculas o tildes no coincide | El comando compara contra los slugs y sugiere el correcto |
| B33 | En 1366×768 el botón «Comprobar» queda fuera de la pantalla | Video máx. 360 px y botón fijo (§9.7) |
| B34 | Efectos dobles en desarrollo (React StrictMode) | Idempotencia en el servidor y *singletons* |
| B35 | Videos servidos sin soporte de rangos (`Range`) | No se puede adelantar ni repetir bien | `StaticFiles` de Starlette soporta `Range`; prueba que responde `206` |

### 14.4 Cámara y modelo

| # | Riesgo | Prevención |
|---|---|---|
| B36 | Discrepancia entre datos de entrenamiento e inferencia | Los vectores se calculan **solo** en el navegador; Python entrena sobre ellos (D11) |
| B37 | Siempre reconoce una letra | Clase `NINGUNA` + umbral 0,70 + suavizado |
| B38 | Funciona con quien entrenó, falla con otros | Datos de ≥ 3 personas; validación por persona |
| B39 | MediaPipe falla por timestamps repetidos | `performance.now()` estrictamente creciente |
| B40 | La luz de la cámara sigue encendida | *Cleanup* completo (§10.4) |
| B41 | La CSP bloquea WASM | `'wasm-unsafe-eval'` y `worker-src blob:` |
| B42 | Bundle inicial pesado por tfjs | Carga diferida de las rutas de cámara |
| B43 | El conversor a TensorFlow.js falla con Keras 3 | Entorno `ml/` fijado a TensorFlow 2.15 + Python 3.11; alternativa en Colab |
| B44 | El modelo exportado no coincide con el orden de etiquetas | `labels.json` y `meta.json` se generan en el mismo script que exporta el modelo; prueba de carga en el navegador |

### 14.5 Entorno y despliegue

| # | Riesgo | Prevención |
|---|---|---|
| B45 | `ZoneInfoNotFoundError` en Windows | Dependencia `tzdata` |
| B46 | Versión de Python distinta entre integrantes | `.python-version` + `uv` instala la versión correcta |
| B47 | Migración autogenerada incompleta (Alembic) | Revisar cada migración; prueba que aplica todas las migraciones sobre una BD vacía y luego `alembic check` |
| B48 | Finales de línea de Windows rompen scripts | `.gitattributes` `eol=lf` |
| B49 | Falta una variable de entorno | `pydantic-settings` valida al arrancar con mensaje claro |
| B50 | El servidor gratuito se «duerme» y la demo tarda ~1 min | Demo principal en local; abrir el despliegue 5 min antes; video de respaldo |
| B51 | Puerto 5432 ocupado por otro PostgreSQL | `docker-compose` usa el puerto 5433 |
| B52 | Tipos de la API desactualizados en el frontend | `alas check` compara con los generados (§8.4) |
| B53 | Conexiones agotadas en Neon gratuito | `pool_size=5`, `pool_pre_ping=True`, `pool_recycle=300` |

### 14.6 Riesgos encontrados en la revisión técnica (v3.1)

| # | Riesgo | Prevención | Prueba |
|---|---|---|---|
| B54 | La respuesta correcta se deduce del JSON porque el ID del video coincide con el de una opción | Tokens opacos (D20) y rutas de video por contenido (D19) | Unit: ningún valor público de opción es un slug ni un `signId` |
| B55 | El navegador muestra el video de relleno viejo después de cargar el real (caché) | Nombres por contenido + `immutable` (D19) | Unit: cambiar el video cambia la ruta |
| B56 | En producción todas las señas aparecen como «de relleno» (o ninguna) porque la caché local no existe | `is_placeholder` sale del manifiesto versionado | Script: seed sin `raw/` conserva los valores |
| B57 | Faltan videos en el despliegue | Videos procesados versionados en git | Revisión del build Docker |
| B58 | El módulo 4 (sin señas) hace fallar la validación o genera lecciones vacías | Los módulos no publicados no generan lecciones | Unit del generador |
| B59 | Lecciones de 2 preguntas: un error reprueba | Mínimo 4 ejercicios con puntaje por lección | Unit de validación |
| B60 | El deletreo del alfabeto no tiene formato definido | Tipo `SPELLING` y lista `spelling` en el YAML | Unit del generador y evaluador |
| B61 | `SET TRANSACTION ISOLATION LEVEL` falla porque la sesión ya hizo consultas | Sesión SERIALIZABLE propia (D21) | API: completar con usuario autenticado |
| B62 | Las pruebas de API con «transacción que se revierte» no ven datos desde la sesión SERIALIZABLE | Estrategia de pruebas por truncado (§15) | La suite de API pasa |
| B63 | «Completar» una sesión vacía suma racha sin practicar | `SESSION_INCOMPLETE` | API |
| B64 | En la universidad varios estudiantes comparten IP y el límite global los bloquea | Límite por usuario en rutas autenticadas | Revisión |
| B65 | `uv run` dentro de Docker intenta instalar dependencias de desarrollo al arrancar | `UV_NO_SYNC=1` y binarios de `.venv` | Build y arranque del contenedor |
| B66 | `ruff` (reglas S) marca cada `assert` de las pruebas y bloquea `alas check` | `per-file-ignores` para pruebas y comandos con subprocess (§19.3) | `alas check` en la fase 0 |
| B67 | `mypy --strict` falla con librerías sin tipos (slowapi, imageio-ffmpeg) | `ignore_missing_imports` solo para esos módulos (§19.3) | `alas check` |
| B68 | La base `alas_test` no existe (Docker solo crea una base) | `docker/init-test-db.sql` | `alas db up` + pytest |
| B69 | `uv run alas` falla porque `apps/api` no es un paquete instalable | `[build-system]` y paquete `app` declarados (§19.3) | `uv run alas --help` |
| B70 | La aplicación no arranca en desarrollo sin `.env` (y la IA no puede crearlo) | Valores por defecto para desarrollo; `.env` obligatorio solo en producción (§19.4) | `alas dev` sin `.env` |
| B71 | La ñ de la búsqueda deja de protegerse si un editor normaliza el archivo | Escapes `\u0303`/`\u00f1` explícitos en el código | Unit «Año» → «año» |
| B72 | Swagger (`/api/docs`) no carga en desarrollo por la CSP | CSP sin aplicar a `/api/docs` | Manual |

### 14.7 Riesgos de las mejoras v3.2

| # | Riesgo | Prevención | Prueba |
|---|---|---|---|
| B73 | El modelo GRU entrenado en Python **no carga en el navegador** («GRUCell does not support reset_after»): Keras usa `reset_after=True` por defecto | `GRU(..., reset_after=False)` | Vitest `tfjs-compat` (verificado el 30/10/2026) |
| B74 | `import tensorflowjs` falla con `No module named 'pkg_resources'` en un entorno creado con uv | `setuptools<81` en `ml/pyproject.toml` | `ml/smoke_tfjs.py` |
| B75 | El modelo se copia con los pesos renombrados (`weights.bin`) y no carga | Servir la carpeta tal cual la genera el conversor | Vitest `tfjs-compat` |
| B76 | Versiones distintas de `tensorflowjs` (Python) y `@tensorflow/tfjs` (navegador) | Ambas fijadas a 4.22.0 | Vitest `tfjs-compat` |
| B77 | Tiempos de la BD y del `Clock` mezclados: duración negativa; imposible probar expiración, vidas o la demo | D22 | API con reloj simulado |
| B78 | El cliente declara «acerté» en el repaso y suma racha y vidas sin practicar | Repaso evaluado por el servidor (D23) | API: el repaso usa tokens |
| B79 | Repasar varias veces el mismo día para inflar la racha o ganar vidas infinitas | La cola solo trae señas vencidas y al terminar quedan para otro día; 409 `NO_REVIEWS_DUE` | API |
| B80 | Un reintento de red descuenta dos vidas por el mismo error | Descuento solo si la inserción ocurrió (`RETURNING`) | API: repetir la respuesta |
| B81 | Usuario atascado con 0 vidas y sin repasos | L1 y repaso nunca piden vidas; recarga por tiempo y por néctar; la lección empezada se puede terminar | API + E2E manual |
| B82 | Las vidas no se recargan porque el servidor gratuito no ejecuta tareas programadas | Cálculo derivado de `hearts_updated_at` (D24) | Unit |
| B83 | La demo se siembra días antes y la racha llega rota a la sustentación | `seed-demo` calcula fechas relativas a hoy y se ejecuta el mismo día (§17.3) | API con reloj simulado |
| B84 | El usuario de demostración queda en producción con una contraseña conocida | `seed-demo` exige `--allow-production` y `DEMO_PASSWORD` en producción | Unit de la CLI |
| B85 | CI en rojo desde el primer push porque aún no existe el código | Paso que detecta si ya existe la fase 0 | Primer push |
| B86 | Dígrafos (CH, LL, RR) rompen un reparto fijo por letras o el deletreo | Reparto por posición y separación por coincidencia más larga | Unit del generador |
| B87 | Una letra con movimiento entra al modelo estático y nunca se reconoce bien | Columna `motion`; `content check` y `train_static.py` la rechazan | Unit de validación |
| B88 | Las vidas llegan a 0 en medio de una lección y el usuario no puede terminarla | `answer` y `complete` nunca revisan vidas; solo `start` | API |
| B89 | La prueba E2E no puede «responder bien» porque las opciones ya no revelan la respuesta, y alguien agrega un «modo prueba» a la API que filtra respuestas | La prueba traduce video ↔ palabra con `manifest.json` y `signs.csv` (§15) | E2E |
| B90 | `numero-1.jpg` se interpreta como el cuadro 1 de una seña «numero» | Cuadros con doble guion bajo; los slugs no admiten `_` | Unit del emparejamiento de nombres |
| B91 | Fotos de celular aparecen de lado | `ImageOps.exif_transpose` | Unit con imagen con EXIF de rotación |
| B92 | Fotos de 12 MP agotan la memoria o hacen lento el proceso | Reducir con `thumbnail` antes de procesar | Unit con imagen de 4000×3000 |
| B93 | ffmpeg falla con medidas impares en `yuv420p` | Lienzo fijo de 1280×720 | Unit con imagen de 1001×777 |
| B94 | Fotos `.heic` del iPhone no abren | Error claro con instrucción para exportar a JPG | Unit |
| B95 | Una seña con video y con imágenes produce resultados distintos según el orden de lectura | Prioridad fija: video > imágenes > relleno | Unit |

---

## 15. Estrategia de pruebas

| Nivel | Herramienta | Qué cubre | Meta |
|---|---|---|---|
| Unitarias de dominio | **pytest** | §7 completo + generador + normalización | **≥ 95 % de líneas** en `app/domain` (`pytest-cov --cov-fail-under=95` sobre ese paquete) |
| Arquitectura | pytest + `ast` | `app/domain` no importa `fastapi` ni `sqlalchemy` | Siempre |
| Contenido | pytest | Lector CSV, validaciones, emparejamiento de nombres de archivo | Todas las reglas de §6.6 |
| API | pytest + `TestClient` + BD de prueba `alas_test`: el contenido se carga una vez por ejecución y **después de cada prueba se truncan las tablas de usuario** (`TRUNCATE … RESTART IDENTITY CASCADE`); no se usa «transacción que se revierte» porque el cierre de lección abre su propia sesión (D21) | Auth, sesiones (B1–B5, B17, B27), diccionario | Flujos principales y errores |
| Componentes | Vitest + Testing Library | `SelectMeaningActivity`, `SignVideoPlayer` (error), guardas, cliente API | Casos de error visibles |
| E2E | **Playwright para Python** (Chromium y Firefox, ventana 1366×768) | Ver abajo | Pasa en local con `alas start-prod` |

Antes de la primera ejecución E2E: `uv run playwright install chromium firefox` (lo hace `alas e2e` si faltan los navegadores).

**Flujo E2E obligatorio:** visitante → intro (6 tarjetas) → mini-quiz → registro → ruta (solo M1-N1-L1 disponible) → completar L1 respondiendo bien → celebración con XP > 0 y racha 1 → L2 disponible → diccionario: buscar «GRACÍAS» → ficha «Gracias» → favorito → recargar la página → la sesión sigue activa.

Convención: elementos interactivos con `data-testid` (`lesson-option-<n>` con la posición 1–4, nunca el slug, porque la opción ya no lo contiene; `check-answer`, `continue`, `node-<id>`, `hearts`).

**Cómo responde bien la prueba E2E sin que la API revele la respuesta:** la prueba lee `media/manifest.json` (ruta del video → slug) y `content/signs.csv` (slug → palabra) desde el repositorio; con eso traduce el video que ve a su palabra y elige la opción correcta (o, al revés, la palabra a su video). **Prohibido** agregar a la API un «modo prueba» que devuelva respuestas.

**Pruebas de API con reloj simulado:** la dependencia `get_clock` se sustituye en las pruebas por un `FakeClock` que se puede adelantar (`clock.advance(hours=4)`), gracias a D22.

### 15.1 Integración continua (GitHub Actions)

`.github/workflows/ci.yml` (ya incluido en el kit) se ejecuta en cada push a `main`, en cada pull request y a mano:
- **`alas check`** con PostgreSQL 16 como servicio (puerto 5433, base `alas_test`) y `alas content check --skip-raw`.
- **E2E** (Playwright, Chromium y Firefox) solo en `main` o a mano, porque tarda más.
- Mientras no exista el código de la fase 0, el flujo solo muestra un aviso (no falla).
- Las pruebas de API aplican las migraciones a `alas_test` al inicio (fixture de sesión), así CI no necesita pasos extra.
- El repositorio debe estar en GitHub. Si el profesor lo pide, la insignia `![CI](…/actions/workflows/ci.yml/badge.svg)` va en el `README.md`.

---

## 16. Fases de implementación

> Tiempo estimado con 2–3 h diarias por persona en un equipo de 3. Las fases 1 y 2 hacen que el resto sea predecible: **no las saltes**.

| Fase | Entregable | Secciones | Criterios de aceptación (verificar a mano) |
|---|---|---|---|
| **0. Base** (día 1–2) | Workspace uv + `apps/api` (FastAPI, `/api/health`, configuración, errores, CLI `alas`), `apps/web` (Vite + React + Tailwind con proxy), Docker (PostgreSQL :5433), Alembic, ruff/mypy/pytest, ESLint/Vitest, `CLAUDE.md`, `alas check`, `alas dev`, **prueba de compatibilidad TensorFlow.js**, **CI en GitHub** | §2, §3, §4, §10.5, §15.1, §19 | `alas dev` levanta ambos; `http://localhost:5173/api/health` → `{ok:true, db:true}`; `alas check` en verde; CI en verde en GitHub. |
| **1. Dominio** (día 2–4) | Todo §7 con pruebas primero + prueba de arquitectura | §7 | Cobertura ≥ 95 %; todos los casos de §7 existen como pruebas. |
| **2. Contenido** (día 4–6) | `content/` prellenado, modelos SQLAlchemy + migración, comandos §6.4, generador §6.7, seed idempotente | §5, §6 | `alas content all` sin errores; 109 videos de relleno; `alas db seed` dos veces → mismos conteos. |
| **3. Auth** (día 6–8) | Registro, login, refresh rotativo, logout, dependencias de seguridad, `alas gen-api`, cliente API en el front, páginas | §8.2, §8.4, §9.2, §11 | Registro → `/aprender`; recargar mantiene la sesión; logout invalida; 6 intentos → 429. |
| **4. Ruta** (día 8–9) | `/learning-path`, layout de escritorio, nodos en zigzag, M4 «Próximamente», Tomi | §7.4, §9 | Usuario nuevo: solo M1-N1-L1 disponible. |
| **5. Lecciones** (día 9–13) | Sesiones de lección, 4 actividades, 7 tipos de ejercicio, reproductor, `complete`, descuento de vidas | §7.2–7.6, §7.10, §8.3, §9.3–9.4 | Completar L1 desbloquea L2; doble clic no duplica XP; respuestas no visibles en DevTools → Network; un error en L2 resta una vida. |
| **6. Gamificación** (día 13–15) | XP, néctar, racha, protector, logros, celebración, vidas (contador, modal, recarga) | §7.3, §7.5, §7.9, §7.10, §9.6 | Celebración con valores del servidor; logros una sola vez; con 0 vidas L2 se bloquea y L1 no. |
| **7. Progreso y repaso** (día 15–16) | `/progreso` (Recharts), historial, unidades, sesión de repaso evaluada por el servidor (`/repaso`) | §7.7, §8.2, §8.5 | Fallar una seña la pone en «por repasar»; el repaso cuenta para la racha y no se puede repetir el mismo día. |
| **8. Diccionario** (día 16–18) | Búsqueda, filtros, ficha, favoritos, sugerencias | §7.8, §8.2 | «GRACÍAS» → Gracias; «grasias» sugiere Gracias. |
| **9. Intro** (día 18–19) | `/bienvenida`, mini-quiz, `introCompleted` | §6.3 | Visitante nuevo → intro → registro → «Primer aleteo». |
| **10. Cámara** (día 19–24) | `alas camera-assets`, reconocedor con `MockClassifier`, `/camara`, colector, **entrenamiento en `ml/`**, modelo con 5–10 letras | §10 | Detecta letras entrenadas; NINGUNA sin mano; la cámara se apaga al salir. |
| **11. Cierre** (día 24–28) | Revisión en 1280×720 / 1366×768 / 1920×1080, pantalla «solo computador», accesibilidad, E2E (Playwright Python), CSP, Dockerfile, despliegue, `README.md`, **usuario de demostración**, checklist de demo | §11, §14, §15, §17 | E2E verde; Lighthouse accesibilidad ≥ 90; app desplegada con HTTPS; `alas db seed-demo` deja la demo lista. |

**En paralelo (equipo de contenido):** semana 1 **validar con el intérprete** `docs/validacion-interprete.md` (letras, movimiento, dígrafos, palabras) y grabar M1; semana 2 grabar M2; semana 3 grabar M3; semana 3–4 grabar muestras del alfabeto (solo letras `static`) para la cámara. Ver §18.

---

## 17. Despliegue y día de la demo

### 17.1 Imagen Docker (un solo servicio)

```dockerfile
# Etapa 1: compilar la SPA
FROM node:22-slim AS web
WORKDIR /web
COPY apps/web/package*.json ./
RUN npm ci
COPY apps/web/ ./
RUN npm run build

# Etapa 2: API en Python que sirve la SPA y los archivos
FROM python:3.12-slim
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv
WORKDIR /app
COPY pyproject.toml uv.lock ./
COPY apps/api ./apps/api
RUN uv sync --frozen --no-dev --package alas-api      # nombre del paquete de apps/api/pyproject.toml
COPY content ./content
COPY --from=web /web/dist ./apps/web/dist
ENV PYTHONUNBUFFERED=1 APP_ENV=production UV_NO_SYNC=1 PATH="/app/.venv/bin:$PATH" \
    CONTENT_DIR=/app/content MEDIA_DIR=/app/apps/web/dist/media WEB_DIST_DIR=/app/apps/web/dist
CMD ["sh", "-c", "alembic -c apps/api/alembic.ini upgrade head && alas db seed && uvicorn app.main:app --app-dir apps/api --host 0.0.0.0 --port ${PORT:-8000} --proxy-headers --forwarded-allow-ips='*'"]
```
(Fijar la etiqueta de la imagen de `uv` a una versión concreta en lugar de `latest`.)

`ml/` y `.github/` no entran en la imagen (no se copian).

Notas: los comandos se ejecutan desde `.venv/bin` (no con `uv run`, que intentaría sincronizar dependencias al arrancar); `alembic.ini` usa `script_location = %(here)s/alembic` y `env.py` toma la URL de la configuración de la app, no del `.ini`; Vite copia `public/` dentro de `dist/`, por eso `MEDIA_DIR` apunta a `dist/media`.

### 17.2 Producción
1. Base de datos en **Neon** (copiar `DATABASE_URL` con `sslmode=require`, formato `postgresql+psycopg://…`).
2. **Render** → Web Service tipo **Docker** desde el repositorio; variables de §19.4 con `APP_ENV=production`.
3. Verificar `https://<app>/api/health`.

### 17.3 Checklist del día de la sustentación
- [ ] Demo **principal en local** (`alas start-prod`) con la base de datos local ya sembrada.
- [ ] **El mismo día**, ejecutar `alas db seed-demo --reset` (§17.4) e iniciar sesión con el usuario de demostración para comprobar racha 5, repaso pendiente y M2-N1-L1 disponible (y vidas llenas: los errores de ayer ya se recargaron). Tener otro correo listo para mostrar el registro.
- [ ] Abrir la versión desplegada 5 minutos antes (el plan gratuito «duerme» el servidor).
- [ ] Probar la cámara en el computador y el lugar de la presentación (luz de frente, fondo liso).
- [ ] Video grabado de la demo completa como respaldo.
- [ ] Ventanas y notificaciones cerradas; zoom del navegador al 110–125 %.

### 17.4 Usuario de demostración (`alas db seed-demo`)

Deja una cuenta lista para mostrar la app sin jugar 20 minutos antes de la sustentación.
- **Usa los servicios reales** (`LessonSessionService`, `ReviewService`) con un reloj simulado, respondiendo con las respuestas que conoce el servidor. Así la demo nunca queda inconsistente con las reglas (D22).
- **Fechas relativas a hoy** (hora de Bogotá, 10:00 de cada día):
  - hace 5 días: M1-N1 L1–L4 con 100 % en el reto (nodo dorado);
  - hace 4 días: M1-N2 L1–L4;
  - hace 3 días: M1-N3 L1–L4;
  - hace 2 días: M1-N4 L1–L2 y un repaso;
  - ayer: M1-N4 L3–L4 con 3 errores en 3 letras (aprueba).
- **Resultado hoy:** módulo 1 completo, racha 5 «en riesgo» (Tomi invita a practicar), repaso pendiente que incluye las 3 letras falladas ayer (más las que el repaso espaciado haya vencido, hasta 15), M2-N1-L1 disponible para mostrar una lección en vivo (la racha sube a 6), logros FIRST_FLAP, FIRST_LESSON, STREAK_3, NODE_DONE, GOLDEN_NODE y MODULE_1, vidas llenas.
- Credenciales: `DEMO_EMAIL` (por defecto `demo@alasdesenas.co`) y `DEMO_PASSWORD` (en desarrollo, por defecto `demo-alas-2026`). El usuario queda con `is_demo = true`.
- Si el usuario ya existe: sin `--reset` termina con un mensaje; con `--reset` lo borra (con todo su progreso) y lo vuelve a crear. Nunca toca otros usuarios.
- **En producción** (`APP_ENV=production`) se niega salvo que se pase `--allow-production` **y** exista `DEMO_PASSWORD` (B84).
- Prueba de API: con un `FakeClock` fijo, el comando deja el estado descrito (racha 5 con `atRisk`, 16 lecciones de M1 aprobadas, M2-N1-L1 disponible, las 3 letras falladas en la cola, 5 vidas, los 6 logros); ejecutarlo dos veces con `--reset` da el mismo resultado.

---

## 18. Guía de grabación de videos (para el equipo)

> Si no es posible grabar video, ver el **plan B con fotos** al final de esta sección (§18.1).

> Esta es la única tarea que no puede hacer la IA. Con esta guía, cada video entra a la app sin edición.

**Equipo:** celular en trípode o apoyado firme, **horizontal (16:9)**, 1080p o 720p, 30 fps.
**Encuadre:** desde la cintura hasta un poco arriba de la cabeza; manos siempre dentro del cuadro; cara visible (la expresión facial es parte de la LSC).
**Fondo y ropa:** pared lisa clara o azul; camiseta lisa de color oscuro y sin estampados; sin anillos ni pulseras llamativas.
**Luz:** de frente (ventana o lámpara detrás de la cámara), sin contraluz.
**Cada clip:** 0,5 s quieto → la seña completa → 0,5 s quieto. Duración total 2–4 s. Una seña por archivo.
**Mismo intérprete y mismo lugar** para todo un módulo (coherencia visual).
**Nombre del archivo:** exactamente el `slug` de `signs.csv` (`gracias.mp4`, `buenos-dias.mp4`). Si te equivocas, `alas content videos` te dice cuál era el correcto.
**Flujo de una sesión de grabación (≈ 3 h por módulo):**
1. Imprimir la lista de slugs del módulo (`alas content check --module M1 --list`).
2. Grabar en orden, marcando cada slug grabado.
3. Pedir al intérprete la descripción de "cómo se hace" y anotarla en la columna `how_to`.
4. Copiar los videos a `content/videos/raw/` y ejecutar `alas content all`.
5. Revisar en la app; regrabar los que se vean mal.

**Autorización:** cada persona que aparece en los videos firma una autorización de uso de imagen para el proyecto (Ley 1581 de 2012).

### 18.1 Plan B: fotos en lugar de video (§6.4.1)

**Mismas condiciones** de encuadre, fondo, ropa, luz y autorización que para el video; celular **horizontal**.
- **Letras estáticas y números:** 1 foto con la mano en la posición final y quieta → `letra-a.jpg`.
- **Señas con movimiento:** 2 fotos (posición inicial y final) o 3 si el recorrido cambia de dirección → `gracias__1.jpg`, `gracias__2.jpg`. Usar ráfaga o temporizador para que la persona no se mueva entre fotos y el encuadre sea idéntico.
- Si el movimiento no se entiende con las fotos, se puede dibujar una flecha sobre la foto con cualquier editor antes de copiarla (opcional).
- **Escribir siempre el `how_to`** de las señas con movimiento («la mano abierta sale del mentón hacia adelante»): con fotos, el texto es indispensable.
- Ritmo: unas 109 señas en una tarde. Copiar a `content/videos/raw/` y ejecutar `alas content all`, igual que con videos.

---

## 19. Plantillas

### 19.1 `CLAUDE.md` (ya incluido en el kit; este es su resumen)

```markdown
# Alas de Señas — reglas del repositorio
- Fuente de verdad: docs/especificacion.md (v3.2). Leer la sección de la fase antes de codificar.
- Lenguajes: Python 3.12 en todo lo que no corre en el navegador; TypeScript SOLO en apps/web.
- Comandos (desde la raíz): uv run alas dev · check · gen-api · db up|migrate|seed|reset · content placeholders|videos|check|all · camera-assets · e2e · start-prod
- Reglas de negocio SOLO en apps/api/app/domain (Python puro, con pruebas). Sin imports de fastapi/sqlalchemy ahí.
- Prohibido: Any explícito, type: ignore sin justificación, any/@ts-ignore en TS, saltar o borrar pruebas,
  round() en reglas de negocio, hash() para semillas, tokens en localStorage, enviar respuestas correctas o IDs de seña en las opciones,
  SQL con f-strings, interfaces TS escritas a mano para respuestas de la API (usar api-types.ts generado).
- Toda consulta ordenada usa order_by explícito. Toda escritura de completado va en una transacción SERIALIZABLE.
- Fechas de negocio con to_local_day(America/Bogota) y Clock inyectado; nunca datetime.now() en el dominio.
- Textos de UI en español (Colombia); código en inglés; JSON de la API en camelCase.
- Al terminar una fase: alas check en verde + docs/PROGRESS.md + commit "feat(fase-N): ...".
- Decisiones nuevas → docs/DECISIONES.md.
```

### 19.2 `docs/PROGRESS.md`

```markdown
## Fase N — <nombre>
- Plan: ...
- Hecho: ...
- Verificación manual: ✅/❌ (detalle)
- Pendiente / riesgos: ...
```

### 19.3 CLI `alas` (`apps/api/app/cli.py`, Typer)

| Comando | Qué hace |
|---|---|
| `alas dev` | Inicia `uvicorn --reload` (puerto 8000) y `npm run dev` de `apps/web` (puerto 5173) como subprocesos; Ctrl+C detiene ambos. Funciona igual en Windows, Mac y Linux. |
| `alas check` | `ruff check` · `ruff format --check` · `mypy --strict app` · `pytest` (sin E2E) · `npm run lint` · `npm run typecheck` · `npm run test -- --run` · verificación de tipos de la API (§8.4). Se detiene en el primer fallo y muestra cuál. |
| `alas gen-api` / `alas gen-api --check` | Exporta `openapi.json` y genera `apps/web/src/lib/api-types.ts`; con `--check` no escribe nada y sale con código 1 si el archivo versionado está desactualizado (lo usa la compuerta de calidad del harness). |
| `alas db up` / `migrate` / `seed` / `reset` | Docker Compose arriba · `alembic upgrade head` · carga de contenido idempotente · borrar y recrear la BD de desarrollo (pide confirmación). |
| `alas db seed-demo [--reset] [--allow-production]` | Usuario de demostración (§17.4). |
| `alas content placeholders` / `videos` / `check` / `all` | Pipeline de contenido (§6.4). |
| `alas camera-assets` | Copia el WASM de MediaPipe desde `apps/web/node_modules/@mediapipe/tasks-vision/wasm` a `apps/web/public/mediapipe/wasm/` y descarga los modelos `.task`. |
| `alas e2e` | Construye, arranca en modo producción contra la BD de prueba y ejecuta Playwright (Python). |
| `alas start-prod` | `npm run build` + `uvicorn` sin recarga sirviendo la SPA. |

Configuración raíz (`pyproject.toml`):
```toml
[tool.uv.workspace]
members = ["apps/api"]
exclude = ["ml"]          # ml/ es un proyecto aparte (Python 3.11 + TensorFlow)

[tool.ruff]
line-length = 100
target-version = "py312"
[tool.ruff.lint]
select = ["E", "F", "I", "B", "UP", "SIM", "RUF", "DTZ", "S"]   # DTZ: prohíbe datetimes sin zona horaria

[tool.ruff.lint.per-file-ignores]
"apps/api/tests/**" = ["S101", "S105", "S106"]          # assert y contraseñas de prueba
"apps/api/app/content/**" = ["S603"]                     # subprocess con lista de argumentos (ffmpeg)
"apps/api/app/cli.py" = ["S603", "S607"]                 # la CLI lanza uvicorn, npm y docker

[tool.mypy]
strict = true
plugins = ["pydantic.mypy"]

[[tool.mypy.overrides]]
module = ["slowapi.*", "imageio_ffmpeg.*"]   # sin tipos publicados; ampliar solo con justificación en DECISIONES.md
ignore_missing_imports = true
```

`apps/api/pyproject.toml` (lo mínimo para que `uv run alas` funcione):
```toml
[project]
name = "alas-api"
requires-python = ">=3.12,<3.13"
# dependencies = [...]  (§3)

[project.scripts]
alas = "app.cli:app"

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["app"]
```

### 19.4 `.env.example`

```
# En desarrollo TODAS tienen valor por defecto (la app arranca sin .env). En producción (APP_ENV=production)
# son obligatorias DATABASE_URL y JWT_SECRET, y JWT_SECRET no puede ser el valor por defecto de desarrollo.
APP_ENV=development
DATABASE_URL=postgresql+psycopg://alas:alas@localhost:5433/alas_de_senas
DATABASE_URL_TEST=postgresql+psycopg://alas:alas@localhost:5433/alas_test
JWT_SECRET=cambia-esto-por-un-texto-aleatorio-de-32-caracteres-o-mas
ACCESS_TOKEN_MINUTES=15
REFRESH_TOKEN_DAYS=7
APP_TIMEZONE=America/Bogota
ADMIN_EMAIL=
ADMIN_PASSWORD=
HEARTS_ENABLED=true
DEMO_EMAIL=demo@alasdesenas.co
DEMO_PASSWORD=
# Rutas (por defecto relativas a la raíz del repositorio)
CONTENT_DIR=content
MEDIA_DIR=apps/web/public/media
WEB_DIST_DIR=apps/web/dist
```

### 19.5 Instrucciones sugeridas para Claude Code, fase por fase

```
Fase 0:  /fase 0   (o: "Lee CLAUDE.md y docs/specs/; implementa el Grupo 0 de docs/specs/tasks.md siguiendo §0.2.")
Fase N:  "Implementa la Fase N. Relee las secciones que cita. Escribe primero las pruebas. Termina solo cuando cumplas §0.3."
Si algo falla: "Muéstrame el error completo, explica la causa raíz y corrígela sin desactivar pruebas."
Revisión:  "Revisa el código de la fase N contra el catálogo §14 y dime qué riesgos no están cubiertos."
```

### 19.6 Requisitos previos en cada computador

- **Python**: no hace falta instalarlo a mano; instalar **uv** (una línea desde su sitio oficial) y ejecutar `uv sync` (descarga Python 3.12).
- **Node.js 22 LTS** (solo para compilar el frontend).
- **Docker Desktop** (PostgreSQL).
- **Git** y **Visual Studio Code** con las extensiones de Python, Ruff y ESLint.

---

## 20. Consejos finales

1. **Consigan al intérprete la primera semana.** Es lo único que puede retrasar el proyecto: todo lo demás está diseñado para avanzar sin videos.
2. **Pidan a Claude Code una fase a la vez** y revisen la verificación manual ustedes mismos antes de seguir.
3. **Hagan commit al final de cada fase.** Si una fase sale mal, se puede volver al último punto estable.
4. **No agreguen funciones nuevas antes de la fase 11.** Las ideas nuevas van a una lista "después de la sustentación".
5. **La cámara es la parte más arriesgada**: está al final a propósito y tiene modo simulado. Si no alcanza el tiempo, se presenta con 5 letras y como beta.
6. **Sean honestos en la sustentación** con la precisión de la cámara y con qué contenido está validado por el intérprete.

# 🐦 Alas de Señas

[![CI](https://github.com/rcamilorodriguez1/alas-de-senas/actions/workflows/ci.yml/badge.svg)](https://github.com/rcamilorodriguez1/alas-de-senas/actions/workflows/ci.yml)

Plataforma web para aprender **Lengua de Señas Colombiana (LSC)** con lecciones cortas, rachas,
logros y la compañía de **Tomi**, un colibrí. Tiene una **cámara beta** que reconoce algunas
señas directamente en el navegador.

Proyecto académico de Ingeniería de Sistemas. Está pensada para portátil y computador
(Chrome, Edge y Firefox, de 1280×720 a 1920×1080); no está hecha para celulares.

> La cámara es una ayuda para practicar, no un evaluador oficial de LSC. Las señas y sus
> variantes las valida una persona competente en LSC ([`docs/validacion-interprete.md`](docs/validacion-interprete.md)).

## Qué hace

| Área | Qué incluye |
|---|---|
| **Ruta de aprendizaje** | 4 módulos (Fundamentos, Personas y vida cotidiana, Entorno y necesidades, Primeras conversaciones; el 4.º aún sin publicar), con niveles y lecciones que se desbloquean en orden. |
| **Lecciones** | Primero observar, después recordar. Hay 7 tipos de ejercicio: observar, de video a significado, de significado a video, memoria, conversación, deletreo y hacer la seña (con la cámara o con autoevaluación). |
| **Gamificación** | XP, racha diaria, vidas que se recuperan con el tiempo, néctar, logros y una tienda con accesorios para Tomi. |
| **Progreso y repaso** | Estadísticas por día y repaso espaciado de las señas falladas. El servidor evalúa el repaso. |
| **Diccionario** | 109 señas con búsqueda y filtro por categoría, cada una con video o imagen. |
| **Cámara beta** | Alfabeto manual (24 letras estáticas) y números del 1 al 5 con una mano. Además, 5 señas con movimiento: hola, adiós, por favor, de nada y perdón. |
| **Administración** | Colectores de muestras para la cámara e importador de datasets externos, con registro de licencias. |
| **Privacidad** | Casilla de tratamiento de datos (Ley 1581 de 2012), página de privacidad y derechos sobre los datos desde el perfil. |

### La cámara no envía video

El video se analiza **en el navegador** con MediaPipe y TensorFlow.js. Al servidor solo llega
qué seña se reconoció y con qué confianza; nunca la imagen.

| Modelo | Qué reconoce | Datos de entrenamiento |
|---|---|---|
| `lsc-alfabeto` (una mano) | 24 letras estáticas, números 1–5 y «ninguna» | LSC70 (fotos) + LSC-54 (videos), 88 personas |
| `lsc-gestos` (dos manos y hombros, 30 cuadros) | hola, adiós, por favor, de nada, perdón y «ninguna» | LSC-54, 18 personas; validación cruzada por persona 89,7 % |

Las letras con movimiento (J, Ñ, Z) y las señas que aún no tienen modelo siguen con
autoevaluación. El entrenamiento está en [`ml/`](ml/) y se hace en Google Colab
(`ml/notebooks/`).

## Tecnología

| Parte | Carpeta | Tecnología |
|---|---|---|
| Frontend | `apps/web` | React 19, TypeScript, Vite, Tailwind, TanStack Query, MediaPipe, TensorFlow.js |
| API | `apps/api/app/api`, `apps/api/app/schemas` | FastAPI, Pydantic (JSON en camelCase) |
| Reglas de negocio | `apps/api/app/domain`, `apps/api/app/services` | Python 3.12 puro, sin FastAPI ni SQLAlchemy |
| Base de datos | `apps/api/app/infra`, `apps/api/alembic` | PostgreSQL 16 (Docker), SQLAlchemy, Alembic |
| Modelos | `ml/` | Python 3.11, TensorFlow 2.15 (aparte del resto) |

Cada parte solo habla con la siguiente. Los tipos TypeScript de la API se generan desde la propia
API (`uv run alas gen-api`), así que el frontend y el backend no se desalinean. El detalle está en
[`docs/ESTRUCTURA.md`](docs/ESTRUCTURA.md).

## Requisitos previos

- [uv](https://docs.astral.sh/uv/) (instala Python 3.12 solo).
- Node.js 22 LTS.
- Docker Desktop (para PostgreSQL).
- Git y Visual Studio Code con las extensiones de Python, Ruff y ESLint.

## Primera vez

```bash
uv sync                          # dependencias de Python
npm ci --prefix apps/web         # dependencias del frontend
cp .env.example .env             # en Windows: copy .env.example .env  (y ajusta los valores)
uv run alas db up                # PostgreSQL en Docker (puerto 5433)
uv run alas db migrate           # crea las tablas
uv run alas db seed              # carga módulos, señas, lecciones y logros
uv run alas camera-assets        # archivos de MediaPipe para la cámara
uv run alas dev                  # API en :8000 y web en http://localhost:5173
```

Docker Desktop debe estar abierto: la API y las pruebas se conectan a PostgreSQL en
`localhost:5433`.

Para detener `alas dev` usa **Ctrl+C**. No cierres la terminal con la X: en Windows podrían
quedar procesos sueltos ocupando los puertos 8000 y 5173.

## Comandos

| Comando | Qué hace |
|---|---|
| `uv run alas dev` | API con recarga (8000) + Vite (5173). |
| `uv run alas check` | ruff, mypy, pytest, ESLint, tsc, Vitest y tipos de la API. Debe quedar en verde antes de cada commit. |
| `uv run alas e2e` | Compila la web, la sirve en modo producción contra la base de prueba y ejecuta Playwright (Chromium y Firefox, 1366×768). No lo ejecutes al mismo tiempo que `alas check`: los dos usan `alas_test`. |
| `uv run alas start-prod` | Compila la web y la sirve con FastAPI en http://localhost:8000 (así se hace la demo local). |
| `uv run alas gen-api` | Regenera los tipos TypeScript de la API (`apps/web/src/lib/api-types.ts`). |
| `uv run alas db up \| migrate \| seed \| reset` | Base de datos de desarrollo. |
| `uv run alas db seed-demo [--reset]` | Usuario de demostración (ver abajo). |
| `uv run alas content placeholders \| videos \| check \| all` | Pipeline de videos y contenido. |
| `uv run alas camera-assets` | Copia el WASM de MediaPipe y descarga sus modelos. |

## Pruebas

- **Backend:** pytest, con más del 95 % de cobertura exigida (hoy 99,5 %).
- **Frontend:** Vitest y Testing Library.
- **De punta a punta:** Playwright, con una cámara falsa para la lección con gestos.
- **Entrenamiento:** pruebas de `ml/` con pytest.

Las reglas de negocio tienen pruebas escritas antes que el código.

## Usuario de demostración

```bash
uv run alas db seed-demo --reset
```

Crea `demo@alasdesenas.co` con la contraseña `demo-alas-2026` (solo en desarrollo; si no,
`DEMO_PASSWORD`). Sus fechas son relativas a hoy:
- Módulo 1 completo.
- Racha de 5 días «en riesgo».
- Repaso pendiente con 3 letras falladas ayer.
- M2-N1-L1 disponible.
- 5 vidas y 6 logros.

Usa los servicios reales con un reloj simulado. En producción solo funciona con
`--allow-production` **y** `DEMO_PASSWORD`.

## Despliegue (Render + Neon)

La imagen [`Dockerfile`](Dockerfile) compila la web, prepara los archivos de MediaPipe y deja un
solo servicio que sirve la API y la web. Al arrancar aplica las migraciones y carga el contenido.

1. **Neon:** crea la base y copia la cadena de conexión con el formato
   `postgresql+psycopg://USUARIO:CLAVE@HOST/BASE?sslmode=require`.
2. **Render → New Web Service → Docker**, desde este repositorio.
3. Variables de entorno (ver `.env.example`):
   - `APP_ENV=production`
   - `DATABASE_URL=` (la de Neon)
   - `JWT_SECRET=` (texto aleatorio de 32 caracteres o más)
   - `ADMIN_EMAIL` y `ADMIN_PASSWORD` (opcionales, crean la cuenta de administración)
   - `DEMO_PASSWORD` (solo si se va a crear la demo en producción)
   - `TRUSTED_PROXY_HOPS` ya viene en 1 en la imagen (el proxy de Render). No uses
     `--forwarded-allow-ips='*'`: dejaría que cualquiera falsifique su IP y se salte el límite de
     intentos de inicio de sesión (D-035).
4. Comprueba que `https://<tu-app>.onrender.com/api/health` responda `{"ok":true,"db":true}`.

Probar la imagen en el propio computador:

```bash
docker build -t alas-de-senas .
docker run --rm -p 8000:8000 -e DATABASE_URL=... -e JWT_SECRET=... alas-de-senas
```

Desde Docker, la base local se alcanza con `host.docker.internal:5433`.

## Integración continua

[`.github/workflows/ci.yml`](.github/workflows/ci.yml) ejecuta `alas check` en cada push y pull
request, y `alas e2e` en `main`.

## Documentación

| Documento | Qué tiene |
|---|---|
| [`docs/specs/requirements.md`](docs/specs/requirements.md) | Qué debe hacer el sistema (10 requisitos, criterios EARS) |
| [`docs/specs/design.md`](docs/specs/design.md) | Cómo se cumple cada requisito |
| [`docs/especificacion.md`](docs/especificacion.md) | Especificación técnica completa |
| [`docs/ESTRUCTURA.md`](docs/ESTRUCTURA.md) | Las 4 partes del proyecto y cómo se comunican |
| [`docs/DECISIONES.md`](docs/DECISIONES.md) | Registro de decisiones (D-001 en adelante) |
| [`docs/PROGRESS.md`](docs/PROGRESS.md) | Bitácora de avance por grupo de tareas |
| [`docs/guia-grabacion-gestos.md`](docs/guia-grabacion-gestos.md) | Cómo grabar muestras para la cámara de movimiento |
| [`docs/harness.md`](docs/harness.md) | Hooks, comandos y subagentes usados con Claude Code |

## Checklist del día de la sustentación

- [ ] Demo **principal en local** con `uv run alas start-prod` y la base local ya sembrada.
- [ ] **El mismo día**, ejecutar `uv run alas db seed-demo --reset` e iniciar sesión con la demo.
      Comprobar racha 5, repaso pendiente, M2-N1-L1 disponible y vidas llenas. Tener otro correo
      listo para mostrar el registro.
- [ ] Abrir la versión desplegada 5 minutos antes (el plan gratuito «duerme» el servidor).
- [ ] Probar la cámara en el computador y el lugar de la presentación (luz de frente, fondo liso).
- [ ] Video grabado de la demo completa como respaldo.
- [ ] Ventanas y notificaciones cerradas; zoom del navegador al 110–125 %.

## Créditos y licencias de los datos

Los datasets externos están registrados en [`content/datasets.csv`](content/datasets.csv), y la
app muestra su atribución en la página `/creditos`.

- **LSC-54:** Mora-Zarate, Garzón-Castro y Castellanos-Rivillas (2025), «LSC-54: A
  landmark-based dataset for Colombian Sign Language», *Data in Brief* 63, 112145. Universidad
  de La Sabana. DOI [10.57760/sciencedb.25639](https://doi.org/10.57760/sciencedb.25639).
  Licencia [CC BY-NC 4.0](https://creativecommons.org/licenses/by-nc/4.0/).
  - Se usa para 22 videos del diccionario (convertidos a MP4 y normalizados) y para entrenar
    los modelos de la cámara.
  - **Solo uso no comercial y con atribución.** Los videos originales y los datasets de
    entrenamiento (`ml/data/`) no están en este repositorio.
- **LSC70:** Muñoz Galindez, Villota Coral y Vargas-Canas (2024), «Speak in Colombian Sign
  Language: A Dynamic LSC70 Database», Mendeley Data V2. Universidad del Cauca. DOI
  [10.17632/9ssyn8tff5.2](https://doi.org/10.17632/9ssyn8tff5.2). Licencia
  [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/).
  - Se usan las fotos del alfabeto para entrenar el modelo `lsc-alfabeto`.

Las demás señas del diccionario usan, por ahora, videos o imágenes provisionales. Toda persona
que aparezca en material propio firma una autorización de uso de imagen.

## Licencia

El equipo aún no ha definido una licencia para el código. Mientras tanto, se aplican los
derechos de autor por defecto. Los datos de terceros conservan sus propias licencias (ver
arriba); en particular, el uso de LSC-54 no puede ser comercial.

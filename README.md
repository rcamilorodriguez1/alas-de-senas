# 🐦 Alas de Señas

Plataforma web para aprender **Lengua de Señas Colombiana (LSC)** con lecciones cortas, rachas,
logros y la ayuda de **Tomi**, un colibrí. Proyecto académico de Ingeniería de Sistemas.
Pensada para portátil y computador (Chrome, Edge y Firefox, de 1280×720 a 1920×1080).

- **Frontend:** React + TypeScript (`apps/web`).
- **API y reglas de negocio:** Python 3.12 con FastAPI, SQLAlchemy y Alembic (`apps/api`).
- **Base de datos:** PostgreSQL 16.
- **Cámara (beta):** MediaPipe y TensorFlow.js en el navegador; el video nunca sale del equipo.
- **Entrenamiento de modelos:** Python 3.11 + TensorFlow (`ml/`, aparte).

La especificación completa está en [`docs/`](docs/) y la organización del código en
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

Para detener `alas dev` usa **Ctrl+C** (no cierres la terminal con la X: en Windows podrían
quedar procesos sueltos ocupando los puertos 8000 y 5173).

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

## Usuario de demostración

```bash
uv run alas db seed-demo --reset
```

Crea `demo@alasdesenas.co` (contraseña `demo-alas-2026` en desarrollo, o `DEMO_PASSWORD`) con
fechas relativas a hoy: Módulo 1 completo, racha de 5 días «en riesgo», repaso pendiente con 3
letras falladas ayer, M2-N1-L1 disponible, 5 vidas y 6 logros. Usa los servicios reales con un
reloj simulado. En producción solo funciona con `--allow-production` **y** `DEMO_PASSWORD`.

## Despliegue (Render + Neon)

La imagen [`Dockerfile`](Dockerfile) compila la web, prepara los archivos de MediaPipe y deja un
solo servicio que sirve la API y la web. Al arrancar aplica las migraciones y carga el contenido.

1. **Neon:** crea la base y copia la cadena de conexión con el formato
   `postgresql+psycopg://USUARIO:CLAVE@HOST/BASE?sslmode=require`.
2. **Render → New Web Service → Docker**, desde el repositorio de GitHub.
3. Variables de entorno (ver `.env.example`):
   - `APP_ENV=production`
   - `DATABASE_URL=` (la de Neon)
   - `JWT_SECRET=` (texto aleatorio de 32 caracteres o más)
   - `ADMIN_EMAIL` y `ADMIN_PASSWORD` (opcionales, crean la cuenta de administración)
   - `DEMO_PASSWORD` (solo si se va a crear la demo en producción)
4. Comprueba `https://<tu-app>.onrender.com/api/health` → `{"ok":true,"db":true}`.

Probar la imagen en el propio computador:

```bash
docker build -t alas-de-senas .
docker run --rm -p 8000:8000 -e DATABASE_URL=... -e JWT_SECRET=... alas-de-senas
```

(desde Docker, la base local se alcanza con `host.docker.internal:5433`).

## Checklist del día de la sustentación (§17.3)

- [ ] Demo **principal en local** con `uv run alas start-prod` y la base local ya sembrada.
- [ ] **El mismo día**: `uv run alas db seed-demo --reset` e iniciar sesión con la demo para
      comprobar racha 5, repaso pendiente, M2-N1-L1 disponible y vidas llenas. Tener otro correo
      listo para mostrar el registro.
- [ ] Abrir la versión desplegada 5 minutos antes (el plan gratuito «duerme» el servidor).
- [ ] Probar la cámara en el computador y el lugar de la presentación (luz de frente, fondo liso).
- [ ] Video grabado de la demo completa como respaldo.
- [ ] Ventanas y notificaciones cerradas; zoom del navegador al 110–125 %.

## Integración continua

`.github/workflows/ci.yml` ejecuta `alas check` en cada push y pull request, y `alas e2e` en
`main`. Requiere que el repositorio esté en GitHub (pendiente, D-006).

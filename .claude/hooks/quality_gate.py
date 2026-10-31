"""Stop: compuerta de calidad. Antes de que Claude dé por terminado su turno, verifica lo que cambió.

- Si cambió Python del backend: ruff, mypy --strict y pruebas unitarias (rápidas).
- Si cambió el frontend: tsc y Vitest.
- Si cambiaron esquemas o routers de la API: que los tipos de TypeScript generados estén al día.
Si algo falla, termina con código 2: Claude NO se detiene y recibe los errores para corregirlos.
Para evitar ciclos infinitos, como máximo bloquea 3 veces seguidas en la misma sesión.
La verificación completa (`uv run alas check`) sigue siendo obligatoria al cerrar cada fase.
"""
from __future__ import annotations

import json
import tempfile
from pathlib import Path

from _common import PROJECT_DIR, allow, block, read_input, run, tail, tool

MAX_BLOCKS = 3


def changed_files() -> list[str]:
    git = tool("git")
    if not git or not (PROJECT_DIR / ".git").exists():
        return []
    code, out = run([git, "status", "--porcelain", "--untracked-files=all"], timeout=20)
    if code != 0:
        return []
    files = []
    for line in out.splitlines():
        if len(line) > 3:
            name = line[3:].split(" -> ")[-1].strip().strip('"')
            files.append(name.replace("\\", "/"))
    return files


def counter_file(session_id: str) -> Path:
    safe = "".join(c for c in session_id if c.isalnum() or c in "-_") or "sin-sesion"
    return Path(tempfile.gettempdir()) / f"alas-quality-gate-{safe}.json"


def main() -> None:
    data = read_input()
    session_id = str(data.get("session_id") or "")
    state_path = counter_file(session_id)
    try:
        blocks = int(json.loads(state_path.read_text()).get("blocks", 0)) if state_path.exists() else 0
    except (ValueError, OSError):
        blocks = 0

    files = changed_files()
    py_changed = any(f.startswith("apps/api/") and f.endswith(".py") for f in files)
    web_changed = any(f.startswith("apps/web/src/") and f.endswith((".ts", ".tsx")) for f in files)
    api_changed = any(f.startswith(("apps/api/app/schemas/", "apps/api/app/api/")) for f in files)

    failures: list[str] = []
    uv = tool("uv")
    api_ready = bool(uv) and (PROJECT_DIR / "apps" / "api" / "pyproject.toml").exists() and (PROJECT_DIR / ".venv").exists()

    if py_changed and api_ready:
        steps = [
            ("ruff", [uv, "run", "--no-sync", "ruff", "check", "apps/api"], 90),
            ("mypy --strict", [uv, "run", "--no-sync", "mypy", "apps/api/app"], 180),
        ]
        if (PROJECT_DIR / "apps" / "api" / "tests" / "unit").exists():
            steps.append(("pytest (unitarias)", [uv, "run", "--no-sync", "pytest", "apps/api/tests/unit", "-q", "-x", "--no-header"], 180))
        for name, cmd, timeout in steps:
            code, out = run(cmd, timeout=timeout)
            if code != 0:
                failures.append(f"### {name} falló\n{tail(out, 40)}")
                break

    npm = tool("npm")
    web = PROJECT_DIR / "apps" / "web"
    if web_changed and npm and (web / "node_modules").exists():
        for name, cmd in (("tsc", [npm, "run", "typecheck"]), ("vitest", [npm, "run", "test", "--", "--run"])):
            code, out = run(cmd, cwd=web, timeout=180)
            if code != 0:
                failures.append(f"### {name} falló\n{tail(out, 40)}")
                break

    if api_changed and api_ready and (PROJECT_DIR / "apps" / "web" / "src" / "lib" / "api-types.ts").exists():
        code, out = run([uv, "run", "--no-sync", "alas", "gen-api", "--check"], timeout=120)
        if code != 0:
            failures.append(f"### Tipos de la API desactualizados\nEjecuta `uv run alas gen-api`.\n{tail(out, 15)}")

    if not failures:
        state_path.unlink(missing_ok=True)
        allow()

    if blocks >= MAX_BLOCKS:
        state_path.unlink(missing_ok=True)
        # Se deja terminar para no entrar en un ciclo; el aviso queda en el log y en PROGRESS.md.
        allow()

    state_path.write_text(json.dumps({"blocks": blocks + 1}))
    block(
        "COMPUERTA DE CALIDAD: no termines todavía. Estos chequeos fallan con tus cambios:\n\n"
        + "\n\n".join(failures)
        + "\n\nCorrige la causa raíz (no desactives ni saltes pruebas). Si el fallo pertenece a una fase "
        "futura y no se puede resolver ahora, explícalo en docs/PROGRESS.md y díselo al usuario."
    )


if __name__ == "__main__":
    main()

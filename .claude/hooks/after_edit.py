"""PostToolUse (Edit|Write|MultiEdit): formatea y revisa el archivo recién editado.

- Python (apps/api, ml): `ruff format` + `ruff check --fix`.
- TypeScript (apps/web/src): `eslint --fix` si las dependencias del frontend están instaladas.
Si quedan errores, termina con código 2 para que Claude los vea y los corrija de inmediato.
Si el proyecto aún no tiene las herramientas instaladas (fase 0 temprana), no hace nada.
"""
from __future__ import annotations

from pathlib import Path

from _common import PROJECT_DIR, allow, block, read_input, rel_path, run, tail, tool


def python_file(path: str) -> None:
    uv = tool("uv")
    # Sin entorno instalado (fase 0 temprana) no se hace nada: `uv run` sin --no-sync intentaría instalar
    # todo dentro del hook y podría agotar el tiempo con un bloqueo confuso.
    if not uv or not (PROJECT_DIR / "pyproject.toml").exists() or not (PROJECT_DIR / ".venv").exists():
        allow()
    run([uv, "run", "--no-sync", "ruff", "format", path], timeout=60)
    code, out = run([uv, "run", "--no-sync", "ruff", "check", "--fix", path], timeout=60)
    if code not in (0,) and "No such file" not in out and "Failed to spawn" not in out:
        block(f"ruff encontró problemas en {path} que no pudo corregir solo. Corrígelos ahora:\n{tail(out, 40)}")


def ts_file(path: str) -> None:
    web = PROJECT_DIR / "apps" / "web"
    eslint = web / "node_modules" / ".bin" / ("eslint.cmd" if (web / "node_modules" / ".bin" / "eslint.cmd").exists() else "eslint")
    if not eslint.exists():
        allow()
    rel_to_web = Path(path).relative_to("apps/web").as_posix()
    code, out = run([str(eslint), "--fix", rel_to_web], cwd=web, timeout=60)
    if code != 0:
        block(f"ESLint encontró problemas en {path}. Corrígelos ahora:\n{tail(out, 40)}")


def main() -> None:
    data = read_input()
    tool_input = data.get("tool_input") or {}
    path = rel_path(str(tool_input.get("file_path") or "")) if isinstance(tool_input, dict) else ""
    if not path or not (PROJECT_DIR / path).exists():
        allow()
    if path.endswith(".py") and (path.startswith("apps/api/") or path.startswith("ml/")):
        python_file(path)
    elif path.startswith("apps/web/src/") and path.endswith((".ts", ".tsx")):
        ts_file(path)
    allow()


if __name__ == "__main__":
    main()

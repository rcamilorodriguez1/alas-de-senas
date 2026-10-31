"""PreToolUse (Edit|Write|MultiEdit): impide escribir código que viola las reglas de la especificación v3.

Solo revisa el texto NUEVO que se va a escribir. Código 2 = la edición NO se aplica y Claude recibe el motivo
con la regla y cómo corregirlo.
"""
from __future__ import annotations

import re

from _common import allow, block, read_input, rel_path

Rule = tuple[str, str]

ANY_FILE: list[Rule] = [
    (r"@pytest\.mark\.(skip|skipif|xfail)\b|\bpytest\.skip\(",
     "No se permiten pruebas saltadas ni marcadas como fallo esperado (regla 3). Corrige el código."),
    (r"\b(it|test|describe)\.(skip|only|todo)\(|\bx(it|describe|test)\(",
     "No se permiten pruebas saltadas ni `.only` en el frontend (regla 3)."),
]

PY_APP: list[Rule] = [
    (r"#\s*type:\s*ignore(?!\[[a-z-]+\]\s*#\s*\S)",
     "`# type: ignore` solo se permite con código y justificación: `# type: ignore[codigo]  # motivo` (regla 7)."),
    (r"\b(text|execute)\(\s*f[\"']", "No construyas SQL con f-strings (§11). Usa SQLAlchemy con parámetros."),
    (r"\bshell\s*=\s*True\b", "No uses `shell=True` en subprocess (§6.4). Pasa la lista de argumentos."),
]

PY_NO_ANY: list[Rule] = [
    (r"(:\s*Any\b|->\s*Any\b|\[Any\b|,\s*Any\]|\bfrom\s+typing\s+import\b[^\n]*\bAny\b)",
     "No uses `Any` explícito (regla 7, mypy --strict). Define un tipo concreto, un TypedDict o un modelo Pydantic."),
]

PY_ML: list[Rule] = [
    (r"\bGRU\((?![^)]*\breset_after\s*=\s*False)",
     "Las capas GRU deben llevar `reset_after=False`: TensorFlow.js no puede cargar el modelo con el valor por "
     "defecto de Keras (B73, anexo A.7)."),
]

PY_DOMAIN: list[Rule] = [
    (r"^\s*(from|import)\s+(fastapi|sqlalchemy|starlette|pydantic_settings)\b",
     "El dominio (app/domain) no puede importar FastAPI ni SQLAlchemy (§4, regla 8). Define un Protocol en el "
     "dominio e impleméntalo en app/infra."),
    (r"\b(datetime\.(now|utcnow|today)|date\.today|time\.time)\(",
     "El dominio no puede leer la hora del sistema (§7.1). Recibe un `Clock` o la fecha como parámetro."),
    (r"(?<![\w.])round\(",
     "No uses `round()` en reglas de negocio: Python redondea al par (round(2.5) == 2). Usa `round_half_up` (§7.2)."),
    (r"(?<![\w.])hash\(",
     "No uses `hash()`: cambia en cada ejecución (PYTHONHASHSEED). Usa `random.Random(\"semilla de texto\")` (§6.7)."),
    (r"(?<![\w.])print\(", "No uses print() en el dominio."),
]

PY_APP_NO_PRINT: list[Rule] = [
    (r"(?<![\w.])print\(", "No uses print() en la aplicación: usa `logging` (o `typer.echo` en la CLI)."),
]

TS_WEB: list[Rule] = [
    (r"@ts-(ignore|nocheck|expect-error)\b", "No se permite @ts-ignore/@ts-nocheck/@ts-expect-error (regla 7)."),
    (r"\bas\s+unknown\s+as\b", "No se permite `as unknown as` (regla 7)."),
    (r"(:\s*any\b|<any>|\bas\s+any\b|any\[\])", "No uses `any` en TypeScript (regla 7)."),
    (r"(?i)localStorage\.setItem\([^)]*(token|jwt|auth)", "El token nunca se guarda en localStorage (§9.2). Va en memoria (Zustand)."),
    (r"\bconsole\.log\(", "No dejes console.log en el código."),
]


def new_text(tool_input: dict[str, object]) -> str:
    parts: list[str] = []
    for key in ("content", "new_string"):
        value = tool_input.get(key)
        if isinstance(value, str):
            parts.append(value)
    edits = tool_input.get("edits")
    if isinstance(edits, list):
        for e in edits:
            if isinstance(e, dict) and isinstance(e.get("new_string"), str):
                parts.append(e["new_string"])
    return "\n".join(parts)


def check(text: str, rules: list[Rule], path: str) -> None:
    for pattern, message in rules:
        m = re.search(pattern, text, flags=re.MULTILINE)
        if m:
            line = text[: m.start()].count("\n") + 1
            snippet = text.splitlines()[line - 1].strip()[:160] if text.splitlines() else ""
            block(f"BLOQUEADO por el harness en {path} (línea ~{line} del texto nuevo):\n  {snippet}\n{message}")


def main() -> None:
    data = read_input()
    tool_input = data.get("tool_input") or {}
    if not isinstance(tool_input, dict):
        allow()
    path = rel_path(str(tool_input.get("file_path") or ""))
    text = new_text(tool_input)
    if not path or not text:
        allow()

    if path == "apps/web/src/lib/api-types.ts":
        block("BLOQUEADO por el harness: api-types.ts se genera desde FastAPI. Ejecuta `uv run alas gen-api` (§8.4).")

    is_test = "/tests/" in f"/{path}" or re.search(r"\.(test|spec)\.tsx?$", path) is not None
    if re.search(r"\.(py|ts|tsx)$", path):
        check(text, ANY_FILE, path)

    if path.endswith(".py") and (path.startswith("apps/api/app/") or path.startswith("ml/")):
        check(text, PY_APP, path)
        if path.startswith("apps/api/app/"):
            check(text, PY_NO_ANY, path)
        if path.startswith("ml/"):
            check(text, PY_ML, path)
        if path.startswith("apps/api/app/domain/"):
            check(text, PY_DOMAIN, path)
        elif not path.endswith("cli.py") and not path.startswith("ml/"):
            check(text, PY_APP_NO_PRINT, path)

    if re.search(r"\.(ts|tsx)$", path) and path.startswith("apps/web/src/") and not is_test:
        check(text, TS_WEB, path)
    allow()


if __name__ == "__main__":
    main()

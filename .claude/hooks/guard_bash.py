"""PreToolUse (Bash): bloquea comandos peligrosos o que rompen las reglas del proyecto.

Código 2 = el comando NO se ejecuta y Claude recibe el motivo.
"""
from __future__ import annotations

import re

from _common import allow, block, read_input

FLAGS = re.IGNORECASE | re.DOTALL

RULES: list[tuple[str, str]] = [
    (r"\bpip3?\s+install\b|\bpython3?\s+-m\s+pip\s+install\b",
     "No uses pip. Las dependencias se gestionan con uv (`uv add <paquete>`, pide permiso) y deben "
     "justificarse en docs/DECISIONES.md (especificación §0.1, regla 5)."),
    (r"--no-verify\b", "No omitas las verificaciones de git (--no-verify)."),
    (r"\bgit\s+push\b.*(\s--force\b|\s-f\b|--force-with-lease)", "No se permite git push forzado."),
    (r"\bgit\s+reset\s+--hard\b|\bgit\s+clean\s+-[a-z]*f",
     "No se permite descartar trabajo con reset --hard ni git clean."),
    (r"\brm\s+-[a-z]*r[a-z]*\s+(/|~|\$home|\*|\.(\s|$)|\.\.)",
     "Borrado recursivo peligroso. Borra solo rutas concretas dentro del proyecto."),
    (r"\b(drop\s+(database|schema|table)|truncate\s+table)\b",
     "No ejecutes DROP/TRUNCATE a mano. Usa migraciones de Alembic o `uv run alas db reset` (pide confirmación)."),
    (r"\balembic\b.*\bdowngrade\s+base\b", "No bajes todas las migraciones (downgrade base)."),
    (r"neon\.tech", "No ejecutes comandos contra la base de datos de producción desde la sesión de desarrollo."),
    (r"\b(curl|wget|iwr|invoke-webrequest)\b[^|]*\|\s*(sh|bash|zsh|python3?|pwsh|powershell|iex)\b",
     "No ejecutes scripts descargados de internet directamente."),
    (r"\bpytest\b.*(--deselect\b|-k\s+['\"]?not\b|--ignore\b)",
     "No excluyas pruebas para que la suite pase (regla 3). Corrige el código o, si la prueba pertenece a una "
     "fase futura, anótalo en docs/PROGRESS.md."),
    (r"\bvitest\b.*--exclude\b", "No excluyas pruebas del frontend para que la suite pase (regla 3)."),
]

NPM_INSTALL = re.compile(r"\bnpm\s+(install|i|ci|uninstall|add)\b", FLAGS)
IN_WEB = re.compile(r"(cd\s+[\"']?\.?/?apps[/\\]web|--prefix\s+[\"']?\.?/?apps[/\\]web)", FLAGS)


def main() -> None:
    data = read_input()
    command = str((data.get("tool_input") or {}).get("command") or "")
    if not command:
        allow()

    for pattern, message in RULES:
        if re.search(pattern, command, FLAGS):
            block(f"BLOQUEADO por el harness: {message}\nComando: {command[:300]}")

    if NPM_INSTALL.search(command):
        cwd = str(data.get("cwd") or "").replace("\\", "/").rstrip("/")
        if not (IN_WEB.search(command) or cwd.endswith("apps/web")):
            block("BLOQUEADO por el harness: usa npm solo dentro de apps/web (por ejemplo "
                  "`npm ci --prefix apps/web`). El resto del proyecto es Python con uv.")
    allow()


if __name__ == "__main__":
    main()

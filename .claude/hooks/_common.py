"""Utilidades compartidas por los hooks del harness de Alas de Señas.

Solo biblioteca estándar: los hooks deben funcionar antes de que exista el entorno del proyecto.
Funcionan igual en Windows, macOS y Linux.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

PROJECT_DIR = Path(os.environ.get("CLAUDE_PROJECT_DIR", Path(__file__).resolve().parents[2])).resolve()


def read_input() -> dict[str, Any]:
    """Lee el JSON que Claude Code envía por stdin. Si no hay JSON válido, devuelve {}."""
    try:
        raw = sys.stdin.read()
        data = json.loads(raw) if raw.strip() else {}
        return data if isinstance(data, dict) else {}
    except (json.JSONDecodeError, OSError, UnicodeDecodeError):
        return {}


def block(message: str) -> None:
    """Termina con código 2: Claude Code bloquea la acción (PreToolUse) o le muestra el mensaje a Claude."""
    sys.stderr.write(message.strip() + "\n")
    sys.exit(2)


def allow() -> None:
    sys.exit(0)


def rel_path(file_path: str) -> str:
    """Ruta relativa al proyecto con barras '/', para comparar igual en Windows y Linux."""
    if not file_path:
        return ""
    p = Path(file_path)
    if not p.is_absolute():
        p = PROJECT_DIR / p
    try:
        return p.resolve().relative_to(PROJECT_DIR).as_posix()
    except ValueError:
        return p.as_posix()


def tool(name: str) -> str | None:
    """Ruta completa de un ejecutable (resuelve npm.cmd en Windows)."""
    return shutil.which(name)


def run(cmd: list[str], cwd: Path | None = None, timeout: int = 120) -> tuple[int, str]:
    """Ejecuta un comando sin shell y devuelve (código, salida combinada)."""
    try:
        proc = subprocess.run(
            cmd,
            cwd=str(cwd or PROJECT_DIR),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
        )
        return proc.returncode, (proc.stdout or "") + (proc.stderr or "")
    except subprocess.TimeoutExpired:
        return 124, f"Tiempo agotado ({timeout} s) ejecutando: {' '.join(cmd)}"
    except OSError as exc:
        return 127, f"No se pudo ejecutar {' '.join(cmd)}: {exc}"


def tail(text: str, lines: int = 60) -> str:
    parts = text.strip().splitlines()
    return "\n".join(parts[-lines:])

"""SessionStart: le da a Claude el contexto del proyecto al iniciar o reanudar una sesión.

Lo que imprime por stdout se agrega como contexto: reglas clave, siguiente tarea pendiente y estado de git.
"""
from __future__ import annotations

import re

from _common import PROJECT_DIR, run, tool


def next_tasks(limit: int = 3) -> list[str]:
    tasks = PROJECT_DIR / "docs" / "specs" / "tasks.md"
    if not tasks.exists():
        return []
    pending: list[str] = []
    group = ""
    for line in tasks.read_text(encoding="utf-8").splitlines():
        if line.startswith("## Grupo"):
            group = line.removeprefix("## ").strip()
        m = re.match(r"\s*- \[ \] (\*\*[\w.]+\*\*.*)", line)
        if m:
            pending.append(f"[{group}] {m.group(1)[:160]}")
            if len(pending) >= limit:
                break
    return pending


def last_progress(lines: int = 12) -> str:
    progress = PROJECT_DIR / "docs" / "PROGRESS.md"
    if not progress.exists():
        return ""
    content = progress.read_text(encoding="utf-8").strip().splitlines()
    return "\n".join(content[-lines:])


def main() -> None:
    out: list[str] = [
        "# Contexto del proyecto Alas de Señas (harness)",
        "- Fuente de verdad: docs/especificacion.md (v3). Requisitos, diseño y tareas: docs/specs/.",
        "- Python en todo excepto apps/web (TypeScript). Reglas de negocio solo en apps/api/app/domain.",
        "- Trabaja una tarea a la vez de docs/specs/tasks.md; al cerrar una fase: `uv run alas check` en verde.",
        "- Los hooks bloquean violaciones de reglas: si uno te bloquea, corrige la causa; no intentes rodearlo.",
    ]
    pending = next_tasks()
    if pending:
        out.append("\n## Siguientes tareas pendientes")
        out.extend(f"- {t}" for t in pending)
    progress = last_progress()
    if progress:
        out.append("\n## Últimas notas de docs/PROGRESS.md\n" + progress)
    git = tool("git")
    if git and (PROJECT_DIR / ".git").exists():
        _, status = run([git, "status", "--short"], timeout=15)
        _, log = run([git, "log", "--oneline", "-5"], timeout=15)
        if log.strip():
            out.append("\n## Últimos commits\n" + log.strip())
        if status.strip():
            out.append("\n## Cambios sin commit\n" + "\n".join(status.strip().splitlines()[:20]))
    print("\n".join(out))


if __name__ == "__main__":
    main()

"""`alas content check`: todas las validaciones de §6.6 y el reporte."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

NODE_SIZE: dict[str, tuple[int, int]] = {
    "STANDARD": (5, 9),
    "NUMBERS": (5, 10),
    "ALPHABET": (12, 16),
}
MIN_SCORED_EXERCISES = 4
MIN_SPELLING_WORDS = 6
MIN_SPELLING_WORDS_L2 = 4
MAX_VIDEO_SECONDS = 8


@dataclass(slots=True)
class Report:
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    # Por módulo publicado: (señas con video/imágenes reales, señas de relleno)
    media_by_module: dict[str, tuple[int, int]] = field(default_factory=dict)
    missing_how_to: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.errors

    def render(self) -> str:
        """Texto en español para la terminal: resumen por módulo, advertencias y errores."""
        raise NotImplementedError


def check_content(
    content_dir: Path,
    media_dir: Path,
    *,
    skip_raw: bool = False,
    labels_path: Path | None = None,
) -> Report:
    """Valida `content_dir` (y `content_dir/videos/raw` salvo `skip_raw`) contra §6.6.

    Nunca lanza por errores de contenido: los acumula en `Report.errors` (los ContentError de
    lectura también se reportan como un error). Reglas: ver la tabla de §6.6 y D-007/D-008
    (las mismas que usa el generador: un GenerationError se reporta como error).
    `labels_path`: `labels.json` del modelo del alfabeto (lista de slugs); si existe se valida.
    """
    raise NotImplementedError

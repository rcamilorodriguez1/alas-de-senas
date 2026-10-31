"""Errores del pipeline de contenido: el mensaje va en español y se muestra tal cual al equipo."""

from __future__ import annotations


class ContentError(Exception):
    """El contenido no se puede leer o no cumple una regla bloqueante."""

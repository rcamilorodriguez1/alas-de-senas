"""Números estáticos con cámara (D-019): motion en los números y `camera_label` en sus PRODUCE."""

from __future__ import annotations

from app.content.loader import load_content, to_sign_specs
from app.content.validation import check_content
from app.domain.content.generator import generate_content
from app.domain.enums import ExerciseType
from app.domain.exercises.models import ProducePayload
from tests.unit.content.real_content import CONTENT_DIR

MEDIA_DIR = CONTENT_DIR.parent / "apps" / "web" / "public" / "media"


def _produce_labels() -> dict[str, str | None]:
    bundle = load_content(CONTENT_DIR)
    generated = generate_content(
        [m.spec for m in bundle.modules], tuple(to_sign_specs(bundle.signs)), bundle.conversations
    )
    labels: dict[str, str | None] = {}
    for exercise in generated.exercises:
        if exercise.type is ExerciseType.PRODUCE and isinstance(exercise.payload, ProducePayload):
            labels[exercise.payload.sign_id] = exercise.payload.camera_label
    return labels


def test_numeros_estaticos_tienen_etiqueta_de_camara_y_los_dinamicos_no() -> None:
    """No todos los números tienen PRODUCE (el generador elige); se revisan los que hay."""
    labels = _produce_labels()
    numbers = {slug: label for slug, label in labels.items() if slug.startswith("numero-")}
    assert numbers, "Premisa: el contenido tiene ejercicios PRODUCE de números"
    for slug, label in numbers.items():
        n = int(slug.removeprefix("numero-"))
        expected = slug if n <= 5 else None
        assert label == expected, slug
    assert any(label for label in numbers.values()), "al menos un número estático usa la cámara"


def test_letras_estaticas_siguen_con_camara_y_las_dinamicas_no() -> None:
    labels = _produce_labels()
    assert labels.get("letra-a") == "letra-a"
    assert labels.get("letra-j") is None


def test_el_contenido_real_valida_con_motion_en_los_numeros() -> None:
    report = check_content(CONTENT_DIR, MEDIA_DIR, skip_raw=True)
    assert not [e for e in report.errors if "motion" in e]

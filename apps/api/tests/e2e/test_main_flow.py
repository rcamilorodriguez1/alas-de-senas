"""Flujo principal de extremo a extremo (§15, R10.6, tarea 11.3).

visitante → intro (6 tarjetas) → mini-quiz → registro → ruta (solo M1-N1-L1 disponible) →
completar L1 respondiendo bien → celebración con XP > 0 y racha 1 → L2 disponible →
diccionario: «GRACÍAS» → ficha «Gracias» → favorito → recargar → la sesión sigue activa.

La prueba responde bien traduciendo lo que ve (la ruta del video) con `media/manifest.json` y
`content/signs.csv` del repositorio. La API no tiene ningún «modo prueba» (B89).
Se ejecuta con `uv run alas e2e` (Chromium y Firefox, 1366x768).
"""

from __future__ import annotations

import re
import uuid

import pytest
from playwright.sync_api import ElementHandle, Locator, Page, expect

from tests.e2e.conftest import SignMaps

pytestmark = pytest.mark.e2e

PASSWORD = "Clave-Segura-E2E-1"
MAX_STEPS = 80  # tope de seguridad: una lección tiene ~12 ejercicios


def _video_src(locator: Locator) -> str:
    src = locator.locator("video").first.get_attribute("src")
    assert src, "El ejercicio debería mostrar un video"
    return src


def _wait_detached(handle: ElementHandle | None) -> None:
    """Espera a que el ejercicio actual desaparezca (cambia de ejercicio o termina)."""
    if handle is not None:
        handle.wait_for_element_state("hidden")


def _do_intro(page: Page, maps: SignMaps) -> None:
    page.goto("/")
    expect(page).to_have_url(re.compile(r"/bienvenida$"))
    for index in range(6):
        expect(page.get_by_text(f"Seña {index + 1} de 6")).to_be_visible()
        label = "Siguiente" if index < 5 else "Ir al mini-quiz"
        page.get_by_role("button", name=label).click()
    for index in range(3):
        expect(page.get_by_text(f"Pregunta {index + 1} de 3")).to_be_visible()
        words = maps.words_for_video(_video_src(page.locator("main")))
        options = page.get_by_role("group", name="Opciones").get_by_role("button")
        options.filter(has_text=re.compile("^(" + "|".join(map(re.escape, words)) + ")$")).click()
        expect(page.get_by_text("¡Correcto! 🎉")).to_be_visible()
        page.get_by_role("button", name="Continuar" if index < 2 else "Crear mi cuenta").click()


def _register(page: Page) -> None:
    expect(page).to_have_url(re.compile(r"/registro$"))
    page.get_by_label("Nombre").fill("Prueba E2E")
    page.get_by_label("Correo").fill(f"e2e-{uuid.uuid4().hex[:12]}@alasdesenas.co")
    page.get_by_label("Contraseña").fill(PASSWORD)
    page.get_by_label(re.compile("Acepto la política")).check()
    page.get_by_role("button", name="Crear cuenta").click()
    expect(page).to_have_url(re.compile(r"/aprender$"))


def _choose(active: Locator, maps: SignMaps) -> None:
    """VIDEO_TO_MEANING o MEANING_TO_VIDEO: elige la opción correcta."""
    options = active.get_by_test_id(re.compile(r"^lesson-option-\d$"))
    question = re.search(r"¿Cuál es la seña de «(.+?)»\?", active.inner_text())
    if question:  # palabra → video
        targets = maps.slugs_by_word[question.group(1)]
        for i in range(options.count()):
            option = options.nth(i)
            if maps.slugs_by_video.get(_video_src(option), set()) & targets:
                option.click()
                break
        else:
            pytest.fail(f"Ninguna opción corresponde a «{question.group(1)}»")
    else:  # video → palabra
        words = maps.words_for_video(_video_src(active))
        options.filter(has_text=re.compile("(" + "|".join(map(re.escape, words)) + ")$")).click()
    active.get_by_test_id("check-answer").click()
    expect(active.get_by_text("¡Exacto!", exact=False)).to_be_visible()
    active.get_by_test_id("continue").click()


def _complete_lesson(page: Page, maps: SignMaps) -> Locator:
    dialog = page.get_by_role("dialog")
    active = page.get_by_test_id("active-exercise")
    for _ in range(MAX_STEPS):
        page.locator('[data-testid="active-exercise"], [role="dialog"]').first.wait_for()
        if dialog.is_visible():
            return dialog
        current = active.locator(":scope > *").first.element_handle()
        if active.get_by_test_id(re.compile(r"^lesson-option-\d$")).count() > 0:
            _choose(active, maps)
        elif active.get_by_role("button", name="Sí, me salió").count() > 0:
            active.get_by_role("button", name="Sí, me salió").click()  # autoevaluación
        else:
            active.get_by_test_id("continue").click()  # observar
        _wait_detached(current)
    pytest.fail("La lección no terminó")


def test_flujo_principal(page: Page, sign_maps: SignMaps) -> None:
    _do_intro(page, sign_maps)
    _register(page)

    # Ruta: solo M1-N1-L1 disponible.
    first = page.get_by_test_id("lesson-M1-N1-L1")
    expect(first).to_contain_text("Disponible")
    expect(
        page.get_by_test_id(re.compile(r"^lesson-")).filter(has_text="Disponible")
    ).to_have_count(1)
    expect(page.get_by_test_id("lesson-M1-N1-L2")).to_contain_text("Bloqueada")

    first.click()
    page.get_by_role("link", name="Empezar").click()
    expect(page).to_have_url(re.compile(r"/leccion/M1-N1-L1$"))

    celebration = _complete_lesson(page, sign_maps)
    xp = re.search(r"\+(\d+) XP", celebration.inner_text())
    assert xp is not None and int(xp.group(1)) > 0
    expect(celebration).to_contain_text("Racha: 1 día")
    celebration.get_by_role("button", name="Volver a la ruta").click()

    expect(page.get_by_test_id("lesson-M1-N1-L2")).to_contain_text("Disponible")

    # Diccionario: búsqueda insensible a tildes y mayúsculas → ficha → favorito.
    page.get_by_role("link", name="Diccionario").first.click()
    page.get_by_placeholder(re.compile("Busca una palabra")).fill("GRACÍAS")
    page.locator('a[href="/diccionario/gracias"]').first.click()
    expect(page).to_have_url(re.compile(r"/diccionario/gracias$"))
    expect(page.get_by_role("heading", name="Gracias")).to_be_visible()
    page.get_by_role("button", name="Guardar en favoritos").click()
    expect(page.get_by_role("button", name="Quitar de favoritos")).to_be_visible()

    # Recargar: el token de acceso vivía en memoria; la cookie de renovación recupera la sesión.
    page.reload()
    expect(page).to_have_url(re.compile(r"/diccionario/gracias$"))
    expect(page.get_by_role("button", name="Quitar de favoritos")).to_be_visible()

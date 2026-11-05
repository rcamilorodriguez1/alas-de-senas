"""`alas camera-assets` (tarea 10.1, §10.1): copia el WASM y descarga el modelo, sin red."""

from __future__ import annotations

from pathlib import Path

import pytest

from app.content.camera_assets import (
    HAND_LANDMARKER_URL,
    HOLISTIC_LANDMARKER_URL,
    CameraAssetsError,
    prepare_camera_assets,
)


def make_web(tmp_path: Path) -> Path:
    wasm = tmp_path / "node_modules" / "@mediapipe" / "tasks-vision" / "wasm"
    wasm.mkdir(parents=True)
    (wasm / "vision_wasm_internal.js").write_text("js", encoding="utf-8")
    (wasm / "vision_wasm_internal.wasm").write_bytes(b"\x00asm")
    return tmp_path


def fake_download(calls: list[str]):
    def download(url: str, target: Path) -> None:
        calls.append(url)
        target.write_bytes(b"modelo")

    return download


def test_copia_el_wasm_y_descarga_el_modelo(tmp_path: Path) -> None:
    web = make_web(tmp_path)
    calls: list[str] = []
    report = prepare_camera_assets(web, download=fake_download(calls))

    wasm = web / "public" / "mediapipe" / "wasm"
    assert sorted(p.name for p in wasm.iterdir()) == [
        "vision_wasm_internal.js",
        "vision_wasm_internal.wasm",
    ]
    assert report.wasm_files == ("vision_wasm_internal.js", "vision_wasm_internal.wasm")
    assert report.model == web / "public" / "mediapipe" / "hand_landmarker.task"
    assert report.model.read_bytes() == b"modelo"
    assert report.downloaded is True
    assert report.error is None
    assert calls == [HAND_LANDMARKER_URL, HOLISTIC_LANDMARKER_URL]  # manos y holístico (10B)
    assert (web / "public" / "mediapipe" / "holistic_landmarker.task").read_bytes() == b"modelo"


def test_no_vuelve_a_descargar_si_el_modelo_ya_esta(tmp_path: Path) -> None:
    web = make_web(tmp_path)
    calls: list[str] = []
    prepare_camera_assets(web, download=fake_download(calls))
    report = prepare_camera_assets(web, download=fake_download(calls))
    assert calls == [HAND_LANDMARKER_URL, HOLISTIC_LANDMARKER_URL]
    assert report.downloaded is False


def test_force_descarga_de_nuevo(tmp_path: Path) -> None:
    web = make_web(tmp_path)
    calls: list[str] = []
    prepare_camera_assets(web, download=fake_download(calls))
    prepare_camera_assets(web, download=fake_download(calls), force=True)
    assert len(calls) == 4


def test_si_la_descarga_falla_da_la_url_oficial_y_conserva_el_wasm(tmp_path: Path) -> None:
    web = make_web(tmp_path)

    def broken(url: str, target: Path) -> None:
        raise OSError("sin conexión")

    report = prepare_camera_assets(web, download=broken)
    assert report.error is not None
    assert HAND_LANDMARKER_URL in report.error
    assert "sin conexión" in report.error
    assert not report.model.exists()
    assert len(report.wasm_files) == 2


def test_sin_node_modules_pide_npm_ci(tmp_path: Path) -> None:
    with pytest.raises(CameraAssetsError, match="npm ci"):
        prepare_camera_assets(tmp_path, download=fake_download([]))


def test_la_url_es_la_oficial_por_https() -> None:
    assert HAND_LANDMARKER_URL.startswith("https://storage.googleapis.com/mediapipe-models/")
    assert HAND_LANDMARKER_URL.endswith("/hand_landmarker.task")


def test_la_url_holistica_es_la_oficial_float16() -> None:
    assert HOLISTIC_LANDMARKER_URL.startswith("https://storage.googleapis.com/mediapipe-models/")
    assert "/float16/" in HOLISTIC_LANDMARKER_URL
    assert HOLISTIC_LANDMARKER_URL.endswith("/holistic_landmarker.task")

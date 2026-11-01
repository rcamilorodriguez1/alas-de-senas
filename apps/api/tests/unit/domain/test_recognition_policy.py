"""Regla del logro «Ojo de colibrí» (§7.9): función pura."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from app.domain.policies.recognition import counts_for_eye

NOW = datetime(2026, 11, 3, 15, 0, tzinfo=UTC)


def test_correcto_y_seguro_cuenta_la_primera_vez() -> None:
    assert counts_for_eye(True, 0.9, None, NOW)


@pytest.mark.parametrize(("correct", "confidence"), [(False, 0.99), (True, 0.69)])
def test_incorrecto_o_poco_seguro_no_cuenta(correct: bool, confidence: float) -> None:
    assert not counts_for_eye(correct, confidence, None, NOW)


def test_justo_0_7_cuenta() -> None:
    assert counts_for_eye(True, 0.7, None, NOW)


def test_la_misma_sena_espera_10_segundos() -> None:
    assert not counts_for_eye(True, 0.9, NOW - timedelta(seconds=9), NOW)
    assert counts_for_eye(True, 0.9, NOW - timedelta(seconds=10), NOW)

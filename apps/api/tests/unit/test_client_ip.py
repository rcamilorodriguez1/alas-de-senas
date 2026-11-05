"""IP del cliente para los límites de peticiones detrás de un proxy (§11, D-035).

`X-Forwarded-For` lo puede escribir el cliente: cada proxy AGREGA al final la IP que vio, así que
solo los últimos `hops` valores (los que pusieron proxies de confianza) son fiables. El primero
nunca se usa.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.core.client_ip import UNKNOWN, resolve_client_ip
from app.core.config import Settings

PEER = "10.1.2.3"  # IP del proxy de Render, o del navegador si no hay proxy


def test_sin_proxies_de_confianza_ignora_x_forwarded_for() -> None:
    assert resolve_client_ip(PEER, "6.6.6.6", None, hops=0) == PEER


def test_con_un_proxy_usa_el_ultimo_valor_que_agrego_ese_proxy() -> None:
    # El cliente mandó «6.6.6.6» falso; Render agregó la IP real que vio (1.2.3.4).
    assert resolve_client_ip(PEER, "6.6.6.6, 1.2.3.4", None, hops=1) == "1.2.3.4"


def test_el_cliente_no_puede_cambiar_su_ip_rotando_el_primer_valor() -> None:
    seen = {resolve_client_ip(PEER, f"6.6.6.{n}, 1.2.3.4", None, hops=1) for n in range(1, 20)}
    assert seen == {"1.2.3.4"}


def test_con_dos_proxies_usa_el_penultimo_valor() -> None:
    assert resolve_client_ip(PEER, "6.6.6.6, 1.2.3.4, 172.16.0.9", None, hops=2) == "1.2.3.4"


def test_sin_x_forwarded_for_usa_la_conexion() -> None:
    assert resolve_client_ip(PEER, None, None, hops=1) == PEER
    assert resolve_client_ip(PEER, "  ", None, hops=1) == PEER


def test_con_menos_valores_que_proxies_usa_la_conexion() -> None:
    # La cadena no es la esperada: no se adivina; la conexión no se puede falsificar.
    assert resolve_client_ip(PEER, "1.2.3.4", None, hops=2) == PEER


@pytest.mark.parametrize("value", ["abc", "1.2.3", "999.1.1.1", "1.2.3.4; drop", "unknown"])
def test_un_valor_que_no_es_ip_se_descarta(value: str) -> None:
    assert resolve_client_ip(PEER, f"6.6.6.6, {value}", None, hops=1) == PEER


def test_acepta_ipv6_y_lo_normaliza() -> None:
    assert resolve_client_ip(PEER, "2001:DB8::1", None, hops=1) == "2001:db8::1"


def test_valores_vacios_entre_comas_no_cuentan_como_saltos() -> None:
    assert resolve_client_ip(PEER, "6.6.6.6,, 1.2.3.4,", None, hops=1) == "1.2.3.4"


def test_la_cabecera_configurada_tiene_prioridad_si_es_una_ip_valida() -> None:
    assert resolve_client_ip(PEER, "6.6.6.6, 1.2.3.4", "8.8.4.4", hops=1) == "8.8.4.4"


@pytest.mark.parametrize("header", [None, "", "no-es-ip", "8.8.4.4, 9.9.9.9"])
def test_si_la_cabecera_configurada_falta_o_no_sirve_sigue_con_los_saltos(
    header: str | None,
) -> None:
    assert resolve_client_ip(PEER, "6.6.6.6, 1.2.3.4", header, hops=1) == "1.2.3.4"


def test_sin_conexion_ni_cabeceras_es_desconocida() -> None:
    assert resolve_client_ip(None, None, None, hops=0) == UNKNOWN


def test_por_defecto_no_se_confia_en_ningun_proxy() -> None:
    settings = Settings(_env_file=None)
    assert settings.trusted_proxy_hops == 0
    assert settings.client_ip_header is None


def test_trusted_proxy_hops_negativo_es_invalido() -> None:
    with pytest.raises(ValidationError):
        Settings(_env_file=None, trusted_proxy_hops=-1)


def test_client_ip_header_vacio_significa_no_configurado() -> None:
    assert Settings(_env_file=None, client_ip_header="  ").client_ip_header is None

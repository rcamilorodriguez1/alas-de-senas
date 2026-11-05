"""IP del cliente para los límites de peticiones (§11, D-035).

`X-Forwarded-For` lo puede escribir el propio cliente; cada proxy AGREGA al final la IP de quien
se le conectó. Por eso solo se confía en los últimos `hops` valores (los agregaron proxies de
confianza, p. ej. el de Render) y nunca en el primero. Ante cualquier duda se usa la conexión
directa, que no se puede falsificar.
"""

from __future__ import annotations

import ipaddress

UNKNOWN = "desconocida"


def _valid_ip(value: str) -> str | None:
    try:
        return str(ipaddress.ip_address(value.strip()))
    except ValueError:
        return None


def resolve_client_ip(
    peer: str | None,
    forwarded_for: str | None,
    trusted_header: str | None,
    *,
    hops: int,
) -> str:
    """`peer`: IP de la conexión. `forwarded_for`: X-Forwarded-For tal cual llegó.
    `trusted_header`: valor de una cabecera que el proxy siempre reescribe (p. ej.
    True-Client-IP), solo si se configuró. `hops`: proxies de confianza delante de la app."""
    fallback = peer or UNKNOWN
    if trusted_header:
        found = _valid_ip(trusted_header)
        if found is not None:
            return found
    if hops <= 0 or not forwarded_for:
        return fallback
    chain = [part for part in (p.strip() for p in forwarded_for.split(",")) if part]
    if len(chain) < hops:
        return fallback  # la cadena no es la esperada: no se adivina
    return _valid_ip(chain[-hops]) or fallback

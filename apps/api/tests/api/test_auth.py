"""Tareas 3.1/3.2 — autenticación y `/me` contra PostgreSQL real (R2, §8.2, §11; B17, B27, B28).

Contrato:
- `POST /api/auth/register` → 201 `{accessToken, user}` + cookie `rt` (HttpOnly, Path=/api/auth,
  SameSite=lax). `POST /api/auth/login` → 200, mismo cuerpo. `POST /api/auth/refresh` rota el
  token. `POST /api/auth/logout` → 204 siempre. `GET|PATCH /api/me` con `Authorization: Bearer`.
- Límites (`app.core.rate_limit`): login 5/min por IP + correo, registro 10/min por IP,
  rutas autenticadas `USER_LIMIT` por usuario.
- Los tiempos los fija el `Clock` inyectado (D22): se sustituye `get_clock` por un `FakeClock`.
"""

from __future__ import annotations

import base64
import importlib
import json
import re
import uuid
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from types import ModuleType

import jwt
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from httpx import Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.clock import get_clock
from app.infra.db import get_engine
from app.infra.models import RefreshToken, User
from tests.fakes import FakeClock

PASSWORD = "clave-segura-123"
EMAIL_TAKEN = {
    "statusCode": 409,
    "code": "EMAIL_TAKEN",
    "message": "Ya existe una cuenta con este correo",
}
INVALID_CREDENTIALS = {
    "statusCode": 401,
    "code": "INVALID_CREDENTIALS",
    "message": "Correo o contraseña incorrectos",
}
TOO_MANY_REQUESTS = {
    "statusCode": 429,
    "code": "TOO_MANY_REQUESTS",
    "message": "Demasiados intentos, espera un minuto",
}
PASSWORD_MESSAGE = "La contraseña debe tener entre 8 y 72 bytes (las tildes y la ñ cuentan doble)."
EMAIL_MESSAGE = "Correo no válido"
POLICY_MESSAGE = "Debes aceptar la política de tratamiento de datos."
MISSING_MESSAGE = "Este campo es obligatorio."
USER_KEYS = {"id", "name", "email", "role", "dailyGoalMinutes", "dominantHand", "avatarUpdatedAt"}


# ---------- Fixtures y utilidades ----------


def _rate_limit_module() -> ModuleType:
    # Se importa en tiempo de ejecución: el módulo puede no existir aún (pruebas primero).
    return importlib.import_module("app.core.rate_limit")


@pytest.fixture(autouse=True)
def reset_limits() -> Iterator[None]:
    module = _rate_limit_module()
    module.reset_rate_limits()
    yield
    module.reset_rate_limits()


@pytest.fixture
def clock(client: TestClient) -> Iterator[FakeClock]:
    fake = FakeClock(datetime.now(UTC).replace(microsecond=0))
    app = client.app
    assert isinstance(app, FastAPI)
    app.dependency_overrides[get_clock] = lambda: fake
    yield fake
    app.dependency_overrides.pop(get_clock, None)


def register_body(email: str = "ana@ejemplo.com", **overrides: object) -> dict[str, object]:
    body: dict[str, object] = {
        "name": "Ana",
        "email": email,
        "password": PASSWORD,
        "dailyGoalMinutes": 10,
        "acceptedDataPolicy": True,
    }
    body.update(overrides)
    return body


def register(client: TestClient, email: str = "ana@ejemplo.com", **overrides: object) -> Response:
    response: Response = client.post("/api/auth/register", json=register_body(email, **overrides))
    return response


def login(client: TestClient, email: str, password: str = PASSWORD) -> Response:
    response: Response = client.post("/api/auth/login", json={"email": email, "password": password})
    return response


def access_token(response: Response) -> str:
    token = response.json()["accessToken"]
    assert isinstance(token, str)
    return token


def user_id(response: Response) -> str:
    value = response.json()["user"]["id"]
    assert isinstance(value, str)
    return value


def rt_cookie(response: Response) -> str:
    value = response.cookies.get("rt")
    assert value, f"La respuesta no trae la cookie rt: {response.headers.get_list('set-cookie')}"
    return value


def rt_set_cookie_header(response: Response) -> str:
    headers = [h for h in response.headers.get_list("set-cookie") if h.startswith("rt=")]
    assert len(headers) == 1, response.headers.get_list("set-cookie")
    return headers[0]


def refresh_with(client: TestClient, token: str | None) -> Response:
    # Se vacía el tarro de cookies para enviar exactamente el token indicado.
    client.cookies.clear()
    headers = {"Cookie": f"rt={token}"} if token is not None else {}
    response: Response = client.post("/api/auth/refresh", headers=headers)
    return response


def logout_with(client: TestClient, token: str | None) -> Response:
    client.cookies.clear()
    headers = {"Cookie": f"rt={token}"} if token is not None else {}
    response: Response = client.post("/api/auth/logout", headers=headers)
    return response


def me(client: TestClient, token: str) -> Response:
    response: Response = client.get("/api/me", headers={"Authorization": f"Bearer {token}"})
    return response


def assert_validation_error(response: Response, field: str) -> str:
    assert response.status_code == 422, response.text
    body = response.json()
    assert body["statusCode"] == 422
    assert body["code"] == "VALIDATION_ERROR"
    assert field in body["fields"], body
    message = body["fields"][field]
    assert isinstance(message, str)
    return message


def assert_unauthorized(response: Response) -> None:
    assert response.status_code == 401, response.text
    body = response.json()
    assert body["statusCode"] == 401
    assert body["code"] == "UNAUTHORIZED"
    assert isinstance(body["message"], str)
    assert body["message"]


def db_user(email: str) -> User | None:
    with Session(get_engine()) as session:
        return session.scalars(select(User).where(User.email == email)).one_or_none()


def db_user_count() -> int:
    with Session(get_engine()) as session:
        return len(session.scalars(select(User.id).order_by(User.id)).all())


def db_refresh_tokens(uid: str) -> list[RefreshToken]:
    with Session(get_engine()) as session:
        stmt = (
            select(RefreshToken)
            .where(RefreshToken.user_id == uuid.UUID(uid))
            .order_by(RefreshToken.expires_at, RefreshToken.id)
        )
        return list(session.scalars(stmt).all())


def b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


# ---------- Registro (R2.1, R2.2, R2.3, R2.8) ----------


def test_registro_devuelve_201_token_usuario_y_cookie(client: TestClient) -> None:
    response = register(client)

    assert response.status_code == 201, response.text
    body = response.json()
    assert set(body) == {"accessToken", "user"}
    assert isinstance(body["accessToken"], str)
    assert body["accessToken"]
    user = body["user"]
    assert set(user) == USER_KEYS
    assert user["name"] == "Ana"
    assert user["email"] == "ana@ejemplo.com"
    assert user["role"] == "LEARNER"
    assert user["dailyGoalMinutes"] == 10
    assert user["dominantHand"] == "right"
    uuid.UUID(user["id"])


def test_registro_cookie_rt_httponly_path_auth_samesite_lax_sin_secure(
    client: TestClient,
) -> None:
    response = register(client)

    header = rt_set_cookie_header(response)
    attrs = [part.strip().lower() for part in header.split(";")]
    assert "httponly" in attrs
    assert "path=/api/auth" in attrs
    assert "samesite=lax" in attrs
    assert "secure" not in attrs  # desarrollo/pruebas: http


def test_registro_no_devuelve_contrasena_ni_hash(client: TestClient) -> None:
    response = register(client)

    assert PASSWORD not in response.text
    assert "$2b$" not in response.text
    assert "password" not in response.text.lower()


def test_registro_normaliza_correo_con_espacios_y_mayusculas(client: TestClient) -> None:
    response = register(client, email="  Ana@Ejemplo.COM ")

    assert response.status_code == 201, response.text
    assert response.json()["user"]["email"] == "ana@ejemplo.com"
    assert db_user("ana@ejemplo.com") is not None


def test_registro_acepta_introcompleted_opcional(client: TestClient) -> None:
    response = register(client, introCompleted=True)

    assert response.status_code == 201, response.text


def test_registro_guarda_hash_bcrypt_costo_12_sin_la_contrasena(client: TestClient) -> None:
    register(client)

    user = db_user("ana@ejemplo.com")
    assert user is not None
    assert user.password_hash.startswith("$2b$12$")
    assert PASSWORD not in user.password_hash


def test_registro_correo_repetido_da_409(client: TestClient) -> None:
    assert register(client).status_code == 201

    response = register(client)

    assert response.status_code == 409
    assert response.json() == EMAIL_TAKEN


@pytest.mark.parametrize("variant", ["ANA@ejemplo.com", "  ana@ejemplo.com  ", " Ana@Ejemplo.COM"])
def test_registro_correo_repetido_con_otras_mayusculas_o_espacios_da_409(
    client: TestClient, variant: str
) -> None:
    assert register(client).status_code == 201

    response = register(client, email=variant)

    assert response.status_code == 409
    assert response.json() == EMAIL_TAKEN
    assert db_user_count() == 1


@pytest.mark.parametrize(
    "password",
    ["a" * 8, "a" * 72, "ñ" * 36, "ñ" * 4],  # 8, 72, 72 y 8 bytes UTF-8
    ids=["8-ascii", "72-ascii", "72-bytes-con-ñ", "8-bytes-con-ñ"],
)
def test_registro_acepta_contrasena_entre_8_y_72_bytes(client: TestClient, password: str) -> None:
    response = register(client, password=password)

    assert response.status_code == 201, response.text
    assert login(client, "ana@ejemplo.com", password).status_code == 200


@pytest.mark.parametrize(
    "password",
    ["a" * 7, "a" * 73, "ñ" * 37, "ñ" * 3 + "a", "a" * 1000, "ñ" * 500],
    ids=["7-ascii", "73-ascii", "74-bytes-con-ñ", "7-bytes-con-ñ", "1000-ascii", "1000-bytes-ñ"],
)
def test_registro_rechaza_contrasena_fuera_de_8_a_72_bytes_sin_500(
    client: TestClient, password: str
) -> None:
    response = register(client, password=password)

    assert response.status_code != 500  # B27
    assert assert_validation_error(response, "password") == PASSWORD_MESSAGE
    assert db_user_count() == 0


@pytest.mark.parametrize("email", ["no-es-correo", "ana@", "@ejemplo.com", "ana ejemplo@x.co", ""])
def test_registro_rechaza_correo_invalido(client: TestClient, email: str) -> None:
    response = register(client, email=email)

    assert assert_validation_error(response, "email") == EMAIL_MESSAGE
    assert db_user_count() == 0


def test_registro_rechaza_politica_no_aceptada(client: TestClient) -> None:
    response = register(client, acceptedDataPolicy=False)

    assert assert_validation_error(response, "acceptedDataPolicy") == POLICY_MESSAGE
    assert db_user_count() == 0


def test_registro_rechaza_politica_ausente(client: TestClient) -> None:
    body = register_body()
    del body["acceptedDataPolicy"]

    response = client.post("/api/auth/register", json=body)

    message = assert_validation_error(response, "acceptedDataPolicy")
    assert message in {POLICY_MESSAGE, MISSING_MESSAGE}
    assert db_user_count() == 0


@pytest.mark.parametrize("minutes", [5, 10, 15, 20])
def test_registro_acepta_metas_diarias_validas(client: TestClient, minutes: int) -> None:
    response = register(client, dailyGoalMinutes=minutes)

    assert response.status_code == 201, response.text
    assert response.json()["user"]["dailyGoalMinutes"] == minutes


@pytest.mark.parametrize("minutes", [0, 1, 7, 25, 30, -5])
def test_registro_rechaza_meta_diaria_fuera_de_las_opciones(
    client: TestClient, minutes: int
) -> None:
    response = register(client, dailyGoalMinutes=minutes)

    assert_validation_error(response, "dailyGoalMinutes")
    assert db_user_count() == 0


def test_registro_rechaza_campo_extra_role_admin_sin_crear_usuario(client: TestClient) -> None:
    response = register(client, role="ADMIN")

    assert response.status_code == 422, response.text
    assert response.json()["code"] == "VALIDATION_ERROR"
    assert db_user_count() == 0


@pytest.mark.parametrize("missing", ["name", "email", "password", "dailyGoalMinutes"])
def test_registro_rechaza_campos_obligatorios_ausentes(client: TestClient, missing: str) -> None:
    body = register_body()
    del body[missing]

    response = client.post("/api/auth/register", json=body)

    assert_validation_error(response, missing)
    assert db_user_count() == 0


# ---------- Inicio de sesión (R2.4, B17, B28) ----------


def test_login_devuelve_200_mismo_cuerpo_y_cookie_nueva(client: TestClient) -> None:
    registered = register(client)
    first_cookie = rt_cookie(registered)

    response = login(client, "ana@ejemplo.com")

    assert response.status_code == 200, response.text
    body = response.json()
    assert set(body) == {"accessToken", "user"}
    assert body["user"] == registered.json()["user"]
    assert rt_cookie(response) != first_cookie
    attrs = [p.strip().lower() for p in rt_set_cookie_header(response).split(";")]
    assert "httponly" in attrs
    assert "path=/api/auth" in attrs


@pytest.mark.parametrize("variant", ["ANA@EJEMPLO.COM", "  ana@ejemplo.com ", " Ana@Ejemplo.Com"])
def test_login_con_correo_en_otras_mayusculas_o_espacios_funciona(
    client: TestClient, variant: str
) -> None:
    register(client)

    response = login(client, variant)

    assert response.status_code == 200, response.text
    assert response.json()["user"]["email"] == "ana@ejemplo.com"


def test_login_contrasena_incorrecta_da_401_generico(client: TestClient) -> None:
    register(client)

    response = login(client, "ana@ejemplo.com", "otra-clave-123")

    assert response.status_code == 401
    assert response.json() == INVALID_CREDENTIALS
    assert "rt=" not in ";".join(response.headers.get_list("set-cookie"))


def test_login_correo_inexistente_da_el_mismo_401(client: TestClient) -> None:
    register(client)

    wrong_password = login(client, "ana@ejemplo.com", "otra-clave-123")
    unknown_email = login(client, "nadie@ejemplo.com")

    assert unknown_email.status_code == 401
    assert unknown_email.json() == INVALID_CREDENTIALS
    assert unknown_email.json() == wrong_password.json()  # R2.4: no revela cuál falló


def test_login_con_contrasena_larga_no_da_500(client: TestClient) -> None:
    register(client)

    response = login(client, "ana@ejemplo.com", "ñ" * 500)

    assert response.status_code in {401, 422}
    assert response.status_code != 500


def test_login_rechaza_campos_extra(client: TestClient) -> None:
    register(client)

    response = client.post(
        "/api/auth/login",
        json={"email": "ana@ejemplo.com", "password": PASSWORD, "role": "ADMIN"},
    )

    assert response.status_code == 422


# ---------- Límites de peticiones (R2.5, §11) ----------


def test_login_sexto_intento_en_un_minuto_da_429_aunque_sea_correcto(
    client: TestClient,
) -> None:
    register(client)
    for _ in range(5):
        assert login(client, "ana@ejemplo.com", "mala-clave-1").status_code == 401

    response = login(client, "ana@ejemplo.com")

    assert response.status_code == 429
    assert response.json() == TOO_MANY_REQUESTS


def test_login_limite_cuenta_el_correo_normalizado(client: TestClient) -> None:
    register(client)
    for variant in ["ana@ejemplo.com", "ANA@ejemplo.com", " ana@ejemplo.com", "Ana@Ejemplo.com"]:
        assert login(client, variant, "mala-clave-1").status_code == 401
    assert login(client, "ana@EJEMPLO.com", "mala-clave-1").status_code == 401

    response = login(client, "  ANA@EJEMPLO.COM  ")

    assert response.status_code == 429
    assert response.json() == TOO_MANY_REQUESTS


def test_login_limite_no_afecta_a_otro_correo_desde_la_misma_ip(client: TestClient) -> None:
    register(client, email="ana@ejemplo.com")
    register(client, email="luis@ejemplo.com")
    for _ in range(6):
        login(client, "ana@ejemplo.com", "mala-clave-1")
    assert login(client, "ana@ejemplo.com").status_code == 429

    response = login(client, "luis@ejemplo.com")

    assert response.status_code == 200, response.text


def test_login_no_se_salta_el_limite_falsificando_x_forwarded_for(client: TestClient) -> None:
    """Sin proxies de confianza (por defecto) `X-Forwarded-For` se ignora: cambiarlo en cada
    intento no da intentos nuevos (D-035)."""
    register(client)
    for n in range(5):
        response = client.post(
            "/api/auth/login",
            json={"email": "ana@ejemplo.com", "password": "mala-clave-1"},
            headers={"X-Forwarded-For": f"6.6.6.{n}"},
        )
        assert response.status_code == 401

    response = client.post(
        "/api/auth/login",
        json={"email": "ana@ejemplo.com", "password": PASSWORD},
        headers={"X-Forwarded-For": "6.6.6.99"},
    )

    assert response.status_code == 429


def test_detras_de_un_proxy_el_limite_usa_la_ip_que_agrego_el_proxy(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Con TRUSTED_PROXY_HOPS=1 (Render) cuenta la IP que agregó el proxy, no la que inventa el
    cliente al principio; y dos personas reales detrás del mismo proxy no se bloquean entre sí."""
    from app.core.config import get_settings

    monkeypatch.setattr(get_settings(), "trusted_proxy_hops", 1)
    register(client)

    def attempt(forwarded: str, password: str) -> int:
        response = client.post(
            "/api/auth/login",
            json={"email": "ana@ejemplo.com", "password": password},
            headers={"X-Forwarded-For": forwarded},
        )
        return response.status_code

    for n in range(5):
        assert attempt(f"6.6.6.{n}, 1.2.3.4", "mala-clave-1") == 401
    assert attempt("6.6.6.99, 1.2.3.4", PASSWORD) == 429  # mismo atacante, otro valor falso
    assert attempt("5.6.7.8", PASSWORD) == 200  # otra persona real, otra IP


def test_registro_undecimo_desde_la_misma_ip_da_429(client: TestClient) -> None:
    for i in range(10):
        assert register(client, email=f"persona{i}@ejemplo.com").status_code == 201

    response = register(client, email="persona10@ejemplo.com")

    assert response.status_code == 429
    assert response.json() == TOO_MANY_REQUESTS
    assert db_user("persona10@ejemplo.com") is None


def test_limite_por_usuario_en_rutas_autenticadas(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(_rate_limit_module(), "USER_LIMIT", "3/minute")
    ana = access_token(register(client, email="ana@ejemplo.com"))
    luis = access_token(register(client, email="luis@ejemplo.com"))
    for _ in range(3):
        assert me(client, ana).status_code == 200

    blocked = me(client, ana)
    other = me(client, luis)

    assert blocked.status_code == 429
    assert blocked.json()["code"] == "TOO_MANY_REQUESTS"
    assert other.status_code == 200, other.text  # por usuario, no por IP


def test_constantes_de_limite_por_defecto() -> None:
    module = _rate_limit_module()

    assert module.LOGIN_LIMIT == "5/minute"
    assert module.REGISTER_LIMIT == "10/minute"
    assert module.USER_LIMIT == "240/minute"


# ---------- Renovación (R2.6, §11) ----------


def test_refresh_devuelve_token_usuario_y_rota_la_cookie(client: TestClient) -> None:
    registered = register(client)
    old_cookie = rt_cookie(registered)

    response = refresh_with(client, old_cookie)

    assert response.status_code == 200, response.text
    body = response.json()
    assert set(body) == {"accessToken", "user"}
    assert body["user"] == registered.json()["user"]
    new_cookie = rt_cookie(response)
    assert new_cookie != old_cookie
    attrs = [p.strip().lower() for p in rt_set_cookie_header(response).split(";")]
    assert "httponly" in attrs
    assert "path=/api/auth" in attrs
    assert "samesite=lax" in attrs
    assert me(client, access_token(response)).status_code == 200


def test_refresh_con_la_cookie_anterior_da_401(client: TestClient) -> None:
    old_cookie = rt_cookie(register(client))
    new_cookie = rt_cookie(refresh_with(client, old_cookie))

    reused = refresh_with(client, old_cookie)

    assert_unauthorized(reused)
    assert new_cookie != old_cookie


def test_refresh_usa_el_tarro_de_cookies_del_cliente(client: TestClient) -> None:
    register(client)  # el cliente guarda la cookie rt (Path=/api/auth)

    response = client.post("/api/auth/refresh")

    assert response.status_code == 200, response.text


def test_refresh_sin_cookie_da_401(client: TestClient) -> None:
    register(client)

    assert_unauthorized(refresh_with(client, None))


def test_refresh_con_cookie_inventada_da_401(client: TestClient) -> None:
    register(client)

    assert_unauthorized(refresh_with(client, "token-inventado-que-no-existe"))


def test_refresh_vencido_tras_7_dias_da_401(client: TestClient, clock: FakeClock) -> None:
    register(client)
    cookie = rt_cookie(login(client, "ana@ejemplo.com"))

    clock.advance(days=7, minutes=1)

    assert_unauthorized(refresh_with(client, cookie))


def test_refresh_aun_valido_antes_de_7_dias(client: TestClient, clock: FakeClock) -> None:
    register(client)
    cookie = rt_cookie(login(client, "ana@ejemplo.com"))

    clock.advance(days=6, hours=23)

    assert refresh_with(client, cookie).status_code == 200


def test_refresh_token_en_bd_es_sha256_y_no_el_valor_de_la_cookie(client: TestClient) -> None:
    response = register(client)
    cookie = rt_cookie(response)

    tokens = db_refresh_tokens(user_id(response))

    assert len(tokens) == 1
    assert re.fullmatch(r"[0-9a-f]{64}", tokens[0].token_hash)
    assert tokens[0].token_hash != cookie
    assert cookie not in tokens[0].token_hash


def test_refresh_expires_at_lo_fija_el_clock(client: TestClient, clock: FakeClock) -> None:
    start = clock.now()
    response = register(client)

    tokens = db_refresh_tokens(user_id(response))

    assert len(tokens) == 1
    assert tokens[0].expires_at == start + timedelta(days=7)
    assert tokens[0].revoked_at is None


def test_refresh_revoca_el_anterior_en_bd_con_la_hora_del_clock(
    client: TestClient, clock: FakeClock
) -> None:
    response = register(client)
    clock.advance(hours=1)
    moment = clock.now()

    refresh_with(client, rt_cookie(response))

    tokens = db_refresh_tokens(user_id(response))
    assert len(tokens) == 2
    old, new = tokens
    assert old.revoked_at == moment
    assert new.revoked_at is None
    assert new.expires_at == moment + timedelta(days=7)


# ---------- Cierre de sesión (R2.7) ----------


def test_logout_da_204_borra_cookie_y_revoca(client: TestClient) -> None:
    response = register(client)
    cookie = rt_cookie(response)

    out = logout_with(client, cookie)

    assert out.status_code == 204
    assert out.content == b""
    header = rt_set_cookie_header(out)
    lowered = header.lower()
    assert "max-age=0" in lowered or "expires=" in lowered
    assert "path=/api/auth" in lowered
    assert_unauthorized(refresh_with(client, cookie))


def test_logout_marca_revoked_at_en_bd(client: TestClient, clock: FakeClock) -> None:
    response = register(client)
    clock.advance(minutes=5)
    moment = clock.now()

    logout_with(client, rt_cookie(response))

    tokens = db_refresh_tokens(user_id(response))
    assert len(tokens) == 1
    assert tokens[0].revoked_at == moment


def test_logout_sin_cookie_da_204(client: TestClient) -> None:
    assert logout_with(client, None).status_code == 204


def test_logout_con_cookie_inventada_da_204(client: TestClient) -> None:
    assert logout_with(client, "no-existe").status_code == 204


def test_logout_dos_veces_da_204(client: TestClient) -> None:
    cookie = rt_cookie(register(client))

    assert logout_with(client, cookie).status_code == 204
    assert logout_with(client, cookie).status_code == 204


# ---------- /me (R2.6, §11) ----------


def test_me_con_bearer_devuelve_el_usuario(client: TestClient) -> None:
    registered = register(client)

    response = me(client, access_token(registered))

    assert response.status_code == 200, response.text
    assert response.json() == registered.json()["user"]


def test_me_sin_cabecera_da_401(client: TestClient) -> None:
    register(client)

    assert_unauthorized(client.get("/api/me"))


@pytest.mark.parametrize("header", ["Bearer", "Bearer basura.no.jwt", "Token abc", "basura"])
def test_me_con_token_invalido_da_401(client: TestClient, header: str) -> None:
    register(client)

    assert_unauthorized(client.get("/api/me", headers={"Authorization": header}))


def test_me_con_token_firmado_con_otro_secreto_da_401(client: TestClient) -> None:
    uid = user_id(register(client))
    forged = jwt.encode(
        {
            "sub": uid,
            "role": "ADMIN",
            "exp": datetime.now(UTC) + timedelta(minutes=10),
        },
        "otro-secreto-de-al-menos-treinta-y-dos-caracteres",
        algorithm="HS256",
    )

    assert_unauthorized(me(client, forged))


def test_me_con_token_alg_none_da_401(client: TestClient) -> None:
    uid = user_id(register(client))
    exp = int((datetime.now(UTC) + timedelta(minutes=10)).timestamp())
    header = b64url(json.dumps({"alg": "none", "typ": "JWT"}).encode())
    payload = b64url(json.dumps({"sub": uid, "role": "ADMIN", "exp": exp}).encode())

    assert_unauthorized(me(client, f"{header}.{payload}."))


def test_me_con_access_token_vencido_da_401(client: TestClient, clock: FakeClock) -> None:
    token = access_token(register(client))
    clock.advance(minutes=15, seconds=1)

    assert_unauthorized(me(client, token))


def test_me_con_access_token_aun_vigente(client: TestClient, clock: FakeClock) -> None:
    token = access_token(register(client))
    clock.advance(minutes=14, seconds=50)

    assert me(client, token).status_code == 200


def test_me_con_token_de_usuario_borrado_da_401(client: TestClient) -> None:
    response = register(client)
    token = access_token(response)
    with Session(get_engine()) as session, session.begin():
        user = session.get(User, uuid.UUID(user_id(response)))
        assert user is not None
        session.delete(user)

    assert_unauthorized(me(client, token))


def test_patch_me_actualiza_campos_permitidos(client: TestClient) -> None:
    token = access_token(register(client))

    response = client.patch(
        "/api/me",
        headers={"Authorization": f"Bearer {token}"},
        json={"name": "Ana María", "dailyGoalMinutes": 20, "dominantHand": "left"},
    )

    assert response.status_code == 200, response.text
    user = response.json()
    assert user["name"] == "Ana María"
    assert user["dailyGoalMinutes"] == 20
    assert user["dominantHand"] == "left"
    assert user["email"] == "ana@ejemplo.com"
    assert me(client, token).json() == user
    stored = db_user("ana@ejemplo.com")
    assert stored is not None
    assert stored.dominant_hand == "left"
    assert stored.daily_goal_minutes == 20


def test_patch_me_parcial_solo_cambia_lo_enviado(client: TestClient) -> None:
    token = access_token(register(client))

    response = client.patch(
        "/api/me", headers={"Authorization": f"Bearer {token}"}, json={"dominantHand": "left"}
    )

    assert response.status_code == 200, response.text
    assert response.json()["name"] == "Ana"
    assert response.json()["dailyGoalMinutes"] == 10
    assert response.json()["dominantHand"] == "left"


@pytest.mark.parametrize(
    "body",
    [
        {"email": "otro@ejemplo.com"},
        {"role": "ADMIN"},
        {"totalXp": 99999},
        {"password": "nueva-clave-123"},
    ],
    ids=["email", "role", "totalXp", "password"],
)
def test_patch_me_rechaza_campos_no_permitidos(client: TestClient, body: dict[str, object]) -> None:
    token = access_token(register(client))

    response = client.patch("/api/me", headers={"Authorization": f"Bearer {token}"}, json=body)

    assert response.status_code == 422, response.text
    stored = db_user("ana@ejemplo.com")
    assert stored is not None
    assert stored.role.value == "LEARNER"
    assert stored.total_xp == 0


def test_patch_me_rechaza_mano_dominante_both(client: TestClient) -> None:
    token = access_token(register(client))

    response = client.patch(
        "/api/me", headers={"Authorization": f"Bearer {token}"}, json={"dominantHand": "both"}
    )

    assert_validation_error(response, "dominantHand")


def test_patch_me_rechaza_meta_diaria_invalida(client: TestClient) -> None:
    token = access_token(register(client))

    response = client.patch(
        "/api/me", headers={"Authorization": f"Bearer {token}"}, json={"dailyGoalMinutes": 7}
    )

    assert_validation_error(response, "dailyGoalMinutes")


def test_patch_me_sin_token_da_401(client: TestClient) -> None:
    register(client)

    assert_unauthorized(client.patch("/api/me", json={"name": "X"}))


# ---------- Revisión del Grupo 3 ---------------------------------------------------------------


def test_login_no_acepta_una_contrasena_que_solo_empieza_igual(client: TestClient) -> None:
    """bcrypt solo mira 72 bytes: «a»*72 + «x» no debe abrir la cuenta de «a»*72."""
    body = {
        "name": "Ana",
        "email": "prefijo@alasdesenas.test",
        "password": "a" * 72,
        "dailyGoalMinutes": 10,
        "acceptedDataPolicy": True,
    }
    assert client.post("/api/auth/register", json=body).status_code == 201
    client.cookies.clear()
    wrong = client.post(
        "/api/auth/login", json={"email": body["email"], "password": "a" * 72 + "x"}
    )
    assert wrong.status_code == 401
    assert wrong.json()["code"] == "INVALID_CREDENTIALS"


def test_patch_me_no_acepta_un_nombre_en_blanco(client: TestClient) -> None:
    body = {
        "name": "Ana",
        "email": "blanco@alasdesenas.test",
        "password": "Clave-Segura-1",
        "dailyGoalMinutes": 10,
        "acceptedDataPolicy": True,
    }
    token = client.post("/api/auth/register", json=body).json()["accessToken"]
    response = client.patch(
        "/api/me", json={"name": "   "}, headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 422
    assert "name" in response.json()["fields"]


def test_refresh_fallido_borra_la_cookie(client: TestClient) -> None:
    client.cookies.clear()
    response = client.post("/api/auth/refresh", headers={"Cookie": "rt=inventada"})
    assert response.status_code == 401
    set_cookie = response.headers.get("set-cookie", "")
    assert "rt=" in set_cookie
    assert "Max-Age=0" in set_cookie or "expires=" in set_cookie.lower()


def test_cookie_secure_en_produccion(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.core.config import Settings, get_settings
    from app.main import create_app

    production = Settings(
        _env_file=None,
        app_env="production",
        database_url=get_settings().database_url,
        jwt_secret="secreto-de-produccion-con-mas-de-32-caracteres",
    )
    app = create_app(production)
    app.dependency_overrides[get_settings] = lambda: production
    client = TestClient(app, base_url="https://testserver")
    body = {
        "name": "Ana",
        "email": "seguro@alasdesenas.test",
        "password": "Clave-Segura-1",
        "dailyGoalMinutes": 10,
        "acceptedDataPolicy": True,
    }
    response = client.post("/api/auth/register", json=body)
    assert response.status_code == 201
    assert "Secure" in response.headers["set-cookie"]
    logout = client.post("/api/auth/logout")
    assert "Secure" in logout.headers["set-cookie"]


# ---------- Autorización de tratamiento de datos (Ley 1581 de 2012, D-037) ----------


def test_registro_guarda_cuando_y_que_version_de_la_politica_se_acepto(
    client: TestClient, clock: FakeClock
) -> None:
    from app.core.privacy import DATA_POLICY_VERSION

    assert register(client).status_code == 201

    user = db_user("ana@ejemplo.com")
    assert user is not None
    assert user.data_policy_accepted_at == clock.now()  # la fija el servidor (D22)
    assert user.data_policy_version == DATA_POLICY_VERSION


def test_el_cliente_no_puede_fijar_la_fecha_ni_la_version_de_la_autorizacion(
    client: TestClient,
) -> None:
    response = register(
        client, dataPolicyAcceptedAt="2020-01-01T00:00:00Z", dataPolicyVersion="falsa"
    )

    assert response.status_code == 422  # extra="forbid"
    assert db_user("ana@ejemplo.com") is None

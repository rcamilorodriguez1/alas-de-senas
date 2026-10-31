import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import {
  bearer,
  deferred,
  emptyResponse,
  errorBody,
  jsonResponse,
  makeAuth,
  makeUser,
  mockFetch,
  type RecordedRequest,
} from "../test/http";
import {
  ApiError,
  apiRequest,
  fetchHealth,
  fetchMe,
  login,
  logout,
  refreshSession,
  register,
  setSessionExpiredHandler,
} from "./api";
import { shouldRetry } from "./query-client";
import { useSessionStore } from "./session-store";

const OLD = "token-viejo";
const NEW = "token-nuevo";
const unauthorized = () => jsonResponse(401, errorBody(401, "UNAUTHORIZED", "Inicia sesión."));
const notFound = () => jsonResponse(404, errorBody(404, "NOT_FOUND", "No existe."));

function signIn(token = OLD) {
  useSessionStore.getState().setSession(token, makeUser());
}

beforeEach(() => {
  useSessionStore.setState(useSessionStore.getInitialState(), true);
  setSessionExpiredHandler(() => undefined);
  window.history.pushState({}, "", "/");
});

afterEach(() => {
  vi.unstubAllGlobals();
  vi.useRealTimers();
});

describe("apiRequest: formato de la petición", () => {
  it("llama a /api<ruta> con el token en Authorization: Bearer cuando hay sesión", async () => {
    signIn();
    const http = mockFetch(() => jsonResponse(200, { ok: true }));
    const result = await apiRequest<{ ok: boolean }>("GET", "/learning-path");
    expect(result).toEqual({ ok: true });
    expect(http.requests).toHaveLength(1);
    expect(http.requests[0].path).toBe("/api/learning-path");
    expect(http.requests[0].method).toBe("GET");
    expect(bearer(http.requests[0])).toBe(`Bearer ${OLD}`);
  });

  it("envía el cuerpo como JSON con Content-Type application/json", async () => {
    signIn();
    const http = mockFetch(() => jsonResponse(200, { correct: true }));
    await apiRequest("POST", "/lesson-sessions/s1/answers", {
      body: { exerciseId: "e1", answer: "tok" },
    });
    const request = http.requests[0];
    expect(request.method).toBe("POST");
    expect(request.headers.get("Content-Type")).toContain("application/json");
    expect(request.body).toEqual({ exerciseId: "e1", answer: "tok" });
  });

  it("no envía Authorization si auth es false aunque haya token", async () => {
    signIn();
    const http = mockFetch(() => jsonResponse(200, { cards: [] }));
    await apiRequest("GET", "/intro", { auth: false });
    expect(bearer(http.requests[0])).toBeNull();
  });

  it("no envía Authorization si no hay token", async () => {
    useSessionStore.getState().clearSession();
    const http = mockFetch(() => jsonResponse(200, { items: [] }));
    await apiRequest("GET", "/dictionary/categories", { auth: false });
    expect(bearer(http.requests[0])).toBeNull();
  });

  it("devuelve undefined cuando la respuesta es 204", async () => {
    signIn();
    mockFetch(() => emptyResponse(204));
    await expect(apiRequest("DELETE", "/dictionary/favorites/hola")).resolves.toBeUndefined();
  });
});

describe("apiRequest: errores", () => {
  it("convierte un error no 2xx en ApiError con status, code, message y fields", async () => {
    signIn();
    mockFetch(() =>
      jsonResponse(
        422,
        errorBody(422, "VALIDATION_ERROR", "Revisa los datos.", { email: "Correo no válido" }),
      ),
    );
    const error = await apiRequest("PATCH", "/me", { body: { name: "" } }).catch(
      (e: unknown) => e,
    );
    expect(error).toBeInstanceOf(ApiError);
    if (!(error instanceof ApiError)) throw new Error("se esperaba ApiError");
    expect(error.status).toBe(422);
    expect(error.code).toBe("VALIDATION_ERROR");
    expect(error.message).toBe("Revisa los datos.");
    expect(error.fields).toEqual({ email: "Correo no válido" });
  });

  it("un 403 con code de negocio llega como ApiError (LESSON_LOCKED)", async () => {
    signIn();
    mockFetch(() =>
      jsonResponse(403, errorBody(403, "LESSON_LOCKED", "Esta lección aún está bloqueada.")),
    );
    await expect(apiRequest("POST", "/lessons/M1-N2-L1/sessions")).rejects.toMatchObject({
      status: 403,
      code: "LESSON_LOCKED",
      message: "Esta lección aún está bloqueada.",
    });
  });

  it("un error sin cuerpo JSON (502 del proxy) también es ApiError con su status", async () => {
    signIn();
    mockFetch(() => new Response("<html>Bad Gateway</html>", { status: 502 }));
    const error = await apiRequest("GET", "/learning-path").catch((e: unknown) => e);
    expect(error).toBeInstanceOf(ApiError);
    if (!(error instanceof ApiError)) throw new Error("se esperaba ApiError");
    expect(error.status).toBe(502);
  });

  it("B25: los ApiError 4xx del cliente no se reintentan con shouldRetry; los 5xx sí", async () => {
    signIn();
    mockFetch((r) =>
      r.path === "/api/a"
        ? jsonResponse(409, errorBody(409, "NOT_ENOUGH_NECTAR", "Te falta néctar."))
        : jsonResponse(500, errorBody(500, "INTERNAL_ERROR", "Error.")),
    );
    const e409 = await apiRequest("POST", "/a").catch((e: unknown) => e);
    const e500 = await apiRequest("POST", "/b").catch((e: unknown) => e);
    expect(shouldRetry(0, e409)).toBe(false);
    expect(shouldRetry(0, e500)).toBe(true);
  });
});

describe("refreshSession", () => {
  it("200 → guarda la nueva sesión y devuelve true (POST con credentials same-origin)", async () => {
    const user = makeUser({ name: "Tomás" });
    const http = mockFetch(() => jsonResponse(200, makeAuth(NEW, user)));
    await expect(refreshSession()).resolves.toBe(true);
    const request = http.to("/api/auth/refresh")[0];
    expect(request.method).toBe("POST");
    expect(request.credentials).toBe("same-origin");
    const state = useSessionStore.getState();
    expect(state.accessToken).toBe(NEW);
    expect(state.user).toEqual(user);
    expect(state.status).toBe("authenticated");
  });

  it("401 → limpia la sesión y devuelve false", async () => {
    signIn();
    mockFetch(() => unauthorized());
    await expect(refreshSession()).resolves.toBe(false);
    const state = useSessionStore.getState();
    expect(state.accessToken).toBeNull();
    expect(state.status).toBe("anonymous");
  });

  it("error de red → limpia la sesión y devuelve false (no rechaza)", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(() => Promise.reject(new TypeError("Failed to fetch"))),
    );
    await expect(refreshSession()).resolves.toBe(false);
    expect(useSessionStore.getState().status).toBe("anonymous");
  });

  it("single-flight: llamadas simultáneas comparten UNA sola petición", async () => {
    const gate = deferred<Response>();
    const http = mockFetch(() => gate.promise);
    const results = Promise.all([refreshSession(), refreshSession(), refreshSession()]);
    gate.resolve(jsonResponse(200, makeAuth(NEW)));
    await expect(results).resolves.toEqual([true, true, true]);
    expect(http.to("/api/auth/refresh")).toHaveLength(1);
  });

  it("una vez resuelto, un refresh posterior hace una petición nueva (no queda en caché)", async () => {
    const http = mockFetch(() => jsonResponse(200, makeAuth(NEW)));
    await refreshSession();
    await refreshSession();
    expect(http.to("/api/auth/refresh")).toHaveLength(2);
  });
});

describe("apiRequest: renovación ante 401", () => {
  it("B22: 3 peticiones simultáneas con token vencido → 1 solo refresh y las 3 se reintentan con el token nuevo", async () => {
    signIn(OLD);
    const oldGate = deferred<null>();
    let oldArrivals = 0;
    const http = mockFetch(async (r: RecordedRequest) => {
      if (r.path === "/api/auth/refresh") {
        // El refresh tarda un poco: da tiempo a que las 3 peticiones reciban su 401.
        await new Promise((resolve) => setTimeout(resolve, 20));
        return jsonResponse(200, makeAuth(NEW));
      }
      if (bearer(r) === `Bearer ${OLD}`) {
        oldArrivals += 1;
        if (oldArrivals === 3) oldGate.resolve(null);
        await oldGate.promise;
        return unauthorized();
      }
      if (bearer(r) === `Bearer ${NEW}`) {
        return jsonResponse(200, { path: r.path });
      }
      return unauthorized();
    });

    const results = await Promise.all([
      apiRequest<{ path: string }>("GET", "/learning-path"),
      apiRequest<{ path: string }>("GET", "/gamification/stats"),
      apiRequest<{ path: string }>("GET", "/reviews/queue"),
    ]);

    expect(results).toEqual([
      { path: "/api/learning-path" },
      { path: "/api/gamification/stats" },
      { path: "/api/reviews/queue" },
    ]);
    expect(http.to("/api/auth/refresh")).toHaveLength(1);
    const retried = http.requests.filter((r) => bearer(r) === `Bearer ${NEW}`);
    expect(retried.map((r) => r.path).sort()).toEqual([
      "/api/gamification/stats",
      "/api/learning-path",
      "/api/reviews/queue",
    ]);
    expect(useSessionStore.getState().accessToken).toBe(NEW);
    expect(useSessionStore.getState().status).toBe("authenticated");
  });

  it("401 y refresh fallido → cierra sesión, avisa con la ruta actual y lanza ApiError 401", async () => {
    signIn(OLD);
    window.history.pushState({}, "", "/leccion/M1-N1-L2?paso=3");
    const onExpired = vi.fn();
    setSessionExpiredHandler(onExpired);
    const http = mockFetch(() => unauthorized());

    const error = await apiRequest("GET", "/learning-path").catch((e: unknown) => e);

    expect(error).toBeInstanceOf(ApiError);
    if (!(error instanceof ApiError)) throw new Error("se esperaba ApiError");
    expect(error.status).toBe(401);
    expect(http.to("/api/auth/refresh")).toHaveLength(1);
    expect(http.to("/api/learning-path")).toHaveLength(1);
    expect(useSessionStore.getState().status).toBe("anonymous");
    expect(useSessionStore.getState().accessToken).toBeNull();
    expect(onExpired).toHaveBeenCalledWith("/leccion/M1-N1-L2?paso=3");
  });

  it("401, refresh exitoso y reintento con 401 otra vez → reintenta UNA sola vez, cierra sesión y avisa", async () => {
    signIn(OLD);
    window.history.pushState({}, "", "/progreso");
    const onExpired = vi.fn();
    setSessionExpiredHandler(onExpired);
    const http = mockFetch((r) =>
      r.path === "/api/auth/refresh" ? jsonResponse(200, makeAuth(NEW)) : unauthorized(),
    );

    await expect(apiRequest("GET", "/progress/summary")).rejects.toMatchObject({ status: 401 });

    expect(http.to("/api/auth/refresh")).toHaveLength(1);
    expect(http.to("/api/progress/summary")).toHaveLength(2);
    expect(bearer(http.to("/api/progress/summary")[1])).toBe(`Bearer ${NEW}`);
    expect(useSessionStore.getState().status).toBe("anonymous");
    expect(onExpired).toHaveBeenCalledTimes(1);
    expect(onExpired).toHaveBeenCalledWith("/progreso");
  });

  it("un 401 en una petición sin auth no intenta refresh ni cierra la sesión", async () => {
    const onExpired = vi.fn();
    setSessionExpiredHandler(onExpired);
    const http = mockFetch(() => unauthorized());
    await expect(apiRequest("GET", "/intro", { auth: false })).rejects.toMatchObject({
      status: 401,
    });
    expect(http.to("/api/auth/refresh")).toHaveLength(0);
    expect(onExpired).not.toHaveBeenCalled();
  });

  it("errores distintos de 401 no disparan refresh", async () => {
    signIn();
    const http = mockFetch(() => notFound());
    await expect(apiRequest("GET", "/nodes/zzz")).rejects.toMatchObject({ status: 404 });
    expect(http.to("/api/auth/refresh")).toHaveLength(0);
    expect(useSessionStore.getState().status).toBe("authenticated");
  });
});

describe("funciones de autenticación", () => {
  const registerBody = {
    name: "Ana",
    email: "ana@example.com",
    password: "ñññaa",
    dailyGoalMinutes: 10 as const,
    acceptedDataPolicy: true,
  };

  it("register → POST /api/auth/register sin Authorization, guarda la sesión y devuelve AuthOut", async () => {
    useSessionStore.getState().clearSession();
    const auth = makeAuth(NEW);
    const http = mockFetch(() => jsonResponse(201, auth));
    await expect(register(registerBody)).resolves.toEqual(auth);
    const request = http.to("/api/auth/register", "POST")[0];
    expect(request.body).toEqual(registerBody);
    expect(bearer(request)).toBeNull();
    expect(useSessionStore.getState().accessToken).toBe(NEW);
    expect(useSessionStore.getState().status).toBe("authenticated");
  });

  it("register con 409 EMAIL_TAKEN lanza ApiError y no abre sesión", async () => {
    useSessionStore.getState().clearSession();
    mockFetch(() =>
      jsonResponse(409, errorBody(409, "EMAIL_TAKEN", "Ya existe una cuenta con este correo")),
    );
    await expect(register(registerBody)).rejects.toMatchObject({
      status: 409,
      code: "EMAIL_TAKEN",
    });
    expect(useSessionStore.getState().status).toBe("anonymous");
  });

  it("login → POST /api/auth/login sin Authorization, guarda la sesión y devuelve AuthOut", async () => {
    useSessionStore.getState().clearSession();
    const auth = makeAuth(NEW, makeUser({ name: "Camilo" }));
    const http = mockFetch(() => jsonResponse(200, auth));
    await expect(login({ email: "ana@example.com", password: "secreta123" })).resolves.toEqual(
      auth,
    );
    const request = http.to("/api/auth/login", "POST")[0];
    expect(request.body).toEqual({ email: "ana@example.com", password: "secreta123" });
    expect(bearer(request)).toBeNull();
    expect(useSessionStore.getState().user?.name).toBe("Camilo");
  });

  it("login con 401 lanza ApiError, NO intenta refresh y NO avisa de sesión vencida", async () => {
    useSessionStore.getState().clearSession();
    const onExpired = vi.fn();
    setSessionExpiredHandler(onExpired);
    const http = mockFetch(() =>
      jsonResponse(401, errorBody(401, "INVALID_CREDENTIALS", "Correo o contraseña incorrectos")),
    );
    await expect(login({ email: "ana@example.com", password: "malamala" })).rejects.toMatchObject(
      { status: 401, code: "INVALID_CREDENTIALS" },
    );
    expect(http.to("/api/auth/refresh")).toHaveLength(0);
    expect(onExpired).not.toHaveBeenCalled();
    expect(useSessionStore.getState().accessToken).toBeNull();
  });

  it("logout → POST /api/auth/logout y limpia la sesión", async () => {
    signIn();
    const http = mockFetch(() => emptyResponse(204));
    await logout();
    expect(http.to("/api/auth/logout", "POST")).toHaveLength(1);
    expect(useSessionStore.getState().accessToken).toBeNull();
    expect(useSessionStore.getState().status).toBe("anonymous");
  });

  it("logout limpia la sesión aunque falle la red", async () => {
    signIn();
    vi.stubGlobal(
      "fetch",
      vi.fn(() => Promise.reject(new TypeError("Failed to fetch"))),
    );
    await logout().catch(() => undefined);
    expect(useSessionStore.getState().accessToken).toBeNull();
    expect(useSessionStore.getState().status).toBe("anonymous");
  });

  it("fetchMe → GET /api/me con el token", async () => {
    signIn();
    const user = makeUser();
    const http = mockFetch(() => jsonResponse(200, user));
    await expect(fetchMe()).resolves.toEqual(user);
    const request = http.to("/api/me", "GET")[0];
    expect(bearer(request)).toBe(`Bearer ${OLD}`);
  });

  it("fetchHealth sigue funcionando (GET /api/health)", async () => {
    const http = mockFetch(() => jsonResponse(200, { ok: true, db: true }));
    await expect(fetchHealth()).resolves.toEqual({ ok: true, db: true });
    expect(http.to("/api/health")).toHaveLength(1);
  });
});

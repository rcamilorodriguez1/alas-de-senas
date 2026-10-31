import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { components } from "./api-types";
import { ApiError, apiRequest, refreshSession, setSessionExpiredHandler } from "./api";
import { safeReturnPath } from "./navigation";
import { useSessionStore } from "./session-store";

type UserOut = components["schemas"]["UserOut"];

const USER: UserOut = {
  id: "00000000-0000-0000-0000-000000000001",
  name: "Ana",
  email: "ana@alasdesenas.test",
  role: "LEARNER",
  dailyGoalMinutes: 10,
  dominantHand: "right",
};

function json(status: number, body: object): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

beforeEach(() => {
  useSessionStore.setState({ accessToken: "viejo", user: USER, status: "authenticated" });
});

afterEach(() => {
  vi.unstubAllGlobals();
  setSessionExpiredHandler(() => undefined);
});

describe("revisión del Grupo 3: la renovación solo cierra la sesión ante un 401", () => {
  it("un 502 en el refresh no cierra la sesión ni redirige", async () => {
    const expired = vi.fn();
    setSessionExpiredHandler(expired);
    vi.stubGlobal(
      "fetch",
      vi.fn((url: string) =>
        Promise.resolve(
          url.endsWith("/auth/refresh")
            ? json(502, { statusCode: 502, code: "HTTP_ERROR", message: "Caído" })
            : json(401, { statusCode: 401, code: "UNAUTHORIZED", message: "Vencido" }),
        ),
      ),
    );
    await expect(apiRequest("GET", "/me")).rejects.toBeInstanceOf(ApiError);
    expect(useSessionStore.getState().status).toBe("authenticated");
    expect(expired).not.toHaveBeenCalled();
  });

  it("un corte de red en el refresh no cierra la sesión", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn((url: string) =>
        url.endsWith("/auth/refresh")
          ? Promise.reject(new TypeError("Failed to fetch"))
          : Promise.resolve(json(401, { statusCode: 401, code: "UNAUTHORIZED", message: "x" })),
      ),
    );
    await expect(apiRequest("GET", "/me")).rejects.toBeInstanceOf(ApiError);
    expect(useSessionStore.getState().accessToken).toBe("viejo");
  });

  it("al arrancar, un corte de red deja al usuario como anónimo (no se queda cargando)", async () => {
    useSessionStore.setState({ accessToken: null, user: null, status: "loading" });
    vi.stubGlobal("fetch", vi.fn(() => Promise.reject(new TypeError("Failed to fetch"))));
    expect(await refreshSession()).toBe(false);
    expect(useSessionStore.getState().status).toBe("anonymous");
  });

  it("un 401 tardío (el token ya cambió) reintenta sin volver a renovar", async () => {
    const calls: string[] = [];
    vi.stubGlobal(
      "fetch",
      vi.fn((url: string, init: RequestInit) => {
        calls.push(url);
        const auth = new Headers(init.headers).get("Authorization");
        if (auth === "Bearer viejo") {
          // Mientras esta petición iba, otra pestaña de la misma app renovó el token.
          useSessionStore.setState({ accessToken: "nuevo" });
          return Promise.resolve(json(401, { statusCode: 401, code: "UNAUTHORIZED", message: "" }));
        }
        return Promise.resolve(json(200, USER));
      }),
    );
    await expect(apiRequest("GET", "/me")).resolves.toEqual(USER);
    expect(calls.filter((url) => url.endsWith("/auth/refresh"))).toHaveLength(0);
  });
});

describe("revisión del Grupo 3: «volver» solo acepta rutas internas", () => {
  it.each(["/\\evil.com", "/\t/evil.com", "//evil.com", "https://evil.com", "javascript:alert(1)"])(
    "rechaza %j",
    (volver) => {
      expect(safeReturnPath(volver)).toBe("/aprender");
    },
  );

  it("conserva una ruta interna con consulta", () => {
    expect(safeReturnPath("/leccion/M1-N1-L1?x=1")).toBe("/leccion/M1-N1-L1?x=1");
  });

  it("no anida volver hacia las pantallas de ingreso", () => {
    expect(safeReturnPath("/ingresar?volver=%2Faprender")).toBe("/aprender");
  });
});

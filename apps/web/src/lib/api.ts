import type { components } from "./api-types";
import { ApiError } from "./query-client";
import { useSessionStore } from "./session-store";

export { ApiError };

export type HealthOut = components["schemas"]["HealthOut"];
export type ErrorOut = components["schemas"]["ErrorOut"];
export type AuthOut = components["schemas"]["AuthOut"];
export type UserOut = components["schemas"]["UserOut"];
export type RegisterIn = components["schemas"]["RegisterIn"];
export type LoginIn = components["schemas"]["LoginIn"];

type Method = "GET" | "POST" | "PATCH" | "DELETE";

interface RequestOptions {
  body?: unknown;
  /** Envía el token de acceso y renueva la sesión ante un 401 (por defecto, sí). */
  auth?: boolean;
}

let refreshInFlight: Promise<boolean> | null = null;
let onSessionExpired: (volver: string) => void = () => undefined;

/** Qué hacer cuando la sesión no se puede renovar (la app redirige a /ingresar?volver=…). */
export function setSessionExpiredHandler(handler: (volver: string) => void): void {
  onSessionExpired = handler;
}

async function send(method: Method, path: string, body: unknown, token: string | null) {
  const headers: Record<string, string> = {};
  if (body !== undefined) headers["Content-Type"] = "application/json";
  if (token) headers.Authorization = `Bearer ${token}`;
  return fetch(`/api${path}`, {
    method,
    headers,
    body: body === undefined ? undefined : JSON.stringify(body),
    credentials: "same-origin",
  });
}

async function toError(response: Response): Promise<ApiError> {
  const data = (await response.json().catch(() => ({}))) as Partial<ErrorOut>;
  return new ApiError(
    response.status,
    data.code ?? "HTTP_ERROR",
    data.message ?? "No se pudo completar la petición.",
    data.fields ?? undefined,
  );
}

async function parse<T>(response: Response): Promise<T> {
  if (!response.ok) throw await toError(response);
  if (response.status === 204) return undefined as T;
  return (await response.json()) as T;
}

/**
 * Renueva la sesión con la cookie `rt`. Single-flight: las peticiones que reciben 401 a la
 * vez comparten una sola renovación (B22); si no, cada una rotaría el token y cerraría la sesión.
 */
export function refreshSession(): Promise<boolean> {
  refreshInFlight ??= (async () => {
    try {
      const response = await send("POST", "/auth/refresh", undefined, null);
      if (!response.ok) {
        useSessionStore.getState().clearSession();
        return false;
      }
      const data = (await response.json()) as AuthOut;
      useSessionStore.getState().setSession(data.accessToken, data.user);
      return true;
    } catch {
      useSessionStore.getState().clearSession();
      return false;
    } finally {
      refreshInFlight = null;
    }
  })();
  return refreshInFlight;
}

export async function apiRequest<T>(
  method: Method,
  path: string,
  options: RequestOptions = {},
): Promise<T> {
  const { body, auth = true } = options;
  const token = auth ? useSessionStore.getState().accessToken : null;
  const response = await send(method, path, body, token);
  if (response.status !== 401 || !auth) return parse<T>(response);

  if (await refreshSession()) {
    const retry = await send(method, path, body, useSessionStore.getState().accessToken);
    if (retry.status !== 401) return parse<T>(retry);
  }
  useSessionStore.getState().clearSession();
  onSessionExpired(window.location.pathname + window.location.search);
  throw await toError(response);
}

export async function register(body: RegisterIn): Promise<AuthOut> {
  const data = await apiRequest<AuthOut>("POST", "/auth/register", { body, auth: false });
  useSessionStore.getState().setSession(data.accessToken, data.user);
  return data;
}

export async function login(body: LoginIn): Promise<AuthOut> {
  const data = await apiRequest<AuthOut>("POST", "/auth/login", { body, auth: false });
  useSessionStore.getState().setSession(data.accessToken, data.user);
  return data;
}

export async function logout(): Promise<void> {
  try {
    await apiRequest<undefined>("POST", "/auth/logout", { auth: false });
  } catch {
    // Aunque falle la red, la sesión local se cierra igual.
  } finally {
    useSessionStore.getState().clearSession();
  }
}

export function fetchMe(): Promise<UserOut> {
  return apiRequest<UserOut>("GET", "/me");
}

export function fetchHealth(): Promise<HealthOut> {
  return apiRequest<HealthOut>("GET", "/health", { auth: false });
}

/** Compatibilidad con el Grupo 0: GET sin autenticación. */
export function apiGet<T>(path: string): Promise<T> {
  return apiRequest<T>("GET", path, { auth: false });
}

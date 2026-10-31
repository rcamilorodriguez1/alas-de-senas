// Utilidades SOLO para pruebas: simulan la API con `vi.stubGlobal("fetch", ...)`.
// Los tipos de respuesta vienen de `api-types.ts` (generado con `alas gen-api`), nunca escritos a mano.
import { vi } from "vitest";
import type { components } from "../lib/api-types";

export type UserOut = components["schemas"]["UserOut"];
export type AuthOut = components["schemas"]["AuthOut"];
export type ErrorOut = components["schemas"]["ErrorOut"];

export function makeUser(overrides: Partial<UserOut> = {}): UserOut {
  return {
    id: "8f14e45f-ceea-4e7a-9b1c-1a2b3c4d5e6f",
    name: "Ana",
    email: "ana@example.com",
    role: "LEARNER",
    dailyGoalMinutes: 10,
    dominantHand: "right",
    ...overrides,
  };
}

export function makeAuth(accessToken: string, user: UserOut = makeUser()): AuthOut {
  return { accessToken, user };
}

export function errorBody(
  statusCode: number,
  code: string,
  message: string,
  fields?: Record<string, string>,
): ErrorOut {
  return fields ? { statusCode, code, message, fields } : { statusCode, code, message };
}

export function jsonResponse(status: number, body: unknown): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

export function emptyResponse(status = 204): Response {
  return new Response(null, { status });
}

export interface RecordedRequest {
  /** Ruta relativa al origen, con query string (p. ej. `/api/me`). */
  path: string;
  method: string;
  headers: Headers;
  body: unknown;
  credentials: RequestCredentials | undefined;
}

export type FetchHandler = (request: RecordedRequest) => Response | Promise<Response>;

function toPath(url: string): string {
  if (url.startsWith("http://") || url.startsWith("https://")) {
    const parsed = new URL(url);
    return parsed.pathname + parsed.search;
  }
  return url;
}

function parseBody(raw: string | null): unknown {
  if (raw === null || raw === "") {
    return undefined;
  }
  try {
    return JSON.parse(raw);
  } catch {
    return raw;
  }
}

async function record(input: RequestInfo | URL, init?: RequestInit): Promise<RecordedRequest> {
  if (input instanceof Request) {
    const raw = await input.clone().text();
    return {
      path: toPath(input.url),
      method: input.method.toUpperCase(),
      headers: new Headers(input.headers),
      body: parseBody(raw),
      credentials: input.credentials,
    };
  }
  const url = input instanceof URL ? input.href : input;
  const rawBody = init?.body;
  return {
    path: toPath(url),
    method: (init?.method ?? "GET").toUpperCase(),
    headers: new Headers(init?.headers),
    body: parseBody(typeof rawBody === "string" ? rawBody : null),
    credentials: init?.credentials,
  };
}

/** Instala un `fetch` falso y devuelve el registro de peticiones recibidas. */
export function mockFetch(handler: FetchHandler) {
  const requests: RecordedRequest[] = [];
  const fn = vi.fn(async (input: RequestInfo | URL, init?: RequestInit): Promise<Response> => {
    const request = await record(input, init);
    requests.push(request);
    return handler(request);
  });
  vi.stubGlobal("fetch", fn);
  return {
    fn,
    requests,
    to(path: string, method?: string): RecordedRequest[] {
      return requests.filter(
        (r) => r.path === path && (method === undefined || r.method === method.toUpperCase()),
      );
    },
  };
}

export function deferred<T>() {
  let resolve: (value: T) => void = () => undefined;
  const promise = new Promise<T>((res) => {
    resolve = res;
  });
  return { promise, resolve };
}

export function bearer(request: RecordedRequest): string | null {
  return request.headers.get("Authorization");
}

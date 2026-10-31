import type { components } from "./api-types";
import { ApiError } from "./query-client";

export type HealthOut = components["schemas"]["HealthOut"];
export type ErrorOut = components["schemas"]["ErrorOut"];

/** GET a la API del mismo origen (D1). Los errores llegan como `{ statusCode, code, message }`. */
export async function apiGet<T>(path: string): Promise<T> {
  const response = await fetch(`/api${path}`, { credentials: "same-origin" });
  if (!response.ok) {
    const body = (await response.json().catch(() => ({}))) as Partial<ErrorOut>;
    throw new ApiError(
      response.status,
      body.code ?? "HTTP_ERROR",
      body.message ?? "No se pudo completar la petición.",
    );
  }
  return (await response.json()) as T;
}

export function fetchHealth(): Promise<HealthOut> {
  return apiGet<HealthOut>("/health");
}

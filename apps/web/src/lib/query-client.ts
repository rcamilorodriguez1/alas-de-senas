import { QueryClient } from "@tanstack/react-query";

export class ApiError extends Error {
  readonly status: number;
  readonly code: string;
  /** Mensajes en español por campo (solo VALIDATION_ERROR). */
  readonly fields?: Record<string, string>;
  /** Cuándo llega la próxima vida (solo NO_HEARTS, §7.10). */
  readonly nextHeartAt: string | null;

  constructor(
    status: number,
    code: string,
    message: string,
    fields?: Record<string, string>,
    nextHeartAt: string | null = null,
  ) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.code = code;
    this.fields = fields;
    this.nextHeartAt = nextHeartAt;
  }
}

/** No se reintentan los errores 4xx: repetir la misma petición daría el mismo error (§3). */
export function shouldRetry(failureCount: number, error: unknown): boolean {
  if (error instanceof ApiError && error.status >= 400 && error.status < 500) {
    return false;
  }
  return failureCount < 2;
}

export function createQueryClient(): QueryClient {
  return new QueryClient({
    defaultOptions: {
      queries: { retry: shouldRetry, refetchOnWindowFocus: false },
      mutations: { retry: false },
    },
  });
}

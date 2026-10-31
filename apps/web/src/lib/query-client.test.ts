import { describe, expect, it } from "vitest";
import { ApiError, shouldRetry } from "./query-client";

describe("shouldRetry", () => {
  it("no reintenta errores 4xx", () => {
    expect(shouldRetry(0, new ApiError(403, "LESSON_LOCKED", "Bloqueada"))).toBe(false);
    expect(shouldRetry(0, new ApiError(404, "NOT_FOUND", "No existe"))).toBe(false);
  });

  it("reintenta errores 5xx y de red hasta dos veces", () => {
    expect(shouldRetry(0, new ApiError(503, "HTTP_ERROR", "Caído"))).toBe(true);
    expect(shouldRetry(1, new TypeError("Failed to fetch"))).toBe(true);
    expect(shouldRetry(2, new TypeError("Failed to fetch"))).toBe(false);
  });
});

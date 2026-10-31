// Utilidades SOLO para pruebas: jsdom no implementa `matchMedia` ni cambia `innerWidth` solo.
import { vi } from "vitest";

export const REDUCED_MOTION_QUERY = "(prefers-reduced-motion: reduce)";

export function mediaQueryList(media: string, matches: boolean): MediaQueryList {
  return {
    media,
    matches,
    onchange: null,
    addEventListener: () => undefined,
    removeEventListener: () => undefined,
    addListener: () => undefined,
    removeListener: () => undefined,
    dispatchEvent: () => false,
  };
}

/** Instala `window.matchMedia`; solo la consulta de movimiento reducido responde `reduced`. */
export function stubMatchMedia(reduced: boolean) {
  const fn = vi.fn((query: string) =>
    mediaQueryList(query, query === REDUCED_MOTION_QUERY ? reduced : false),
  );
  vi.stubGlobal("matchMedia", fn);
  return fn;
}

/** Cambia el ancho de la ventana (opcionalmente avisando con `resize`). */
export function setViewportWidth(width: number, notify = false) {
  Object.defineProperty(window, "innerWidth", { configurable: true, writable: true, value: width });
  if (notify) {
    window.dispatchEvent(new Event("resize"));
  }
}

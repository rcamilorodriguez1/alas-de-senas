import "@testing-library/jest-dom/vitest";
import { cleanup } from "@testing-library/react";
import { afterEach } from "vitest";
import { mediaQueryList, setViewportWidth } from "./media";

// jsdom no trae `matchMedia`: por defecto, ninguna consulta coincide (sin movimiento reducido).
// Se define con `defineProperty` para que `vi.unstubAllGlobals()` lo deje en su sitio.
if (typeof window !== "undefined" && typeof window.matchMedia !== "function") {
  Object.defineProperty(window, "matchMedia", {
    configurable: true,
    writable: true,
    value: (query: string) => mediaQueryList(query, false),
  });
}

// Sin `globals: true`, Testing Library no limpia el DOM sola entre pruebas.
afterEach(() => {
  cleanup();
  // Escritorio por defecto (§9.7): 1366 px de ancho.
  if (typeof window !== "undefined") {
    setViewportWidth(1366);
  }
});

// El ancho inicial también es de escritorio, para que `SmallScreenGate` no oculte las páginas.
if (typeof window !== "undefined") {
  setViewportWidth(1366);
}

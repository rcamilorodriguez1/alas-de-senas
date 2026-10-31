/** Barra invertida o caracteres de control: el navegador los convierte en «//». */
function hasUnsafeChars(value: string): boolean {
  return [...value].some((char) => char === "\\" || (char.codePointAt(0) ?? 0) < 0x20);
}

const AUTH_PAGES = ["/ingresar", "/registro"];

/**
 * Destino seguro tras ingresar: solo rutas del mismo origen. Rechaza «//x», «/\x» y
 * caracteres de control (el navegador los interpreta como otro dominio: redirección abierta).
 */
export function safeReturnPath(volver: string | null): string {
  const fallback = "/aprender";
  if (!volver || !volver.startsWith("/") || hasUnsafeChars(volver)) return fallback;
  const base = "https://alas.local";
  let url: URL;
  try {
    url = new URL(volver, base);
  } catch {
    return fallback;
  }
  if (url.origin !== base || AUTH_PAGES.includes(url.pathname)) return fallback;
  return url.pathname + url.search + url.hash;
}

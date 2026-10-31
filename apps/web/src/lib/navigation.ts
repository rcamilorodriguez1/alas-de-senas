/** Destino seguro tras ingresar: solo rutas internas (evita redirecciones abiertas). */
export function safeReturnPath(volver: string | null): string {
  if (volver && volver.startsWith("/") && !volver.startsWith("//")) return volver;
  return "/aprender";
}

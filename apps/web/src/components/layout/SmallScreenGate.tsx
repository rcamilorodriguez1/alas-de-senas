import { useEffect, useState, type ReactNode } from "react";
import { Mascot } from "../mascot/Mascot";

export const MIN_WIDTH = 1024;
/** §9.7: el aviso no bloquea el diccionario, aunque no esté optimizado para celular. */
const ALLOWED_PREFIXES = ["/diccionario"];

function isBlocked(): boolean {
  const allowed = ALLOWED_PREFIXES.some((prefix) => window.location.pathname.startsWith(prefix));
  return window.innerWidth < MIN_WIDTH && !allowed;
}

/**
 * Esta entrega es solo para portátil y PC (§9.7, R10.1): bajo 1024 px se muestra un aviso
 * amable encima de la app. La app queda montada y oculta (`hidden` + `inert`): al volver a
 * ensanchar la ventana no se pierde el estado ni se repite el arranque de la sesión.
 */
export function SmallScreenGate({ children }: { children: ReactNode }) {
  const [blocked, setBlocked] = useState(isBlocked);
  useEffect(() => {
    const update = () => setBlocked(isBlocked());
    window.addEventListener("resize", update);
    window.addEventListener("popstate", update);
    return () => {
      window.removeEventListener("resize", update);
      window.removeEventListener("popstate", update);
    };
  }, []);
  return (
    <>
      <div hidden={blocked} inert={blocked}>
        {children}
      </div>
      {blocked && (
        <main className="flex min-h-screen flex-col items-center justify-center gap-6 bg-emerald-50 p-8 text-center font-sans text-slate-800">
          <Mascot mood="happy" size={120} />
          <h1 className="font-display text-2xl font-extrabold">
            Alas de Señas está pensada por ahora para portátil o computador
          </h1>
          <p className="text-lg">¡Pronto llegará la versión para celular!</p>
        </main>
      )}
    </>
  );
}

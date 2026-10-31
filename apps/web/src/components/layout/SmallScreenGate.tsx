import { useEffect, useState, type ReactNode } from "react";
import { Mascot } from "../mascot/Mascot";

export const MIN_WIDTH = 1024;

function isSmall(): boolean {
  return window.innerWidth < MIN_WIDTH;
}

/** Esta entrega es solo para portátil y PC (§9.7, R10.1): aviso amable bajo 1024 px. */
export function SmallScreenGate({ children }: { children: ReactNode }) {
  const [small, setSmall] = useState(isSmall);
  useEffect(() => {
    const onResize = () => setSmall(isSmall());
    window.addEventListener("resize", onResize);
    return () => window.removeEventListener("resize", onResize);
  }, []);
  if (!small) return <>{children}</>;
  return (
    <main className="flex min-h-screen flex-col items-center justify-center gap-6 bg-emerald-50 p-8 text-center font-sans text-slate-800">
      <Mascot mood="happy" size={120} />
      <h1 className="font-display text-2xl font-extrabold">
        Alas de Señas está pensada por ahora para portátil o computador
      </h1>
      <p className="text-lg">¡Pronto llegará la versión para celular!</p>
    </main>
  );
}

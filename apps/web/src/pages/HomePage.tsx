import { useQuery } from "@tanstack/react-query";
import { fetchHealth } from "../lib/api";

function HealthStatus() {
  const { data, isPending, isError } = useQuery({ queryKey: ["health"], queryFn: fetchHealth });
  if (isPending) {
    return <p className="text-slate-500">Comprobando el servidor…</p>;
  }
  if (isError || !data.db) {
    return <p className="text-red-700">El servidor o la base de datos no responden.</p>;
  }
  return <p className="text-tomi-600">Servidor y base de datos funcionando.</p>;
}

export function HomePage() {
  return (
    <main className="flex min-h-screen flex-col items-center justify-center gap-4 bg-white p-8 font-sans text-slate-800">
      <h1 className="font-display text-5xl font-extrabold text-tomi-600">Alas de Señas</h1>
      <p className="text-lg">Aprende Lengua de Señas Colombiana con Tomi.</p>
      <HealthStatus />
    </main>
  );
}

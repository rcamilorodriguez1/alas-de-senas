import { useState } from "react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { AppLayout } from "../../components/layout/AppLayout";
import { StatsPanel } from "../gamification/StatsPanel";
import { streakLabel } from "../gamification/gamification-api";
import { useHistory, useProgressSummary, useUnits } from "./progress-api";

function percentText(value: number | null): string {
  return value === null ? "—" : `${value} %`;
}

function formatDate(iso: string): string {
  return new Date(iso).toLocaleDateString("es-CO", {
    day: "numeric",
    month: "short",
    hour: "2-digit",
    minute: "2-digit",
    timeZone: "America/Bogota",
  });
}

function StatCard({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-2xl bg-white p-4 shadow">
      <p className="text-sm font-semibold text-[#45606A]">{label}</p>
      <p className="font-display text-2xl font-extrabold">{value}</p>
    </div>
  );
}

function History() {
  const [page, setPage] = useState(1);
  const { data, isPending, isError } = useHistory(page);
  const pages = data ? Math.max(1, Math.ceil(data.total / data.pageSize)) : 1;
  return (
    <section
      aria-labelledby="historial"
      className="rounded-2xl bg-white p-4 shadow"
    >
      <h2 id="historial" className="font-display text-xl font-extrabold">
        Historial
      </h2>
      {isPending && <p role="status">Cargando historial…</p>}
      {isError && <p role="alert">No pudimos cargar tu historial.</p>}
      {data && data.items.length === 0 && (
        <p className="mt-2 text-[#45606A]">Aún no has terminado lecciones.</p>
      )}
      {data && data.items.length > 0 && (
        <>
          <table className="mt-3 w-full text-left text-sm">
            <thead>
              <tr className="text-[#45606A]">
                <th className="py-1">Fecha</th>
                <th>Lección</th>
                <th>Puntaje</th>
                <th>XP</th>
              </tr>
            </thead>
            <tbody>
              {data.items.map((item) => (
                <tr key={item.sessionId} className="border-t border-slate-100">
                  <td className="py-1.5">{formatDate(item.completedAt)}</td>
                  <td>
                    {item.nodeTitle} · {item.lessonTitle}
                  </td>
                  <td>
                    {item.score} %{" "}
                    {item.passed && (
                      <>
                        <span aria-hidden="true">✔</span>
                        <span className="sr-only">aprobada</span>
                      </>
                    )}
                  </td>
                  <td>+{item.xpEarned}</td>
                </tr>
              ))}
            </tbody>
          </table>
          <div className="mt-3 flex items-center justify-between text-sm font-semibold">
            <button
              type="button"
              onClick={() => setPage(page - 1)}
              disabled={page <= 1}
              className="rounded-xl border border-slate-300 px-3 py-1 disabled:opacity-40"
            >
              Anterior
            </button>
            <span>
              Página {page} de {pages}
            </span>
            <button
              type="button"
              onClick={() => setPage(page + 1)}
              disabled={page >= pages}
              className="rounded-xl border border-slate-300 px-3 py-1 disabled:opacity-40"
            >
              Siguiente
            </button>
          </div>
        </>
      )}
    </section>
  );
}

export function ProgressPage() {
  const summary = useProgressSummary();
  const units = useUnits();
  const chart =
    summary.data?.modules.map((module) => ({
      name: `Módulo ${module.order}`,
      avance: module.percent,
    })) ?? [];
  return (
    <AppLayout aside={<StatsPanel />}>
      <h1 className="mb-4 font-display text-3xl font-extrabold">Progreso</h1>
      {summary.isPending && <p role="status">Cargando tu progreso…</p>}
      {summary.isError && <p role="alert">No pudimos cargar tu progreso.</p>}
      {summary.data && (
        <div className="flex flex-col gap-6">
          <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
            <StatCard
              label="Avance global"
              value={`${summary.data.percent} %`}
            />
            <StatCard label="XP total" value={`${summary.data.totalXp}`} />
            <StatCard label="Racha" value={streakLabel(summary.data.streak)} />
            <StatCard
              label="Señas aprendidas"
              value={`${summary.data.signsLearned}`}
            />
          </div>
          <section
            aria-labelledby="por-modulo"
            className="rounded-2xl bg-white p-4 shadow"
          >
            <h2 id="por-modulo" className="font-display text-xl font-extrabold">
              Avance por módulo
            </h2>
            {/* La gráfica es decorativa: la lista oculta da los mismos datos al lector de pantalla. */}
            <div aria-hidden="true" className="mt-2 h-[200px] w-full">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={chart} accessibilityLayer={false}>
                  <CartesianGrid strokeDasharray="3 3" vertical={false} />
                  <XAxis dataKey="name" />
                  <YAxis domain={[0, 100]} unit=" %" width={52} />
                  <Tooltip
                    formatter={(value) => [`${String(value)} %`, "Avance"]}
                  />
                  <Bar
                    dataKey="avance"
                    fill="#10B981"
                    radius={[6, 6, 0, 0]}
                    isAnimationActive={false}
                  />
                </BarChart>
              </ResponsiveContainer>
            </div>
            <ul className="sr-only">
              {summary.data.modules.map((module) => (
                <li key={module.id}>
                  {module.title}: {module.percent} %
                </li>
              ))}
            </ul>
          </section>
        </div>
      )}
      {units.data && (
        <section
          aria-labelledby="unidades"
          className="mt-6 rounded-2xl bg-white p-4 shadow"
        >
          <h2 id="unidades" className="font-display text-xl font-extrabold">
            Resultados por unidad
          </h2>
          <table className="mt-3 w-full text-left text-sm">
            <thead>
              <tr className="text-[#45606A]">
                <th className="py-1">Unidad</th>
                <th>Puntaje promedio</th>
                <th>Precisión</th>
              </tr>
            </thead>
            <tbody>
              {units.data.modules.flatMap((module) => [
                <tr
                  key={module.id}
                  className="border-t border-slate-200 font-bold"
                >
                  <td className="py-1.5">
                    Módulo {module.order} · {module.title}
                  </td>
                  <td>{percentText(module.averageScore)}</td>
                  <td>{percentText(module.accuracy)}</td>
                </tr>,
                ...module.nodes.map((node) => (
                  <tr key={node.id} className="border-t border-slate-100">
                    <td className="py-1.5 pl-4">
                      Nodo {node.order} · {node.title}
                    </td>
                    <td>{percentText(node.averageScore)}</td>
                    <td>{percentText(node.accuracy)}</td>
                  </tr>
                )),
              ])}
            </tbody>
          </table>
        </section>
      )}
      <div className="mt-6">
        <History />
      </div>
    </AppLayout>
  );
}

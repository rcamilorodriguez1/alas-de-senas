import type { ReactNode } from "react";

export function AuthLayout({ title, children }: { title: string; children: ReactNode }) {
  return (
    <main className="flex min-h-screen items-center justify-center bg-emerald-50 p-8 font-sans text-slate-800">
      <section className="w-full max-w-md rounded-3xl bg-white p-8 shadow-lg">
        <p className="font-display text-sm font-bold uppercase tracking-wide text-tomi-600">
          Alas de Señas
        </p>
        <h1 className="mb-6 font-display text-3xl font-extrabold">{title}</h1>
        {children}
      </section>
    </main>
  );
}

export function FieldError({ id, message }: { id: string; message?: string }) {
  if (!message) return null;
  return (
    <p id={id} className="mt-1 text-sm text-red-700">
      {message}
    </p>
  );
}

export const inputClass =
  "mt-1 w-full rounded-xl border border-slate-300 px-4 py-2 focus:border-tomi-500 focus:outline-none focus:ring-2 focus:ring-tomi-500/40";
export const buttonClass =
  "w-full rounded-xl bg-tomi-600 px-4 py-3 font-display text-lg font-bold text-white hover:bg-tomi-500 disabled:opacity-60";

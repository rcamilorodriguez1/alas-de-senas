import { Search } from "lucide-react";
import { useEffect, useState } from "react";
import { Link, useSearchParams } from "react-router";
import { AppLayout } from "../../components/layout/AppLayout";
import { useSessionStore } from "../../lib/session-store";
import { StatsPanel } from "../gamification/StatsPanel";
import {
  useCategories,
  useFavorites,
  useSignSearch,
  type SignCard,
} from "./dictionary-api";

const DEBOUNCE_MS = 300;

function SignCardLink({ sign }: { sign: SignCard }) {
  return (
    <li>
      <Link
        to={`/diccionario/${sign.slug}`}
        className="flex h-full flex-col overflow-hidden rounded-2xl border border-slate-200 bg-white hover:border-[#047857] focus-visible:border-[#047857]"
      >
        <img
          src={sign.video.poster}
          alt=""
          className="aspect-video w-full bg-[#0E2A2F] object-cover"
        />
        <span className="px-3 pt-2 font-display font-extrabold">
          {sign.word}
        </span>
        <span className="px-3 pb-2 text-sm text-[#45606A]">
          {sign.category.name}
        </span>
      </Link>
    </li>
  );
}

function Favorites() {
  const { data } = useFavorites();
  if (!data) return null;
  return (
    <section aria-labelledby="favoritos" className="mt-8">
      <h2 id="favoritos" className="font-display text-xl font-extrabold">
        Tus favoritos
      </h2>
      {data.length === 0 ? (
        <p className="mt-2 text-[#45606A]">
          Aún no guardas señas. Usa «Guardar en favoritos» en una ficha.
        </p>
      ) : (
        <ul className="mt-3 grid grid-cols-2 gap-3 lg:grid-cols-3">
          {data.map((sign) => (
            <SignCardLink key={sign.slug} sign={sign} />
          ))}
        </ul>
      )}
    </section>
  );
}

/** Diccionario (R7): busca sin importar mayúsculas ni tildes; accesible sin iniciar sesión. */
export function DictionaryPage() {
  const [params, setParams] = useSearchParams();
  const q = params.get("q") ?? "";
  const category = params.get("categoria") ?? "";
  const page = Math.max(1, Number(params.get("pagina") ?? "1") || 1);
  const [text, setText] = useState(q);
  const authenticated = useSessionStore(
    (state) => state.status === "authenticated",
  );
  const categories = useCategories();
  const results = useSignSearch(q, category, page);

  // La búsqueda se lanza al dejar de escribir y queda en la URL (se puede compartir o volver).
  useEffect(() => {
    if (text === q) return;
    const timer = window.setTimeout(() => {
      setParams((previous) => {
        const next = new URLSearchParams(previous);
        if (text.trim()) next.set("q", text);
        else next.delete("q");
        next.delete("pagina");
        return next;
      });
    }, DEBOUNCE_MS);
    return () => window.clearTimeout(timer);
  }, [text, q, setParams]);

  const update = (key: string, value: string) =>
    setParams((previous) => {
      const next = new URLSearchParams(previous);
      if (value) next.set(key, value);
      else next.delete(key);
      if (key !== "pagina") next.delete("pagina");
      return next;
    });

  const data = results.data;
  const pages = data ? Math.max(1, Math.ceil(data.total / data.pageSize)) : 1;

  return (
    <AppLayout aside={<StatsPanel />}>
      <h1 className="font-display text-3xl font-extrabold">Diccionario</h1>
      <div className="mt-4 flex flex-wrap gap-3">
        <label className="relative min-w-60 flex-1">
          <span className="sr-only">Buscar una palabra</span>
          <Search
            aria-hidden="true"
            size={18}
            className="absolute top-3 left-3 text-[#45606A]"
          />
          <input
            type="search"
            value={text}
            onChange={(event) => setText(event.target.value)}
            placeholder="Busca una palabra, por ejemplo «gracias»"
            maxLength={80}
            className="w-full rounded-xl border border-slate-300 bg-white py-2.5 pr-3 pl-10"
          />
        </label>
        <label className="flex items-center gap-2 font-semibold">
          Categoría
          <select
            value={category}
            onChange={(event) => update("categoria", event.target.value)}
            className="rounded-xl border border-slate-300 bg-white px-3 py-2.5"
          >
            <option value="">Todas</option>
            {categories.data?.map((item) => (
              <option key={item.id} value={item.id}>
                {item.name} ({item.count})
              </option>
            ))}
          </select>
        </label>
      </div>

      {results.isError && (
        <p role="alert" className="mt-4 rounded-xl bg-red-50 p-3 text-red-800">
          No pudimos buscar en el diccionario. Intenta de nuevo.
        </p>
      )}
      {results.isPending && <p role="status">Buscando…</p>}
      {data && (
        <section aria-label="Resultados" className="mt-5">
          <p role="status" className="text-sm font-semibold text-[#45606A]">
            {data.total === 1 ? "1 seña" : `${data.total} señas`}
          </p>
          {data.total === 0 && q.trim() && (
            <div className="mt-3 rounded-2xl bg-white p-4 shadow">
              <p className="font-semibold">No encontramos «{q.trim()}».</p>
              {data.suggestions.length > 0 && (
                <p className="mt-2">
                  ¿Quisiste decir{" "}
                  {data.suggestions.map((suggestion, index) => (
                    <span key={suggestion.slug}>
                      {index > 0 && ", "}
                      <Link
                        to={`/diccionario/${suggestion.slug}`}
                        className="font-bold text-[#047857] underline"
                      >
                        {suggestion.word}
                      </Link>
                    </span>
                  ))}
                  ?
                </p>
              )}
            </div>
          )}
          <ul className="mt-3 grid grid-cols-2 gap-3 lg:grid-cols-3">
            {data.items.map((sign) => (
              <SignCardLink key={sign.slug} sign={sign} />
            ))}
          </ul>
          {pages > 1 && (
            <div className="mt-4 flex items-center justify-between text-sm font-semibold">
              <button
                type="button"
                disabled={page <= 1}
                onClick={() => update("pagina", String(page - 1))}
                className="rounded-xl border border-slate-300 px-3 py-1 disabled:opacity-40"
              >
                Anterior
              </button>
              <span>
                Página {page} de {pages}
              </span>
              <button
                type="button"
                disabled={page >= pages}
                onClick={() => update("pagina", String(page + 1))}
                className="rounded-xl border border-slate-300 px-3 py-1 disabled:opacity-40"
              >
                Siguiente
              </button>
            </div>
          )}
        </section>
      )}
      {authenticated && <Favorites />}
    </AppLayout>
  );
}

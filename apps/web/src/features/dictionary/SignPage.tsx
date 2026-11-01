import { useQueryClient } from "@tanstack/react-query";
import { ArrowLeft, Star } from "lucide-react";
import { useState } from "react";
import { Link, useParams } from "react-router";
import { AppLayout } from "../../components/layout/AppLayout";
import { SignVideoPlayer } from "../../components/video/SignVideoPlayer";
import { ApiError } from "../../lib/api";
import { useSessionStore } from "../../lib/session-store";
import { StatsPanel } from "../gamification/StatsPanel";
import {
  dictionaryKey,
  setFavorite,
  useSign,
  type SignDetail,
} from "./dictionary-api";

function RelatedLesson({
  lesson,
}: {
  lesson: NonNullable<SignDetail["relatedLesson"]>;
}) {
  if (lesson.status === "LOCKED") {
    return (
      <p>
        Se enseña en la lección «{lesson.title}»{" "}
        <span className="font-semibold">(bloqueada por ahora)</span>.
      </p>
    );
  }
  return (
    <p>
      Se enseña en la lección{" "}
      <Link
        to={`/leccion/${lesson.id}`}
        className="font-bold text-[#047857] underline"
      >
        «{lesson.title}»
      </Link>
      .
    </p>
  );
}

/** Práctica rápida sin puntaje: mirar, hacer la seña y autoevaluarse (R7.4). */
function QuickPractice({ slowMotion }: { slowMotion: boolean }) {
  const [answer, setAnswer] = useState<"ok" | "again" | null>(null);
  return (
    <section
      aria-labelledby="practica"
      className="rounded-2xl bg-emerald-50 p-4"
    >
      <h2 id="practica" className="font-display text-lg font-extrabold">
        Práctica rápida
      </h2>
      <p className="mt-1">
        Mira la seña{slowMotion ? " (puedes usar 0,5x)" : ""}, hazla frente a un espejo y dinos
        cómo te fue.
      </p>
      <div className="mt-3 flex gap-2">
        <button
          type="button"
          onClick={() => setAnswer("ok")}
          className="rounded-xl bg-[#047857] px-4 py-2 font-bold text-white"
        >
          Sí, me salió
        </button>
        <button
          type="button"
          onClick={() => setAnswer("again")}
          className="rounded-xl border border-[#047857] px-4 py-2 font-bold text-[#047857]"
        >
          Necesito repasar
        </button>
      </div>
      <p role="status" className="mt-2 font-semibold">
        {answer === "ok" && "¡Muy bien! Sigue así."}
        {answer === "again" &&
          (slowMotion
            ? "Mírala otra vez a 0,5x y fíjate en la forma de la mano."
            : "Mírala otra vez y fíjate en la forma de la mano.")}
      </p>
    </section>
  );
}

export function SignPage() {
  const { slug = "" } = useParams();
  const queryClient = useQueryClient();
  const authenticated = useSessionStore(
    (state) => state.status === "authenticated",
  );
  const { data: sign, isPending, error } = useSign(slug);
  const [saving, setSaving] = useState(false);
  const [notice, setNotice] = useState<string | null>(null);

  const toggleFavorite = async () => {
    if (!sign || saving) return; // aria-disabled: el foco no salta al guardar
    setSaving(true);
    setNotice(null);
    try {
      await setFavorite(sign.slug, !sign.isFavorite);
      await queryClient.invalidateQueries({ queryKey: dictionaryKey });
    } catch {
      setNotice("No pudimos guardar el cambio. Intenta de nuevo.");
    } finally {
      setSaving(false);
    }
  };

  return (
    <AppLayout aside={<StatsPanel />}>
      <Link
        to="/diccionario"
        className="inline-flex items-center gap-1 font-semibold text-[#047857]"
      >
        <ArrowLeft aria-hidden="true" size={18} />
        Volver al diccionario
      </Link>
      {isPending && <p role="status">Cargando la seña…</p>}
      {error && (
        <p role="alert" className="mt-4 rounded-xl bg-red-50 p-3 text-red-800">
          {error instanceof ApiError && error.code === "SIGN_NOT_FOUND"
            ? "No encontramos esta seña."
            : "No pudimos cargar la seña. Intenta de nuevo."}
        </p>
      )}
      {sign && (
        <article className="mt-4 flex flex-col gap-4">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div>
              <h1 className="font-display text-3xl font-extrabold">
                {sign.word}
              </h1>
              <p className="font-semibold text-[#45606A]">
                {sign.category.name}
              </p>
            </div>
            {authenticated && (
              <button
                type="button"
                aria-disabled={saving}
                onClick={() => void toggleFavorite()}
                className="inline-flex items-center gap-2 rounded-xl border border-slate-300 bg-white px-3 py-2 font-semibold aria-disabled:opacity-60"
              >
                <Star
                  aria-hidden="true"
                  size={18}
                  className={
                    sign.isFavorite
                      ? "fill-amber-400 text-amber-500"
                      : "text-[#45606A]"
                  }
                />
                {sign.isFavorite
                  ? "Quitar de favoritos"
                  : "Guardar en favoritos"}
              </button>
            )}
          </div>
          {notice && (
            <p
              role="alert"
              className="rounded-xl bg-amber-50 p-3 text-amber-900"
            >
              {notice}
            </p>
          )}
          <SignVideoPlayer
            src={sign.video.src}
            poster={sign.video.poster}
            word={sign.word}
            isPlaceholder={sign.video.placeholder}
            mediaSource={sign.video.source}
            loop
          />
          <dl className="grid gap-3 rounded-2xl bg-white p-4 shadow">
            <div>
              <dt className="font-bold">Significado</dt>
              <dd>{sign.meaning}</dd>
            </div>
            <div>
              <dt className="font-bold">Cómo se hace</dt>
              <dd>{sign.howTo ?? "Descripción en revisión"}</dd>
            </div>
            <div>
              <dt className="font-bold">Ejemplo de uso</dt>
              <dd>{sign.usageExample}</dd>
            </div>
            {sign.relatedLesson && (
              <div>
                <dt className="font-bold">En tu ruta</dt>
                <dd>
                  <RelatedLesson lesson={sign.relatedLesson} />
                </dd>
              </div>
            )}
          </dl>
          <QuickPractice slowMotion={sign.video.source !== "images"} />
        </article>
      )}
    </AppLayout>
  );
}

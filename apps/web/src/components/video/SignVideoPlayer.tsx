import { Pause, Play, RotateCcw } from "lucide-react";
import { useEffect, useRef, useState } from "react";

export interface SignVideoPlayerProps {
  src: string;
  poster: string;
  word: string;
  isPlaceholder?: boolean;
  mediaSource?: "video" | "images" | "placeholder";
  loop?: boolean;
  autoPlay?: boolean;
  /** Videos más pequeños (opciones de MEANING_TO_VIDEO, memoria, conversación). */
  compact?: boolean;
  /** Alto máximo del video en px (por defecto 300; §9.7: nunca más de 360). */
  maxHeight?: number;
  label?: string;
}

/** Reproductor de señas (§9.4): ▶/⏸, repetir, 0,5x/1x, error con reintento y etiquetas. */
export function SignVideoPlayer({
  src,
  poster,
  word,
  isPlaceholder = false,
  mediaSource = "video",
  loop = true,
  autoPlay = false,
  compact = false,
  maxHeight = 300,
  label,
}: SignVideoPlayerProps) {
  const ref = useRef<HTMLVideoElement>(null);
  const [playing, setPlaying] = useState(false);
  const [slow, setSlow] = useState(false);
  const [failed, setFailed] = useState(false);
  const [reloads, setReloads] = useState(0);
  const images = mediaSource === "images";
  const placeholder = isPlaceholder || mediaSource === "placeholder";

  const play = () => {
    const video = ref.current;
    if (!video) return;
    // play() devuelve una promesa que el navegador puede rechazar (autoplay bloqueado, B30).
    void video
      .play()
      .then(() => setPlaying(true))
      .catch(() => setPlaying(false));
  };

  useEffect(() => {
    if (autoPlay && !failed) play();
    // Solo al cambiar de video.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [src, failed]);

  const togglePlay = () => {
    const video = ref.current;
    if (!video) return;
    if (playing) {
      video.pause();
      setPlaying(false);
    } else {
      play();
    }
  };

  const replay = () => {
    const video = ref.current;
    if (!video) return;
    video.currentTime = 0;
    play();
  };

  const toggleSpeed = () => {
    const next = !slow;
    setSlow(next);
    if (ref.current) ref.current.playbackRate = next ? 0.5 : 1;
  };

  // Tras «Reintentar» el <video> vuelve al DOM: entonces se recarga.
  useEffect(() => {
    if (reloads > 0) ref.current?.load();
  }, [reloads]);

  const retry = () => {
    setFailed(false);
    setReloads((count) => count + 1);
  };

  if (failed) {
    return (
      <div
        role="alert"
        className={`flex flex-col items-center justify-center gap-3 rounded-2xl bg-slate-100 p-6 text-center ${compact ? "h-32" : "h-60"}`}
      >
        <p className="font-semibold text-[#45606A]">No pudimos cargar este video</p>
        <button
          type="button"
          onClick={retry}
          className="rounded-xl border border-slate-300 bg-white px-4 py-1.5 font-semibold"
        >
          Reintentar
        </button>
      </div>
    );
  }

  return (
    <figure className="relative overflow-hidden rounded-2xl bg-[#0E2A2F]">
      <video
        ref={ref}
        src={src}
        poster={poster}
        muted
        playsInline
        loop={loop}
        preload="metadata"
        aria-label={label ?? `Video de la seña ${word}`}
        onError={() => setFailed(true)}
        onPlay={() => setPlaying(true)}
        onPause={() => setPlaying(false)}
        style={compact ? undefined : { maxHeight }}
        className={`mx-auto w-full object-contain ${compact ? "max-h-32" : ""}`}
      />
      {(placeholder || images) && (
        <span className="absolute top-2 left-2 rounded-full bg-white/90 px-2 py-0.5 text-xs font-semibold text-[#0E2A2F]">
          {images ? "Secuencia de imágenes" : "Video en preparación"}
        </span>
      )}
      {!compact && (
        <figcaption className="flex items-center gap-2 bg-[#0E2A2F] px-3 py-2 text-sm text-white">
          <button
            type="button"
            onClick={togglePlay}
            className="flex items-center gap-1 rounded-lg px-2 py-1 hover:bg-white/10"
          >
            {playing ? <Pause aria-hidden="true" size={16} /> : <Play aria-hidden="true" size={16} />}
            {playing ? "Pausar" : "Reproducir"}
          </button>
          <button
            type="button"
            onClick={replay}
            className="flex items-center gap-1 rounded-lg px-2 py-1 hover:bg-white/10"
          >
            <RotateCcw aria-hidden="true" size={16} />
            Repetir
          </button>
          {!images && (
            <button
              type="button"
              onClick={toggleSpeed}
              aria-pressed={slow}
              className="ml-auto rounded-lg px-2 py-1 hover:bg-white/10"
            >
              0,5x
            </button>
          )}
        </figcaption>
      )}
    </figure>
  );
}

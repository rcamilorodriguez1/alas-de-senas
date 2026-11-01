import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { mockMedia, SIGN_VIDEO, type MediaSpies } from "../../test/lesson";
import { SignVideoPlayer } from "./SignVideoPlayer";

const HOLA = SIGN_VIDEO.hola;

let media: MediaSpies;

beforeEach(() => {
  media = mockMedia();
});

afterEach(() => {
  vi.restoreAllMocks();
});

function video(word = "hola"): HTMLVideoElement {
  const el = screen.getByLabelText(`Video de la seña ${word}`);
  if (!(el instanceof HTMLVideoElement)) throw new Error("El reproductor debe usar <video>");
  return el;
}

describe("SignVideoPlayer — elemento <video> (§9.4, B29)", () => {
  it("usa src, poster, muted, playsInline, preload=metadata y aria-label con la palabra", () => {
    render(<SignVideoPlayer src={HOLA.src} poster={HOLA.poster} word="hola" />);
    const el = video();
    expect(el.getAttribute("src")).toBe(HOLA.src);
    expect(el.getAttribute("poster")).toBe(HOLA.poster);
    expect(el.muted).toBe(true);
    expect(el.hasAttribute("playsinline")).toBe(true);
    expect(el.getAttribute("preload")).toBe("metadata");
  });

  it("respeta loop", () => {
    render(<SignVideoPlayer src={HOLA.src} poster={HOLA.poster} word="hola" loop />);
    expect(video().loop).toBe(true);
  });

  it("acepta palabras con ñ y tildes en la etiqueta", () => {
    render(<SignVideoPlayer src={SIGN_VIDEO.señor.src} poster={SIGN_VIDEO.señor.poster} word="señor" />);
    expect(video("señor")).toBeInTheDocument();
  });

  it("sin isPlaceholder ni imágenes no muestra etiquetas de relleno", () => {
    render(<SignVideoPlayer src={HOLA.src} poster={HOLA.poster} word="hola" />);
    expect(screen.queryByText("Video en preparación")).not.toBeInTheDocument();
    expect(screen.queryByText("Secuencia de imágenes")).not.toBeInTheDocument();
  });
});

describe("SignVideoPlayer — controles propios (R4.3)", () => {
  it("«Reproducir» llama a play() y pasa a «Pausar»; «Pausar» llama a pause() y vuelve a «Reproducir»", async () => {
    const user = userEvent.setup();
    render(<SignVideoPlayer src={HOLA.src} poster={HOLA.poster} word="hola" />);

    await user.click(screen.getByRole("button", { name: "Reproducir" }));
    expect(media.play).toHaveBeenCalled();
    const pauseButton = await screen.findByRole("button", { name: "Pausar" });
    expect(screen.queryByRole("button", { name: "Reproducir" })).not.toBeInTheDocument();

    await user.click(pauseButton);
    expect(media.pause).toHaveBeenCalled();
    expect(await screen.findByRole("button", { name: "Reproducir" })).toBeInTheDocument();
  });

  it("«Repetir» pone currentTime en 0 y reproduce", async () => {
    const user = userEvent.setup();
    render(<SignVideoPlayer src={HOLA.src} poster={HOLA.poster} word="hola" />);
    const el = video();
    el.currentTime = 1.7;
    media.play.mockClear();

    await user.click(screen.getByRole("button", { name: "Repetir" }));

    expect(el.currentTime).toBe(0);
    expect(media.play).toHaveBeenCalledTimes(1);
  });

  it("velocidad lenta: «0,5x» pone playbackRate 0.5 con aria-pressed y se puede volver a 1x", async () => {
    const user = userEvent.setup();
    render(<SignVideoPlayer src={HOLA.src} poster={HOLA.poster} word="hola" />);
    const el = video();
    const slow = screen.getByRole("button", { name: "0,5x" });
    expect(el.playbackRate).toBe(1);
    expect(slow).toHaveAttribute("aria-pressed", "false");

    await user.click(slow);
    expect(el.playbackRate).toBe(0.5);
    expect(screen.getByRole("button", { name: "0,5x" })).toHaveAttribute("aria-pressed", "true");

    // Un solo botón que alterna o un par «0,5x» / «1x»: ambos diseños vuelven a la velocidad normal.
    const normal = screen.queryByRole("button", { name: "1x" }) ?? screen.getByRole("button", { name: "0,5x" });
    await user.click(normal);
    expect(el.playbackRate).toBe(1);
    expect(screen.getByRole("button", { name: "0,5x" })).toHaveAttribute("aria-pressed", "false");
  });
});

describe("SignVideoPlayer — reproducción bloqueada (B30)", () => {
  it("con autoPlay y play() rechazado no lanza error y deja visible «Reproducir»", async () => {
    media.blockPlayback(true);
    render(<SignVideoPlayer src={HOLA.src} poster={HOLA.poster} word="hola" autoPlay />);
    // Si la promesa rechazada no se captura, Vitest falla la prueba por rechazo no manejado.
    await waitFor(() => expect(screen.getByRole("button", { name: "Reproducir" })).toBeInTheDocument());
    expect(screen.queryByRole("button", { name: "Pausar" })).not.toBeInTheDocument();
    expect(screen.queryByText("No pudimos cargar este video")).not.toBeInTheDocument();
  });

  it("si el usuario pulsa «Reproducir» y el navegador lo bloquea, el botón sigue siendo «Reproducir»", async () => {
    const user = userEvent.setup();
    media.blockPlayback(true);
    render(<SignVideoPlayer src={HOLA.src} poster={HOLA.poster} word="hola" />);

    await user.click(screen.getByRole("button", { name: "Reproducir" }));

    expect(media.play).toHaveBeenCalled();
    await waitFor(() => expect(screen.getByRole("button", { name: "Reproducir" })).toBeInTheDocument());
  });
});

describe("SignVideoPlayer — error de carga (R4.12)", () => {
  it("muestra «No pudimos cargar este video» y «Reintentar» vuelve a cargar", async () => {
    const user = userEvent.setup();
    render(<SignVideoPlayer src={HOLA.src} poster={HOLA.poster} word="hola" />);

    fireEvent.error(video());

    expect(await screen.findByText("No pudimos cargar este video")).toBeInTheDocument();
    media.load.mockClear();
    await user.click(screen.getByRole("button", { name: "Reintentar" }));

    expect(media.load).toHaveBeenCalled();
    await waitFor(() => expect(screen.queryByText("No pudimos cargar este video")).not.toBeInTheDocument());
    expect(video()).toBeInTheDocument();
  });
});

describe("SignVideoPlayer — etiquetas de origen (§9.4, R9.13)", () => {
  it("isPlaceholder muestra «Video en preparación»", () => {
    render(<SignVideoPlayer src={HOLA.src} poster={HOLA.poster} word="hola" isPlaceholder />);
    expect(screen.getByText("Video en preparación")).toBeInTheDocument();
  });

  it("mediaSource=placeholder también muestra «Video en preparación»", () => {
    render(<SignVideoPlayer src={HOLA.src} poster={HOLA.poster} word="hola" mediaSource="placeholder" />);
    expect(screen.getByText("Video en preparación")).toBeInTheDocument();
  });

  it("mediaSource=images muestra «Secuencia de imágenes» y no ofrece la velocidad lenta", () => {
    render(<SignVideoPlayer src={HOLA.src} poster={HOLA.poster} word="hola" mediaSource="images" />);
    expect(screen.getByText("Secuencia de imágenes")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "0,5x" })).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Repetir" })).toBeInTheDocument();
  });

  it("mediaSource=video ofrece la velocidad lenta y no muestra etiquetas", () => {
    render(<SignVideoPlayer src={HOLA.src} poster={HOLA.poster} word="hola" mediaSource="video" />);
    expect(screen.getByRole("button", { name: "0,5x" })).toBeInTheDocument();
    expect(screen.queryByText("Secuencia de imágenes")).not.toBeInTheDocument();
  });
});

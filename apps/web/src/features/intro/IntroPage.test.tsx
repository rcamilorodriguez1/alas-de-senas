// Bienvenida (tarea 9.1; R1.1–R1.6).
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { createMemoryRouter, RouterProvider } from "react-router";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { appRoutes } from "../../app/routes";
import type { components } from "../../lib/api-types";
import { useSessionStore } from "../../lib/session-store";
import { bearer, jsonResponse, mockFetch } from "../../test/http";
import { mockMedia } from "../../test/lesson";
import { isIntroCompleted } from "./intro-storage";

type Schemas = components["schemas"];

const video = (slug: string): Schemas["VideoRef"] => ({
  src: `/media/v/${slug}.mp4`,
  poster: `/media/p/${slug}.webp`,
  placeholder: true,
  source: "placeholder",
});
const WORDS: [string, string][] = [
  ["hola", "Hola"],
  ["gracias", "Gracias"],
  ["por-favor", "Por favor"],
  ["si", "Sí"],
  ["no", "No"],
  ["adios", "Adiós"],
];
const INTRO: Schemas["IntroOut"] = {
  cards: WORDS.map(([slug, word]) => ({ slug, word, video: video(slug) })),
  quiz: [
    { slug: "gracias", video: video("gracias"), options: [
      { word: "Gracias", correct: true }, { word: "Por favor", correct: false }, { word: "Sí", correct: false },
    ] },
    { slug: "hola", video: video("hola"), options: [
      { word: "Gracias", correct: false }, { word: "Hola", correct: true }, { word: "Por favor", correct: false },
    ] },
    { slug: "no", video: video("no"), options: [
      { word: "Adiós", correct: false }, { word: "Hola", correct: false }, { word: "No", correct: true },
    ] },
  ],
};

function renderIntro() {
  const router = createMemoryRouter(appRoutes, { initialEntries: ["/bienvenida"] });
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={client}>
      <RouterProvider router={router} />
    </QueryClientProvider>,
  );
  return router;
}

beforeEach(() => {
  mockMedia();
  window.localStorage.removeItem("alas.introCompleted");
  useSessionStore.setState({ accessToken: null, user: null, status: "anonymous" });
});

afterEach(() => {
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
  window.localStorage.removeItem("alas.introCompleted");
});

describe("/bienvenida", () => {
  it("6 tarjetas con video, palabra y Tomi; mini-quiz con retroalimentación; marca el intro y va al registro", async () => {
    const user = userEvent.setup();
    const api = mockFetch(() => jsonResponse(200, INTRO));
    const router = renderIntro();

    expect(await screen.findByRole("heading", { name: "Hola" })).toBeInTheDocument();
    expect(bearer(api.to("/api/intro", "GET")[0])).toBeNull();
    expect(screen.getByLabelText("Video de la seña Hola")).toBeInTheDocument();
    expect(screen.getByText("¡Hola! Soy Tomi. Mira cómo se saluda en LSC.")).toBeInTheDocument();
    for (let i = 0; i < 5; i += 1) {
      expect(screen.getByRole("link", { name: "Ya tengo cuenta" })).toHaveAttribute("href", "/ingresar");
      await user.click(screen.getByRole("button", { name: "Siguiente" }));
    }
    expect(screen.getByRole("heading", { name: "Adiós" })).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Ir al mini-quiz" }));

    expect(screen.getByText("Mini-quiz · Pregunta 1 de 3")).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "¿Qué significa esta seña?" })).toHaveFocus();
    expect(screen.getByRole("link", { name: "Ya tengo cuenta" })).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Gracias" }));
    expect(screen.getByRole("status")).toHaveTextContent("¡Correcto!");
    await user.click(screen.getByRole("button", { name: "Continuar" }));
    await user.click(screen.getByRole("button", { name: "Gracias" }));
    expect(screen.getByRole("status")).toHaveTextContent("Casi. Era «Hola».");
    await user.click(screen.getByRole("button", { name: "Continuar" }));
    expect(isIntroCompleted()).toBe(false);
    await user.click(screen.getByRole("button", { name: "No" }));
    expect(isIntroCompleted()).toBe(true); // R1.4: al terminar el quiz, antes de elegir a dónde ir
    await user.click(screen.getByRole("button", { name: "Crear mi cuenta" }));

    await waitFor(() => expect(router.state.location.pathname).toBe("/registro"));
    expect(isIntroCompleted()).toBe(true);
  });

  it("si no carga, avisa y permite reintentar", async () => {
    mockFetch(() => jsonResponse(500, { statusCode: 500, code: "INTERNAL", message: "x" }));
    renderIntro();
    expect(await screen.findByRole("alert")).toHaveTextContent("No pudimos cargar la bienvenida.");
    expect(screen.getByRole("link", { name: "Ya tengo cuenta" })).toBeInTheDocument();
  });
});

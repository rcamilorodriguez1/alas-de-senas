// Páginas /repaso y /progreso (tarea 7.4; R6.1–R6.8; §8.5, D23).
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { createMemoryRouter, RouterProvider } from "react-router";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { appRoutes } from "../../app/routes";
import type { components } from "../../lib/api-types";
import { useSessionStore } from "../../lib/session-store";
import { errorBody, jsonResponse, makeUser, mockFetch, type FetchHandler } from "../../test/http";
import { containingText, mockMedia, stubScrollIntoView, videoToMeaning } from "../../test/lesson";

type Schemas = components["schemas"];

const QUEUE = "/api/reviews/queue";
const START = "/api/reviews/sessions";
const SESSION = "4b9c2d1e-0f3a-4b5c-8d7e-6f5a4b3c2d1e";
const ANSWERS = `/api/review-sessions/${SESSION}/answers`;
const COMPLETE = `/api/review-sessions/${SESSION}/complete`;

const STATS: Schemas["StatsOut"] = {
  totalXp: 40,
  nectar: 15,
  streak: { current: 1, longest: 1, freezesAvailable: 0, atRisk: false },
  today: { seconds: 0, goalSeconds: 600, xp: 0 },
  hearts: { enabled: true, current: 3, max: 5, nextHeartAt: null },
};

const QUEUED: Schemas["ReviewQueueOut"] = { due: 2, signs: [{ word: "hola" }, { word: "gracias" }] };

const hola = videoToMeaning("R-01", 1, null, "hola", ["gracias", "buenos días"]);
const gracias = videoToMeaning("R-02", 2, null, "gracias", ["hola", "buenos días"]);
const START_BODY: Schemas["ReviewStartOut"] = {
  sessionId: SESSION,
  exercises: [hola, gracias].map((built) => ({
    id: built.exercise.id,
    type: built.exercise.type,
    content: built.exercise.content,
  })),
};

const COMPLETION: Schemas["ReviewCompletionOut"] = {
  correct: 2,
  total: 2,
  score: 100,
  streak: { current: 2, extended: true },
  heartsGained: 1,
  newAchievements: [],
};

function answerBody(correct: boolean, word: string): Schemas["ReviewAnswerOut"] {
  return { correct, correctToken: null, correctTokens: [], correctWord: word, alreadyAnswered: false };
}

function server(overrides: Partial<Record<string, () => Response>> = {}): FetchHandler {
  return (r) => {
    const custom = overrides[`${r.method} ${r.path}`];
    if (custom) return custom();
    if (r.method === "GET" && r.path === "/api/gamification/stats") return jsonResponse(200, STATS);
    if (r.method === "GET" && r.path === QUEUE) return jsonResponse(200, QUEUED);
    if (r.method === "POST" && r.path === START) return jsonResponse(201, START_BODY);
    if (r.method === "POST" && r.path === ANSWERS) return jsonResponse(200, answerBody(true, "hola"));
    if (r.method === "POST" && r.path === COMPLETE) return jsonResponse(200, COMPLETION);
    return jsonResponse(404, errorBody(404, "NOT_FOUND", "No encontrado."));
  };
}

function renderAt(path: string) {
  const router = createMemoryRouter(appRoutes, { initialEntries: [path] });
  const client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
  render(
    <QueryClientProvider client={client}>
      <RouterProvider router={router} />
    </QueryClientProvider>,
  );
}

async function chooseFirstAndCheck(user: ReturnType<typeof userEvent.setup>) {
  await user.click((await screen.findAllByRole("radio"))[0]);
  await user.click(screen.getByRole("button", { name: "Comprobar respuesta" }));
  await user.click(await screen.findByRole("button", { name: "Continuar" }));
}

beforeEach(() => {
  mockMedia();
  stubScrollIntoView();
  useSessionStore.setState({ accessToken: "t", user: makeUser(), status: "authenticated" });
});

afterEach(() => {
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
});

describe("/repaso", () => {
  it("muestra cuántas señas hay por repasar y cuáles", async () => {
    mockFetch(server());
    renderAt("/repaso");
    expect(await screen.findByText(containingText("Tienes 2 señas por repasar"))).toBeInTheDocument();
    const main = within(screen.getByRole("main"));
    expect(main.getByText("hola")).toBeInTheDocument();
    expect(main.getByText("gracias")).toBeInTheDocument();
  });

  it("sin señas vencidas dice que todo está al día y no ofrece empezar", async () => {
    mockFetch(server({ [`GET ${QUEUE}`]: () => jsonResponse(200, { due: 0, signs: [] }) }));
    renderAt("/repaso");
    expect(await screen.findByText("No tienes señas por repasar hoy.")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Empezar repaso" })).not.toBeInTheDocument();
  });

  it("409 NO_REVIEWS_DUE al empezar muestra «todo al día»", async () => {
    const user = userEvent.setup();
    mockFetch(
      server({
        [`POST ${START}`]: () =>
          jsonResponse(409, errorBody(409, "NO_REVIEWS_DUE", "No tienes señas por repasar hoy.")),
      }),
    );
    renderAt("/repaso");
    await user.click(await screen.findByRole("button", { name: "Empezar repaso" }));
    expect(await screen.findByText("No tienes señas por repasar hoy.")).toBeInTheDocument();
  });

  it("responde cada seña al servidor (nunca envía aciertos) y muestra el resultado", async () => {
    const user = userEvent.setup();
    const api = mockFetch(server());
    renderAt("/repaso");
    await user.click(await screen.findByRole("button", { name: "Empezar repaso" }));

    expect(await screen.findByRole("progressbar", { name: "Avance del repaso" })).toBeInTheDocument();
    expect(screen.getByText("El repaso no quita vidas.")).toBeInTheDocument();
    await chooseFirstAndCheck(user);
    await chooseFirstAndCheck(user);

    expect(await screen.findByText("¡Repaso terminado!")).toBeInTheDocument();
    expect(screen.getByText(containingText("2 de 2 correctas"))).toBeInTheDocument();
    expect(screen.getByText(containingText("+1 vida"))).toBeInTheDocument();
    const answers = api.to(ANSWERS, "POST");
    expect(answers).toHaveLength(2);
    for (const request of answers) {
      expect(JSON.stringify(request.body)).not.toMatch(/"correct"/);
      expect(JSON.stringify(request.body)).toMatch(/optionToken/);
    }
    expect(api.to(COMPLETE, "POST")).toHaveLength(1);
  });

  it("el panel muestra las señas por repasar con un enlace a /repaso", async () => {
    mockFetch(server());
    renderAt("/aprender");
    expect(await screen.findByText(containingText("Señas por repasar: 2"))).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Repasar ahora" })).toHaveAttribute("href", "/repaso");
  });
});

describe("/progreso", () => {
  const SUMMARY: Schemas["ProgressSummaryOut"] = {
    percent: 6,
    modules: [{ id: "M1", title: "Fundamentos de la LSC", order: 1, percent: 13 }],
    totalXp: 40,
    streak: 2,
    signsLearned: 3,
  };
  const UNITS: Schemas["UnitsOut"] = {
    modules: [
      {
        id: "M1",
        title: "Fundamentos de la LSC",
        order: 1,
        averageScore: 90,
        accuracy: 85,
        nodes: [{ id: "M1-N1", title: "Saludos y cortesía", order: 1, averageScore: 90, accuracy: 85 }],
      },
    ],
  };
  const historyPage = (page: number): Schemas["HistoryPageOut"] => ({
    items: [
      {
        sessionId: `00000000-0000-4000-8000-00000000000${page}`,
        lessonId: "M1-N1-L1",
        lessonTitle: page === 1 ? "Aprende" : "Reconoce",
        nodeTitle: "Saludos y cortesía",
        completedAt: "2026-11-03T15:00:00Z",
        score: 100,
        passed: true,
        xpEarned: 20,
      },
    ],
    page,
    pageSize: 20,
    total: 21,
  });

  function progressServer(): FetchHandler {
    return (r) => {
      if (r.path === "/api/progress/summary") return jsonResponse(200, SUMMARY);
      if (r.path === "/api/progress/units") return jsonResponse(200, UNITS);
      if (r.path.startsWith("/api/progress/history")) {
        const page = new URLSearchParams(r.path.split("?")[1] ?? "").get("page") ?? "1";
        return jsonResponse(200, historyPage(Number(page)));
      }
      return server()(r);
    };
  }

  it("muestra avance, XP, racha, señas aprendidas y resultados por unidad", async () => {
    mockFetch(progressServer());
    renderAt("/progreso");
    expect(await screen.findByText("Avance global")).toBeInTheDocument();
    expect(screen.getByText("6 %")).toBeInTheDocument();
    expect(screen.getByText("2 días")).toBeInTheDocument();
    expect(screen.getByText(containingText("Fundamentos de la LSC: 13 %"))).toBeInTheDocument();
    expect(await screen.findByText(containingText("Nodo 1 · Saludos y cortesía"))).toBeInTheDocument();
    expect(screen.getAllByText("85 %").length).toBeGreaterThan(0);
  });

  it("el historial se pagina de 20 en 20", async () => {
    const user = userEvent.setup();
    mockFetch(progressServer());
    renderAt("/progreso");
    expect(await screen.findByText("Página 1 de 2")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Siguiente" }));
    await waitFor(() => expect(screen.getByText("Página 2 de 2")).toBeInTheDocument());
    expect(screen.getByText(containingText("Saludos y cortesía · Reconoce"))).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Siguiente" })).toBeDisabled();
  });
});

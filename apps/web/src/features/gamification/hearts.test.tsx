// Vidas en la interfaz (tarea 6.5; R5.13–R5.15; §7.10).
import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { components } from "../../lib/api-types";
import { useSessionStore } from "../../lib/session-store";
import { errorBody, jsonResponse, makeUser, mockFetch, type FetchHandler } from "../../test/http";
import {
  containingText,
  HEARTS_FULL,
  LESSON_INFO,
  lessonFixture,
  lessonLoaded,
  lessonServer,
  m1n1l1,
  mockMedia,
  renderLesson,
  stubScrollIntoView,
  videoToMeaning,
} from "../../test/lesson";
import { stubMatchMedia } from "../../test/media";

type StatsOut = components["schemas"]["StatsOut"];

const NOW = new Date("2026-11-03T15:00:00Z");
const NEXT_HEART = "2026-11-03T16:30:05Z"; // 1 h 30 min 5 s después de NOW
const REFILL = "/api/gamification/hearts-refill";

const STATS: StatsOut = {
  totalXp: 40,
  nectar: 10,
  streak: { current: 1, longest: 1, freezesAvailable: 0, atRisk: false },
  today: { seconds: 0, goalSeconds: 600, xp: 0 },
  hearts: { enabled: true, current: 5, max: 5, nextHeartAt: null },
};

function l2() {
  return lessonFixture(LESSON_INFO.L2, [
    videoToMeaning("M1-N1-L2-E01", 1, 0, "hola", ["gracias", "buenos días", "hasta luego"]),
    videoToMeaning("M1-N1-L2-E02", 2, 0, "gracias", ["hola", "buenos días", "hasta luego"]),
  ]);
}

function noHearts(): Response {
  return jsonResponse(403, {
    ...errorBody(403, "NO_HEARTS", "Te quedaste sin vidas por ahora."),
    nextHeartAt: NEXT_HEART,
  });
}

beforeEach(() => {
  mockMedia();
  stubScrollIntoView();
  useSessionStore.setState({ accessToken: "t", user: makeUser(), status: "authenticated" });
});

afterEach(() => {
  vi.useRealTimers();
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
});

/** Elige una opción incorrecta del primer ejercicio y comprueba. */
async function answerWrong(user: ReturnType<typeof userEvent.setup>) {
  const radios = await screen.findAllByRole("radio");
  const wrong = radios.find((radio) => !radio.textContent?.includes("hola")) ?? radios[1];
  await user.click(wrong);
  await user.click(screen.getByRole("button", { name: "Comprobar respuesta" }));
}

describe("Vidas en la lección", () => {
  it("al perder una vida el contador baja y late", async () => {
    const user = userEvent.setup();
    mockFetch(lessonServer(l2()).handler);
    renderLesson("M1-N1-L2");
    await lessonLoaded();
    expect(screen.getByLabelText("Vidas: 5")).not.toHaveAttribute("data-heartbeat");

    await answerWrong(user);

    const counter = await screen.findByLabelText("Vidas: 4");
    expect(counter).toHaveAttribute("data-heartbeat", "true");
  });

  it("con movimiento reducido el contador baja sin latido", async () => {
    stubMatchMedia(true);
    const user = userEvent.setup();
    mockFetch(lessonServer(l2()).handler);
    renderLesson("M1-N1-L2");
    await lessonLoaded();

    await answerWrong(user);

    const counter = await screen.findByLabelText("Vidas: 4");
    expect(counter).not.toHaveAttribute("data-heartbeat");
  });

  it("una lección Aprende con 0 vidas se abre y no pone vidas en juego", async () => {
    const fixture = m1n1l1();
    fixture.start.hearts = { ...HEARTS_FULL, current: 0, nextHeartAt: NEXT_HEART };
    mockFetch(lessonServer(fixture).handler);
    renderLesson("M1-N1-L1");
    await lessonLoaded();
    expect(screen.getByText("Sin vidas en juego")).toBeInTheDocument();
    expect(screen.queryByRole("dialog", { name: "Sin vidas" })).not.toBeInTheDocument();
  });
});

describe("Modal «Sin vidas» (NO_HEARTS)", () => {
  it("ofrece repasar, recargar o volver, con cuenta regresiva", async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    vi.setSystemTime(NOW);
    mockFetch(lessonServer(l2(), { starts: [noHearts()] }).handler);
    renderLesson("M1-N1-L2");

    const dialog = await screen.findByRole("dialog", { name: "Sin vidas" });
    const d = within(dialog);
    expect(d.getByText(containingText("Te quedaste sin vidas"))).toBeInTheDocument();
    expect(d.getByText(containingText("Recuperas la próxima en 1:30:05"))).toBeInTheDocument();
    expect(d.getByRole("link", { name: "Repasar señas" })).toHaveAttribute("href", "/repaso");
    expect(d.getByRole("link", { name: "Volver a la ruta" })).toHaveAttribute("href", "/aprender");
    expect(d.getByRole("button", { name: "Recargar vidas (30 de néctar)" })).toBeInTheDocument();
    expect(d.getByText("Las lecciones «Aprende» siempre están disponibles.")).toBeInTheDocument();

    await vi.advanceTimersByTimeAsync(1000);
    expect(await d.findByText(containingText("Recuperas la próxima en 1:30:04"))).toBeInTheDocument();
  });

  it("recargar con néctar vuelve a abrir la lección", async () => {
    const user = userEvent.setup();
    const server = lessonServer(l2(), { starts: [noHearts(), l2()] });
    const handler: FetchHandler = (request) => {
      if (request.path === REFILL && request.method === "POST") return jsonResponse(200, STATS);
      return server.handler(request);
    };
    const api = mockFetch(handler);
    renderLesson("M1-N1-L2");

    await user.click(await screen.findByRole("button", { name: "Recargar vidas (30 de néctar)" }));

    expect(await screen.findByRole("progressbar", { name: "Avance de la lección" })).toBeInTheDocument();
    expect(api.to(REFILL, "POST")).toHaveLength(1);
    expect(screen.queryByRole("dialog", { name: "Sin vidas" })).not.toBeInTheDocument();
  });

  it("sin néctar suficiente avisa y no abre la lección", async () => {
    const user = userEvent.setup();
    const server = lessonServer(l2(), { starts: [noHearts()] });
    const handler: FetchHandler = (request) => {
      if (request.path === REFILL && request.method === "POST") {
        return jsonResponse(409, errorBody(409, "NOT_ENOUGH_NECTAR", "No tienes suficiente néctar"));
      }
      return server.handler(request);
    };
    mockFetch(handler);
    renderLesson("M1-N1-L2");

    await user.click(await screen.findByRole("button", { name: "Recargar vidas (30 de néctar)" }));

    await waitFor(() =>
      expect(screen.getByRole("alert")).toHaveTextContent("No tienes suficiente néctar"),
    );
    expect(screen.getByRole("dialog", { name: "Sin vidas" })).toBeInTheDocument();
  });
});

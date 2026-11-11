// Celebración al terminar la lección (tarea 6.3; R4.9, R5.12; §9, mockup 4.5).
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent, { type UserEvent } from "@testing-library/user-event";
import confetti from "canvas-confetti";
import { createMemoryRouter, MemoryRouter, RouterProvider } from "react-router";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { appRoutes } from "../../app/routes";
import type { components } from "../../lib/api-types";
import { useSessionStore } from "../../lib/session-store";
import { errorBody, jsonResponse, makeUser, mockFetch, type FetchHandler } from "../../test/http";
import {
  containingText,
  LESSON_INFO,
  lessonFixture,
  lessonLoaded,
  lessonServer,
  mockMedia,
  observe,
  produce,
  renderLesson,
  stubScrollIntoView,
} from "../../test/lesson";
import { stubMatchMedia } from "../../test/media";
import { CelebrationModal } from "./CelebrationModal";
import { statsKey } from "./gamification-api";

vi.mock("canvas-confetti", () => ({ default: vi.fn() }));

type LessonCompletionOut = components["schemas"]["LessonCompletionOut"];
type StatsOut = components["schemas"]["StatsOut"];

const PASSED: LessonCompletionOut = {
  score: 83,
  correct: 5,
  total: 6,
  passed: true,
  xpEarned: 16,
  nectarEarned: 4,
  streak: { current: 3, extended: true },
  newAchievements: [
    { id: "FIRST_LESSON", title: "Primeras alas", nectar: 10 },
    { id: "STREAK_3", title: "Aleteo constante", nectar: 15 },
  ],
  unlocked: [{ type: "LESSON", id: "M1-N1-L2" }],
  mascotMood: "cheer",
  mascotMessage: "¡Volaste alto! Ya sabes saludar en LSC.",
};

const FAILED: LessonCompletionOut = {
  score: 50,
  correct: 3,
  total: 6,
  passed: false,
  xpEarned: 0,
  nectarEarned: 0,
  streak: { current: 3, extended: false },
  newAchievements: [],
  unlocked: [],
  mascotMood: "thinking",
  mascotMessage: "Vas bien. Repasa las señas y vuelve a intentarlo.",
};

const STATS: StatsOut = {
  totalXp: 120,
  nectar: 40,
  streak: { current: 2, longest: 2, freezesAvailable: 0, atRisk: true },
  today: { seconds: 60, goalSeconds: 600, xp: 0 },
  hearts: { enabled: true, current: 5, max: 5, nextHeartAt: null },
};

function renderModal(result: LessonCompletionOut) {
  const onClose = vi.fn();
  render(
    <MemoryRouter>
      <CelebrationModal result={result} onClose={onClose} />
    </MemoryRouter>,
  );
  return { onClose, dialog: screen.getByRole("dialog", { name: "Resultado de la lección" }) };
}

const confettiMock = vi.mocked(confetti);

beforeEach(() => {
  confettiMock.mockClear();
});

afterEach(() => {
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
  useSessionStore.setState(useSessionStore.getInitialState(), true);
});

describe("CelebrationModal — contenido (R4.9)", () => {
  it("es un diálogo modal con nombre «Resultado de la lección»", () => {
    const { dialog } = renderModal(PASSED);
    expect(dialog).toHaveAttribute("aria-modal", "true");
  });

  it("aprobada: «¡Lección completada!», puntaje, XP y néctar ganados", () => {
    const { dialog } = renderModal(PASSED);
    const d = within(dialog);
    expect(d.getByText(containingText("¡Lección completada!"))).toBeInTheDocument();
    expect(d.queryByText(containingText("¡Buen intento!"))).not.toBeInTheDocument();
    expect(d.getByText(/83\s%/)).toBeInTheDocument();
    expect(d.getByText(containingText("+16 XP"))).toBeInTheDocument();
    expect(d.getByText(containingText("+4 de néctar"))).toBeInTheDocument();
  });

  it("no aprobada: «¡Buen intento!» con su puntaje, sin «¡Lección completada!»", () => {
    const { dialog } = renderModal(FAILED);
    const d = within(dialog);
    expect(d.getByText(containingText("¡Buen intento!"))).toBeInTheDocument();
    expect(d.queryByText(containingText("¡Lección completada!"))).not.toBeInTheDocument();
    expect(d.getByText(/50\s%/)).toBeInTheDocument();
    expect(d.getByText(containingText("+0 XP"))).toBeInTheDocument();
  });

  it("muestra el mensaje de Tomi (R5.12)", () => {
    const { dialog } = renderModal(PASSED);
    expect(within(dialog).getByText(containingText(PASSED.mascotMessage))).toBeInTheDocument();
  });

  it("racha extendida: «Racha: 3 días» con la llama y «¡Racha extendida!»", () => {
    const { dialog } = renderModal(PASSED);
    expect(within(dialog).getByText(containingText("Racha: 3 días"))).toBeInTheDocument();
    expect(dialog.querySelector('img[data-icon="racha"]')).not.toBeNull();
    expect(within(dialog).getByText(containingText("¡Racha extendida!"))).toBeInTheDocument();
  });

  it("racha no extendida (segunda lección del día): muestra la racha sin «¡Racha extendida!»", () => {
    const { dialog } = renderModal(FAILED);
    expect(within(dialog).getByText(containingText("Racha: 3 días"))).toBeInTheDocument();
    expect(within(dialog).queryByText(containingText("¡Racha extendida!"))).not.toBeInTheDocument();
  });

  it("por cada logro nuevo: «¡Logro desbloqueado!», su título y su néctar", () => {
    const { dialog } = renderModal(PASSED);
    const d = within(dialog);
    expect(d.getAllByText(containingText("¡Logro desbloqueado!"))).toHaveLength(2);
    expect(d.getByText(containingText("Primeras alas"))).toBeInTheDocument();
    expect(d.getByText(containingText("Aleteo constante"))).toBeInTheDocument();
    expect(d.getByText(containingText("+10 de néctar"))).toBeInTheDocument();
    expect(d.getByText(containingText("+15 de néctar"))).toBeInTheDocument();
  });

  it("sin logros nuevos no muestra «¡Logro desbloqueado!»", () => {
    const { dialog } = renderModal(FAILED);
    expect(within(dialog).queryByText(containingText("¡Logro desbloqueado!"))).not.toBeInTheDocument();
  });
});

describe("CelebrationModal — interacción y accesibilidad", () => {
  it("al abrir, el foco está en «Volver a la ruta»", async () => {
    const { dialog } = renderModal(PASSED);
    const back = within(dialog).getByRole("button", { name: "Volver a la ruta" });
    await waitFor(() => expect(back).toHaveFocus());
  });

  it("«Volver a la ruta» llama a onClose una vez", async () => {
    const user = userEvent.setup();
    const { dialog, onClose } = renderModal(PASSED);
    await user.click(within(dialog).getByRole("button", { name: "Volver a la ruta" }));
    expect(onClose).toHaveBeenCalledTimes(1);
  });

  it("Escape llama a onClose", async () => {
    const user = userEvent.setup();
    const { onClose } = renderModal(PASSED);
    await user.keyboard("{Escape}");
    expect(onClose).toHaveBeenCalledTimes(1);
  });
});

describe("CelebrationModal — confeti (canvas-confetti)", () => {
  it("aprobada y sin movimiento reducido: lanza el confeti una sola vez", async () => {
    stubMatchMedia(false);
    renderModal(PASSED);
    await waitFor(() => expect(confettiMock).toHaveBeenCalledTimes(1));
    await new Promise((resolve) => setTimeout(resolve, 30));
    expect(confettiMock).toHaveBeenCalledTimes(1);
  });

  it("no aprobada: no hay confeti", async () => {
    stubMatchMedia(false);
    renderModal(FAILED);
    await new Promise((resolve) => setTimeout(resolve, 30));
    expect(confettiMock).not.toHaveBeenCalled();
  });

  it("con prefers-reduced-motion: no hay confeti aunque haya aprobado", async () => {
    stubMatchMedia(true);
    renderModal(PASSED);
    expect(screen.getByText(containingText("¡Lección completada!"))).toBeInTheDocument();
    await new Promise((resolve) => setTimeout(resolve, 30));
    expect(confettiMock).not.toHaveBeenCalled();
  });
});

// ---------- Integración con LessonPage (§9: complete → CelebrationModal → /aprender) ----------

const SHORT = () =>
  lessonFixture(LESSON_INFO.L1, [observe("M1-N1-L1-E01", 1, 0, "hola"), produce("M1-N1-L1-E02", 2, 0, "hola")]);

function withStats(handler: FetchHandler): FetchHandler {
  return (request) =>
    request.method === "GET" && request.path === "/api/gamification/stats"
      ? jsonResponse(200, STATS)
      : handler(request);
}

async function finishShortLesson(user: UserEvent) {
  await lessonLoaded();
  await user.click(await screen.findByRole("button", { name: "Continuar" }));
  await user.click(await screen.findByRole("button", { name: "Sí, me salió" }));
}

describe("LessonPage — celebración al completar (R4.9)", () => {
  beforeEach(() => {
    mockMedia();
    stubScrollIntoView();
    useSessionStore.setState({ accessToken: "t", user: makeUser(), status: "authenticated" });
  });

  it("al terminar abre el diálogo «Resultado de la lección» con los datos del servidor", async () => {
    const user = userEvent.setup();
    mockFetch(withStats(lessonServer(SHORT(), { completion: PASSED }).handler));
    renderLesson();
    await finishShortLesson(user);

    const dialog = await screen.findByRole("dialog", { name: "Resultado de la lección" });
    const d = within(dialog);
    expect(d.getByText(containingText("¡Lección completada!"))).toBeInTheDocument();
    expect(d.getByText(containingText("+16 XP"))).toBeInTheDocument();
    expect(d.getAllByText(containingText("¡Logro desbloqueado!"))).toHaveLength(2);
    expect(d.getByText(containingText("Aleteo constante"))).toBeInTheDocument();
  });

  it("«Volver a la ruta» del diálogo lleva a /aprender", async () => {
    const user = userEvent.setup();
    mockFetch(withStats(lessonServer(SHORT(), { completion: PASSED }).handler));
    const router = renderLesson();
    await finishShortLesson(user);

    const dialog = await screen.findByRole("dialog", { name: "Resultado de la lección" });
    await user.click(within(dialog).getByRole("button", { name: "Volver a la ruta" }));
    await waitFor(() => expect(router.state.location.pathname).toBe("/aprender"));
  });

  it("al completar invalida la consulta de estadísticas (statsKey)", async () => {
    const user = userEvent.setup();
    mockFetch(withStats(lessonServer(SHORT(), { completion: PASSED }).handler));
    const client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
    client.setQueryData(statsKey, STATS);
    expect(client.getQueryState(statsKey)?.isInvalidated).toBe(false);
    const router = createMemoryRouter(appRoutes, { initialEntries: ["/leccion/M1-N1-L1"] });
    render(
      <QueryClientProvider client={client}>
        <RouterProvider router={router} />
      </QueryClientProvider>,
    );
    await finishShortLesson(user);
    await screen.findByRole("dialog", { name: "Resultado de la lección" });

    await waitFor(() => expect(client.getQueryState(statsKey)?.isInvalidated).toBe(true));
  });

  it("si falla al completar no abre el diálogo de resultado", async () => {
    const user = userEvent.setup();
    const broken = jsonResponse(500, errorBody(500, "INTERNAL_ERROR", "Algo salió mal."));
    mockFetch(withStats(lessonServer(SHORT(), { completion: broken }).handler));
    renderLesson();
    await finishShortLesson(user);
    await new Promise((resolve) => setTimeout(resolve, 50));
    expect(screen.queryByRole("dialog", { name: "Resultado de la lección" })).not.toBeInTheDocument();
  });
});

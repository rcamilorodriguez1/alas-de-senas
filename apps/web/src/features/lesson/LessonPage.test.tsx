import { screen, waitFor, within } from "@testing-library/react";
import userEvent, { type UserEvent } from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { appRoutes } from "../../app/routes";
import { useSessionStore } from "../../lib/session-store";
import { bearer, errorBody, jsonResponse, makeUser, mockFetch } from "../../test/http";
import {
  activityCard,
  COMPLETION_FAILED,
  COMPLETION_PASSED,
  containingText,
  LESSON_INFO,
  lessonFixture,
  lessonLoaded,
  lessonServer,
  m1n1l1,
  meaningToVideo,
  mockMedia,
  NEW_SESSION_ID,
  observe,
  produce,
  renderLesson,
  SESSION_ID,
  sessionExpired,
  SIGN_VIDEO,
  stubScrollIntoView,
  videoToMeaning,
} from "../../test/lesson";

const ANSWERS = `/api/lesson-sessions/${SESSION_ID}/answers`;
const COMPLETE = `/api/lesson-sessions/${SESSION_ID}/complete`;
const START = "/api/lessons/M1-N1-L1/sessions";

beforeEach(() => {
  mockMedia();
  stubScrollIntoView();
  useSessionStore.setState({ accessToken: "t", user: makeUser({ name: "Camilo" }), status: "authenticated" });
});

afterEach(() => {
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
  useSessionStore.setState(useSessionStore.getInitialState(), true);
});

/** Responde el ejercicio actual de M1-N1-L1 (OBSERVE → VIDEO_TO_MEANING → PRODUCE) como lo haría el usuario. */
async function answerObserve(user: UserEvent) {
  await user.click(await screen.findByRole("button", { name: "Continuar" }));
}

async function answerSelect(user: UserEvent, index = 0) {
  const radios = await screen.findAllByRole("radio");
  await user.click(radios[index]);
  await user.click(screen.getByRole("button", { name: "Comprobar respuesta" }));
  await user.click(await screen.findByRole("button", { name: "Continuar" }));
}

async function answerProduce(user: UserEvent) {
  await user.click(await screen.findByRole("button", { name: "Sí, me salió" }));
}

function progressValue(): number {
  return Number(screen.getByRole("progressbar").getAttribute("aria-valuenow"));
}

describe("ruta /leccion/:lessonId", () => {
  it("está protegida: sin sesión lleva a /ingresar con la ruta para volver", async () => {
    useSessionStore.setState({ accessToken: null, user: null, status: "anonymous" });
    const api = mockFetch(lessonServer(m1n1l1()).handler);
    const router = renderLesson();
    await waitFor(() => expect(router.state.location.pathname).toBe("/ingresar"));
    expect(router.state.location.search).toBe(`?volver=${encodeURIComponent("/leccion/M1-N1-L1")}`);
    expect(api.to(START, "POST")).toHaveLength(0);
  });

  it("existe en appRoutes", () => {
    expect(appRoutes.some((r) => r.path === "/leccion/:lessonId")).toBe(true);
  });
});

describe("LessonPage — inicio de sesión (§8.3, B34)", () => {
  it("hace UN solo POST …/sessions aunque StrictMode monte dos veces", async () => {
    const api = mockFetch(lessonServer(m1n1l1()).handler);
    renderLesson("M1-N1-L1", { strict: true });
    await lessonLoaded();
    // Un tic extra para que un segundo efecto, si lo hubiera, alcance a disparar.
    await new Promise((resolve) => setTimeout(resolve, 20));
    const starts = api.to(START, "POST");
    expect(starts).toHaveLength(1);
    expect(bearer(starts[0])).toBe("Bearer t");
  });

  it("usa el lessonId de la URL", async () => {
    const fixture = lessonFixture(LESSON_INFO.L2, [observe("M1-N1-L2-E01", 1, 0, "hola")]);
    const api = mockFetch(lessonServer(fixture).handler);
    renderLesson("M1-N1-L2");
    await lessonLoaded();
    expect(api.to("/api/lessons/M1-N1-L2/sessions", "POST")).toHaveLength(1);
  });
});

describe("LessonPage — encabezado (R4.1, §9.3)", () => {
  it("muestra módulo, nodo, lección y tipo en mayúsculas, XP estimado, progreso 0 y «Seña 1 de 3»", async () => {
    mockFetch(lessonServer(m1n1l1()).handler);
    renderLesson();
    await lessonLoaded();

    expect(screen.getByText(containingText("MÓDULO 1 · NODO 1 — LECCIÓN 1 · APRENDE"))).toBeInTheDocument();
    expect(screen.getByText(containingText("+20 XP"))).toBeInTheDocument();
    const bar = screen.getByRole("progressbar");
    expect(bar).toHaveAttribute("aria-valuenow", "0");
    expect(screen.getByText(containingText("Seña 1 de 3"))).toBeInTheDocument();
  });

  it("en Aprende muestra «Sin vidas en juego» y no el contador de vidas", async () => {
    mockFetch(lessonServer(m1n1l1()).handler);
    renderLesson();
    await lessonLoaded();
    expect(screen.getByText(containingText("Sin vidas en juego"))).toBeInTheDocument();
    expect(screen.queryByLabelText(/^Vidas:/)).not.toBeInTheDocument();
  });

  it("en Reconoce muestra «❤️ 5» con aria-label «Vidas: 5»", async () => {
    const fixture = lessonFixture(LESSON_INFO.L2, [
      observe("M1-N1-L2-E01", 1, 0, "hola"),
      videoToMeaning("M1-N1-L2-E02", 2, 0, "hola", ["gracias", "buenos días", "hasta luego"]),
    ]);
    mockFetch(lessonServer(fixture).handler);
    renderLesson("M1-N1-L2");
    await lessonLoaded();

    expect(screen.getByText(containingText("MÓDULO 1 · NODO 1 — LECCIÓN 2 · RECONOCE"))).toBeInTheDocument();
    const hearts = screen.getByLabelText("Vidas: 5");
    expect(hearts).toHaveTextContent(/❤️\s*5/);
    expect(screen.queryByText(containingText("Sin vidas en juego"))).not.toBeInTheDocument();
    expect(screen.getByText(containingText("Seña 1 de 1"))).toBeInTheDocument();
  });

  it("el reto final (sin agrupación por seña) no muestra «Seña n de m»", async () => {
    const fixture = lessonFixture(LESSON_INFO.L4, [
      videoToMeaning("M1-N1-L4-E01", 1, null, "gracias", ["hola", "buenos días", "hasta luego"]),
      meaningToVideo("M1-N1-L4-E02", 2, null, "hola", ["gracias", "buenos días", "por favor"]),
    ]);
    mockFetch(lessonServer(fixture).handler);
    renderLesson("M1-N1-L4");
    await lessonLoaded();
    expect(screen.getByText(containingText("LECCIÓN 4 · RETO FINAL"))).toBeInTheDocument();
    expect(screen.getByText(containingText("+30 XP"))).toBeInTheDocument();
    expect(screen.queryByText(/Seña \d+ de \d+/)).not.toBeInTheDocument();
  });

  it("tras responder la primera seña (3 de 12) la barra marca 25 y pasa a «Seña 2 de 3»", async () => {
    const user = userEvent.setup();
    mockFetch(lessonServer(m1n1l1()).handler);
    renderLesson();
    await lessonLoaded();

    await answerObserve(user);
    await answerSelect(user);
    await answerProduce(user);

    await waitFor(() => expect(progressValue()).toBe(25));
    expect(screen.getByText(containingText("Seña 2 de 3"))).toBeInTheDocument();
    expect(await screen.findByLabelText("Video de la seña buenos días")).toBeInTheDocument();
  });
});

describe("LessonPage — actividades en secuencia (R4.1, R4.2)", () => {
  it("muestra las cuatro actividades en orden", async () => {
    mockFetch(lessonServer(m1n1l1()).handler);
    renderLesson();
    await lessonLoaded();
    const cards = [activityCard(1), activityCard(2), activityCard(3), activityCard(4)];
    for (let i = 1; i < cards.length; i += 1) {
      expect(cards[i - 1].compareDocumentPosition(cards[i]) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
    }
  });

  it("al empezar, la 1 está activa y la 2, 3 y 4 pendientes con 🔒 y «Pendiente»", async () => {
    mockFetch(lessonServer(m1n1l1()).handler);
    renderLesson();
    await lessonLoaded();

    const first = activityCard(1);
    expect(first).not.toHaveTextContent("Pendiente");
    expect(first).not.toHaveTextContent("Completada");
    for (const n of [2, 3, 4] as const) {
      const card = activityCard(n);
      expect(card).toHaveTextContent("Pendiente");
      expect(card).toHaveTextContent("🔒");
      expect(within(card).queryByRole("radio")).not.toBeInTheDocument();
    }
  });

  it("al observar, la 1 queda «Completada» con ✔ y se activa la 2", async () => {
    const user = userEvent.setup();
    mockFetch(lessonServer(m1n1l1()).handler);
    renderLesson();
    await lessonLoaded();

    await answerObserve(user);

    await waitFor(() => expect(activityCard(1)).toHaveTextContent("Completada"));
    expect(activityCard(1)).toHaveTextContent("✔");
    const second = activityCard(2);
    expect(second).not.toHaveTextContent("Pendiente");
    expect(second).not.toHaveTextContent("🔒");
    expect(await within(second).findAllByRole("radio")).toHaveLength(4);
    expect(activityCard(3)).toHaveTextContent("Pendiente");
    expect(activityCard(4)).toHaveTextContent("Pendiente");
  });

  it("la actividad activa contiene el ejercicio actual (Selecciona) y la 3 se activa con PRODUCE", async () => {
    const user = userEvent.setup();
    mockFetch(lessonServer(m1n1l1()).handler);
    renderLesson();
    await lessonLoaded();

    await answerObserve(user);
    await answerSelect(user);

    const third = activityCard(3);
    expect(await within(third).findByRole("button", { name: "Sí, me salió" })).toBeInTheDocument();
    expect(activityCard(2)).toHaveTextContent("Completada");
    expect(activityCard(4)).toHaveTextContent("Pendiente");
  });
});

describe("LessonPage — precarga del siguiente video (§9.4, B31)", () => {
  it("crea un <video preload=auto> oculto con el video del siguiente ejercicio", async () => {
    const fixture = lessonFixture(LESSON_INFO.L1, [
      observe("M1-N1-L1-E01", 1, 0, "hola"),
      observe("M1-N1-L1-E02", 2, 1, "gracias"),
    ]);
    mockFetch(lessonServer(fixture).handler);
    renderLesson();
    await lessonLoaded();

    const preload = Array.from(document.querySelectorAll("video")).filter(
      (v) => v.getAttribute("preload") === "auto",
    );
    expect(preload.map((v) => v.getAttribute("src"))).toContain(SIGN_VIDEO.gracias.src);
  });
});

describe("LessonPage — errores al iniciar", () => {
  it("403 LESSON_LOCKED: «Esta lección aún está bloqueada» y enlace «Volver a la ruta»", async () => {
    const locked = jsonResponse(403, errorBody(403, "LESSON_LOCKED", "Esta lección aún está bloqueada"));
    mockFetch(lessonServer(m1n1l1(), { starts: [locked] }).handler);
    renderLesson();

    expect(await screen.findByText(containingText("Esta lección aún está bloqueada"))).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Volver a la ruta" })).toHaveAttribute("href", "/aprender");
  });

  it("403 NO_HEARTS: «Te quedaste sin vidas por ahora» con enlace a /aprender", async () => {
    const noHearts = jsonResponse(403, errorBody(403, "NO_HEARTS", "Te quedaste sin vidas por ahora"));
    mockFetch(lessonServer(m1n1l1(), { starts: [noHearts] }).handler);
    renderLesson("M1-N1-L2");

    expect(await screen.findByText(containingText("Te quedaste sin vidas por ahora"))).toBeInTheDocument();
    const links = screen.getAllByRole("link").map((l) => l.getAttribute("href"));
    expect(links).toContain("/aprender");
  });
});

describe("LessonPage — sesión expirada (R4.10b)", () => {
  it("410 SESSION_EXPIRED al responder muestra el aviso y «Empezar de nuevo» crea una sesión nueva", async () => {
    const user = userEvent.setup();
    const fresh = m1n1l1(NEW_SESSION_ID);
    const server = lessonServer(m1n1l1(), {
      starts: [m1n1l1(), fresh],
      onAnswer: (request) => (request.path === ANSWERS ? sessionExpired() : undefined),
    });
    const api = mockFetch(server.handler);
    renderLesson();
    await lessonLoaded();

    await answerObserve(user);

    expect(
      await screen.findByText(containingText("Esta lección se actualizó o pasó mucho tiempo. Empecemos de nuevo")),
    ).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Empezar de nuevo" }));

    await waitFor(() => expect(api.to(START, "POST")).toHaveLength(2));
    await lessonLoaded();
    expect(progressValue()).toBe(0);

    await answerObserve(user);
    await waitFor(() => expect(api.to(`/api/lesson-sessions/${NEW_SESSION_ID}/answers`, "POST")).toHaveLength(1));
    expect(
      screen.queryByText(containingText("Esta lección se actualizó o pasó mucho tiempo")),
    ).not.toBeInTheDocument();
  });

  it("410 SESSION_EXPIRED al completar también ofrece «Empezar de nuevo»", async () => {
    const user = userEvent.setup();
    const fixture = lessonFixture(LESSON_INFO.L1, [observe("M1-N1-L1-E01", 1, 0, "hola")]);
    mockFetch(lessonServer(fixture, { completion: sessionExpired() }).handler);
    renderLesson();
    await lessonLoaded();

    await answerObserve(user);

    expect(
      await screen.findByText(containingText("Esta lección se actualizó o pasó mucho tiempo. Empecemos de nuevo")),
    ).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Empezar de nuevo" })).toBeInTheDocument();
  });
});

describe("LessonPage — salir (R4.11)", () => {
  const CONFIRM = "¿Salir de la lección? Perderás el avance de esta sesión.";

  it("sin respuestas, ✕ sale directo a /aprender sin confirmar", async () => {
    const user = userEvent.setup();
    const confirm = vi.spyOn(window, "confirm").mockReturnValue(false);
    mockFetch(lessonServer(m1n1l1()).handler);
    const router = renderLesson();
    await lessonLoaded();

    await user.click(screen.getByRole("button", { name: "Salir de la lección" }));

    await waitFor(() => expect(router.state.location.pathname).toBe("/aprender"));
    expect(confirm).not.toHaveBeenCalled();
  });

  it("con respuestas pide confirmación y, si la rechaza, se queda en la lección", async () => {
    const user = userEvent.setup();
    const confirm = vi.spyOn(window, "confirm").mockReturnValue(false);
    const api = mockFetch(lessonServer(m1n1l1()).handler);
    const router = renderLesson();
    await lessonLoaded();
    await answerObserve(user);
    await waitFor(() => expect(api.to(ANSWERS, "POST")).toHaveLength(1));

    await user.click(screen.getByRole("button", { name: "Salir de la lección" }));

    expect(confirm).toHaveBeenCalledWith(CONFIRM);
    expect(router.state.location.pathname).toBe("/leccion/M1-N1-L1");
  });

  it("con respuestas, si acepta la confirmación, vuelve a /aprender", async () => {
    const user = userEvent.setup();
    const confirm = vi.spyOn(window, "confirm").mockReturnValue(true);
    const api = mockFetch(lessonServer(m1n1l1()).handler);
    const router = renderLesson();
    await lessonLoaded();
    await answerObserve(user);
    await waitFor(() => expect(api.to(ANSWERS, "POST")).toHaveLength(1));

    await user.click(screen.getByRole("button", { name: "Salir de la lección" }));

    expect(confirm).toHaveBeenCalledWith(CONFIRM);
    await waitFor(() => expect(router.state.location.pathname).toBe("/aprender"));
  });

  it("registra beforeunload solo cuando ya hay respuestas", async () => {
    const user = userEvent.setup();
    const api = mockFetch(lessonServer(m1n1l1()).handler);
    renderLesson();
    await lessonLoaded();

    const before = new Event("beforeunload", { cancelable: true });
    window.dispatchEvent(before);
    expect(before.defaultPrevented).toBe(false);

    await answerObserve(user);
    await waitFor(() => expect(api.to(ANSWERS, "POST")).toHaveLength(1));

    await waitFor(() => {
      const after = new Event("beforeunload", { cancelable: true });
      window.dispatchEvent(after);
      expect(after.defaultPrevented).toBe(true);
    });
  });
});

describe("LessonPage — completar (R4.9, R4.10)", () => {
  const SHORT = () =>
    lessonFixture(LESSON_INFO.L1, [observe("M1-N1-L1-E01", 1, 0, "hola"), produce("M1-N1-L1-E02", 2, 0, "hola")]);

  it("no completa antes del último ejercicio; al responderlo hace UN POST …/complete y celebra", async () => {
    const user = userEvent.setup();
    const api = mockFetch(lessonServer(SHORT()).handler);
    renderLesson("M1-N1-L1", { strict: true });
    await lessonLoaded();

    await answerObserve(user);
    await waitFor(() => expect(api.to(ANSWERS, "POST")).toHaveLength(1));
    expect(api.to(COMPLETE, "POST")).toHaveLength(0);

    await answerProduce(user);

    expect(await screen.findByText(containingText("¡Lección completada!"))).toBeInTheDocument();
    expect(api.to(COMPLETE, "POST")).toHaveLength(1);
    expect(bearer(api.to(COMPLETE, "POST")[0])).toBe("Bearer t");
    expect(screen.getByText(/83\s%/)).toBeInTheDocument();
    expect(screen.getByText(containingText("+16 XP"))).toBeInTheDocument();
    expect(screen.getByText(containingText("+4 néctar"))).toBeInTheDocument();
    expect(screen.getByText(containingText(COMPLETION_PASSED.mascotMessage))).toBeInTheDocument();
  });

  it("si no aprueba muestra «¡Buen intento!» con su puntaje", async () => {
    const user = userEvent.setup();
    mockFetch(lessonServer(SHORT(), { completion: COMPLETION_FAILED }).handler);
    renderLesson();
    await lessonLoaded();

    await answerObserve(user);
    await answerProduce(user);

    expect(await screen.findByText(containingText("¡Buen intento!"))).toBeInTheDocument();
    expect(screen.queryByText(containingText("¡Lección completada!"))).not.toBeInTheDocument();
    expect(screen.getByText(/50\s%/)).toBeInTheDocument();
    expect(screen.getByText(containingText("+5 XP"))).toBeInTheDocument();
    expect(screen.getByText(containingText("+1 néctar"))).toBeInTheDocument();
    expect(screen.getByText(containingText(COMPLETION_FAILED.mascotMessage))).toBeInTheDocument();
  });

  it("«Volver a la ruta» lleva a /aprender", async () => {
    const user = userEvent.setup();
    mockFetch(lessonServer(SHORT()).handler);
    const router = renderLesson();
    await lessonLoaded();
    await answerObserve(user);
    await answerProduce(user);
    await screen.findByText(containingText("¡Lección completada!"));

    const back =
      screen.queryByRole("link", { name: "Volver a la ruta" }) ??
      screen.getByRole("button", { name: "Volver a la ruta" });
    await user.click(back);

    await waitFor(() => expect(router.state.location.pathname).toBe("/aprender"));
  });

  it("al terminar ya no pide confirmación para salir", async () => {
    const user = userEvent.setup();
    const confirm = vi.spyOn(window, "confirm").mockReturnValue(false);
    mockFetch(lessonServer(SHORT()).handler);
    const router = renderLesson();
    await lessonLoaded();
    await answerObserve(user);
    await answerProduce(user);
    await screen.findByText(containingText("¡Lección completada!"));

    const back =
      screen.queryByRole("link", { name: "Volver a la ruta" }) ??
      screen.getByRole("button", { name: "Volver a la ruta" });
    await user.click(back);

    await waitFor(() => expect(router.state.location.pathname).toBe("/aprender"));
    expect(confirm).not.toHaveBeenCalled();
  });
});

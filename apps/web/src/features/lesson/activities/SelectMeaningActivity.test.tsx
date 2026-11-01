// Selecciona el significado (VIDEO_TO_MEANING y MEANING_TO_VIDEO) probado dentro de LessonPage,
// que es quien conoce la sesión y envía las respuestas (R4.4, R4.5, R4.6, R4.14).
import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { useSessionStore } from "../../../lib/session-store";
import { makeUser, mockFetch } from "../../../test/http";
import {
  containingText,
  LESSON_INFO,
  lessonFixture,
  lessonLoaded,
  lessonServer,
  meaningToVideo,
  mockMedia,
  observe,
  renderLesson,
  SESSION_ID,
  SIGN_VIDEO,
  stubScrollIntoView,
  videoToMeaning,
  type AnswerOut,
  type Word,
} from "../../../test/lesson";

const ANSWERS = `/api/lesson-sessions/${SESSION_ID}/answers`;
const WORDS: Word[] = ["hola", "gracias", "buenos días", "hasta luego"];

beforeEach(() => {
  mockMedia();
  stubScrollIntoView();
  useSessionStore.setState({ accessToken: "t", user: makeUser(), status: "authenticated" });
});

afterEach(() => {
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
  useSessionStore.setState(useSessionStore.getInitialState(), true);
});

/** Reconoce: VIDEO_TO_MEANING de «hola» seguido de un OBSERVE (para que «Continuar» avance). */
function v2mLesson() {
  const select = videoToMeaning("M1-N1-L2-E01", 1, 0, "hola", ["gracias", "buenos días", "hasta luego"]);
  const next = observe("M1-N1-L2-E02", 2, 1, "gracias");
  return { select, fixture: lessonFixture(LESSON_INFO.L2, [select, next]) };
}

function m2vLesson() {
  const select = meaningToVideo("M1-N1-L2-E01", 1, 0, "hola", ["gracias", "buenos días", "por favor"]);
  const next = observe("M1-N1-L2-E02", 2, 1, "gracias");
  return { select, fixture: lessonFixture(LESSON_INFO.L2, [select, next]) };
}

function options(): HTMLElement[] {
  const group = screen.getByRole("radiogroup");
  return within(group).getAllByRole("radio");
}

/** Índice (0–3) en pantalla de la opción con ese token: el orden público es el del payload. */
function indexOfToken(tokens: string[], token: string): number {
  const i = tokens.indexOf(token);
  expect(i).toBeGreaterThanOrEqual(0);
  return i;
}

function wordTokens(select: ReturnType<typeof v2mLesson>["select"]): string[] {
  const content = select.exercise.content;
  if (content.type !== "VIDEO_TO_MEANING") throw new Error("Se esperaba VIDEO_TO_MEANING");
  return content.options.map((o) => o.token);
}

function tomiMessage(text: string): HTMLElement {
  const statuses = screen.getAllByRole("status").filter((s) => (s.textContent ?? "").includes(text));
  expect(statuses.length).toBeGreaterThan(0);
  return statuses[0];
}

describe("SelectMeaningActivity — VIDEO_TO_MEANING", () => {
  it("muestra 4 opciones de palabra como radios numerados 1–4 en un radiogroup, en el orden recibido", async () => {
    const { select, fixture } = v2mLesson();
    mockFetch(lessonServer(fixture).handler);
    renderLesson("M1-N1-L2");
    await lessonLoaded();

    const radios = await screen.findAllByRole("radio");
    expect(radios).toHaveLength(4);
    expect(screen.getByRole("radiogroup")).toBeInTheDocument();
    const content = select.exercise.content;
    if (content.type !== "VIDEO_TO_MEANING") throw new Error("tipo");
    content.options.forEach((option, i) => {
      expect(radios[i]).toHaveTextContent(option.word);
      expect(radios[i]).toHaveTextContent(String(i + 1));
    });
    const stimulus = Array.from(document.querySelectorAll("video")).find(
      (v) => v.getAttribute("src") === SIGN_VIDEO.hola.src,
    );
    expect(stimulus).toBeDefined();
  });

  it("R4.4: antes de responder no hay data-correct, ni «Correcta», ni la palabra correcta en etiquetas", async () => {
    const { fixture } = v2mLesson();
    mockFetch(lessonServer(fixture).handler);
    renderLesson("M1-N1-L2");
    await lessonLoaded();
    await screen.findAllByRole("radio");

    expect(document.querySelector("[data-correct]")).toBeNull();
    expect(screen.queryByText(/Correcta/)).not.toBeInTheDocument();
    expect(screen.queryByText(/Incorrecta/)).not.toBeInTheDocument();
    const labels = Array.from(document.querySelectorAll("[aria-label]")).map((el) => el.getAttribute("aria-label") ?? "");
    expect(labels.filter((l) => l.toLowerCase().includes("hola"))).toEqual([]);
    const titles = Array.from(document.querySelectorAll("[title]")).map((el) => el.getAttribute("title") ?? "");
    expect(titles.filter((t) => t.toLowerCase().includes("hola"))).toEqual([]);
  });

  it("«Comprobar respuesta» está deshabilitado hasta elegir una opción", async () => {
    const user = userEvent.setup();
    const { fixture } = v2mLesson();
    const api = mockFetch(lessonServer(fixture).handler);
    renderLesson("M1-N1-L2");
    await lessonLoaded();

    const check = await screen.findByRole("button", { name: "Comprobar respuesta" });
    expect(check).toBeDisabled();
    await user.click(check);
    expect(api.to(ANSWERS, "POST")).toHaveLength(0);

    await user.click(options()[2]);
    expect(options()[2]).toBeChecked();
    expect(screen.getByRole("button", { name: "Comprobar respuesta" })).toBeEnabled();
  });

  it("acierto: envía {exerciseId, answer:{optionToken}}, marca «Correcta» y Tomi dice «¡Exacto!»", async () => {
    const user = userEvent.setup();
    const { select, fixture } = v2mLesson();
    const api = mockFetch(lessonServer(fixture).handler);
    renderLesson("M1-N1-L2");
    await lessonLoaded();

    const tokens = wordTokens(select);
    const correct = indexOfToken(tokens, select.tokenOf.hola);
    await user.click((await screen.findAllByRole("radio"))[correct]);
    await user.click(screen.getByRole("button", { name: "Comprobar respuesta" }));

    await waitFor(() => expect(api.to(ANSWERS, "POST")).toHaveLength(1));
    expect(api.to(ANSWERS, "POST")[0].body).toEqual({
      exerciseId: "M1-N1-L2-E01",
      answer: { optionToken: select.tokenOf.hola },
    });
    await waitFor(() => expect(options()[correct]).toHaveTextContent("Correcta"));
    expect(screen.queryByText(/Incorrecta/)).not.toBeInTheDocument();
    expect(tomiMessage("¡Exacto!")).toBeInTheDocument();
    expect(screen.getByLabelText("Vidas: 5")).toBeInTheDocument();
  });

  it("error: marca la elegida «Incorrecta», la correcta «Correcta», Tomi anima y se pierde una vida", async () => {
    const user = userEvent.setup();
    const { select, fixture } = v2mLesson();
    mockFetch(lessonServer(fixture).handler);
    renderLesson("M1-N1-L2");
    await lessonLoaded();

    const tokens = wordTokens(select);
    const correct = indexOfToken(tokens, select.tokenOf.hola);
    const wrong = indexOfToken(tokens, select.tokenOf.gracias);
    await user.click((await screen.findAllByRole("radio"))[wrong]);
    await user.click(screen.getByRole("button", { name: "Comprobar respuesta" }));

    await waitFor(() => expect(options()[wrong]).toHaveTextContent("Incorrecta"));
    expect(options()[correct]).toHaveTextContent("Correcta");
    expect(options()[correct]).not.toHaveTextContent("Incorrecta");
    expect(tomiMessage("Casi. Mira de nuevo la seña.")).toBeInTheDocument();
    expect(screen.queryByText(/¡Exacto!/)).not.toBeInTheDocument();
    await waitFor(() => expect(screen.getByLabelText("Vidas: 4")).toHaveTextContent(/❤️\s*4/));
  });

  it("tras responder, «Continuar» pasa al siguiente ejercicio", async () => {
    const user = userEvent.setup();
    const { fixture } = v2mLesson();
    mockFetch(lessonServer(fixture).handler);
    renderLesson("M1-N1-L2");
    await lessonLoaded();

    await user.click((await screen.findAllByRole("radio"))[0]);
    await user.click(screen.getByRole("button", { name: "Comprobar respuesta" }));
    expect(screen.queryByRole("button", { name: "Comprobar respuesta" })).not.toBeInTheDocument();
    await user.click(await screen.findByRole("button", { name: "Continuar" }));

    expect(await screen.findByLabelText("Video de la seña gracias")).toBeInTheDocument();
    expect(screen.queryByRole("radiogroup")).not.toBeInTheDocument();
  });

  it("R4.6: si la API responde alreadyAnswered, muestra el resultado del primer intento sin error", async () => {
    const user = userEvent.setup();
    const { select, fixture } = v2mLesson();
    const tokens = wordTokens(select);
    const correct = indexOfToken(tokens, select.tokenOf.hola);
    const replay = (_r: unknown, evaluated: AnswerOut): AnswerOut => ({
      ...evaluated,
      correct: false,
      alreadyAnswered: true,
    });
    mockFetch(lessonServer(fixture, { onAnswer: replay }).handler);
    renderLesson("M1-N1-L2");
    await lessonLoaded();

    // En este intento elige la correcta, pero el servidor conserva el primer intento (incorrecto).
    await user.click((await screen.findAllByRole("radio"))[correct]);
    await user.click(screen.getByRole("button", { name: "Comprobar respuesta" }));

    await waitFor(() => expect(options()[correct]).toHaveTextContent("Correcta"));
    expect(tomiMessage("Casi. Mira de nuevo la seña.")).toBeInTheDocument();
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
    expect(await screen.findByRole("button", { name: "Continuar" })).toBeInTheDocument();
  });
});

describe("SelectMeaningActivity — MEANING_TO_VIDEO", () => {
  it("muestra la palabra y 4 opciones de video «Opción n» sin revelar la palabra en etiquetas", async () => {
    const { select, fixture } = m2vLesson();
    mockFetch(lessonServer(fixture).handler);
    renderLesson("M1-N1-L2");
    await lessonLoaded();

    const radios = await screen.findAllByRole("radio");
    expect(radios).toHaveLength(4);
    expect(screen.getByText(containingText("hola"))).toBeInTheDocument();
    const content = select.exercise.content;
    if (content.type !== "MEANING_TO_VIDEO") throw new Error("tipo");
    content.options.forEach((option, i) => {
      const optionVideo = screen.getByLabelText(`Opción ${i + 1}`);
      const el = optionVideo instanceof HTMLVideoElement ? optionVideo : optionVideo.querySelector("video");
      expect(el?.getAttribute("src")).toBe(option.video.src);
    });
    expect(document.querySelector("[data-correct]")).toBeNull();
    expect(screen.queryByText(/Correcta/)).not.toBeInTheDocument();
    const labels = Array.from(document.querySelectorAll("[aria-label]")).map((el) => el.getAttribute("aria-label") ?? "");
    expect(labels.filter((l) => l.toLowerCase().includes("hola"))).toEqual([]);
  });

  it("envía el token del video elegido y marca la correcta", async () => {
    const user = userEvent.setup();
    const { select, fixture } = m2vLesson();
    const api = mockFetch(lessonServer(fixture).handler);
    renderLesson("M1-N1-L2");
    await lessonLoaded();

    const content = select.exercise.content;
    if (content.type !== "MEANING_TO_VIDEO") throw new Error("tipo");
    const tokens = content.options.map((o) => o.token);
    const correct = indexOfToken(tokens, select.tokenOf.hola);
    const wrong = indexOfToken(tokens, select.tokenOf["por favor"]);

    await user.click((await screen.findAllByRole("radio"))[wrong]);
    await user.click(screen.getByRole("button", { name: "Comprobar respuesta" }));

    await waitFor(() => expect(api.to(ANSWERS, "POST")).toHaveLength(1));
    expect(api.to(ANSWERS, "POST")[0].body).toEqual({
      exerciseId: "M1-N1-L2-E01",
      answer: { optionToken: select.tokenOf["por favor"] },
    });
    await waitFor(() => expect(options()[correct]).toHaveTextContent("Correcta"));
    expect(options()[wrong]).toHaveTextContent("Incorrecta");
  });
});

describe("SelectMeaningActivity — atajos de teclado (R4.14, §9.7)", () => {
  it("las teclas 1–4 eligen la opción n", async () => {
    const user = userEvent.setup();
    const { fixture } = v2mLesson();
    mockFetch(lessonServer(fixture).handler);
    renderLesson("M1-N1-L2");
    await lessonLoaded();
    await screen.findAllByRole("radio");

    for (const key of ["2", "4", "1", "3"]) {
      await user.keyboard(key);
      const n = Number(key) - 1;
      options().forEach((radio, i) => {
        if (i === n) expect(radio).toBeChecked();
        else expect(radio).not.toBeChecked();
      });
    }
  });

  it("Enter sin opción elegida no envía nada", async () => {
    const user = userEvent.setup();
    const { fixture } = v2mLesson();
    const api = mockFetch(lessonServer(fixture).handler);
    renderLesson("M1-N1-L2");
    await lessonLoaded();
    await screen.findAllByRole("radio");

    await user.keyboard("{Enter}");
    await new Promise((resolve) => setTimeout(resolve, 20));
    expect(api.to(ANSWERS, "POST")).toHaveLength(0);
  });

  it("«2» y Enter comprueban la opción 2; otro Enter continúa al siguiente ejercicio", async () => {
    const user = userEvent.setup();
    const { select, fixture } = v2mLesson();
    const api = mockFetch(lessonServer(fixture).handler);
    renderLesson("M1-N1-L2");
    await lessonLoaded();
    await screen.findAllByRole("radio");

    await user.keyboard("2");
    await user.keyboard("{Enter}");

    await waitFor(() => expect(api.to(ANSWERS, "POST")).toHaveLength(1));
    expect(api.to(ANSWERS, "POST")[0].body).toEqual({
      exerciseId: "M1-N1-L2-E01",
      answer: { optionToken: wordTokens(select)[1] },
    });
    await screen.findByRole("button", { name: "Continuar" });

    await user.keyboard("{Enter}");

    expect(await screen.findByLabelText("Video de la seña gracias")).toBeInTheDocument();
    expect(api.to(ANSWERS, "POST")).toHaveLength(1);
  });

  it("las teclas de número no cambian la opción después de comprobar", async () => {
    const user = userEvent.setup();
    const { fixture } = v2mLesson();
    const api = mockFetch(lessonServer(fixture).handler);
    renderLesson("M1-N1-L2");
    await lessonLoaded();
    await screen.findAllByRole("radio");

    await user.keyboard("1");
    await user.keyboard("{Enter}");
    await waitFor(() => expect(api.to(ANSWERS, "POST")).toHaveLength(1));
    await screen.findByRole("button", { name: "Continuar" });

    await user.keyboard("3");
    expect(options()[0]).toBeChecked();
    expect(options()[2]).not.toBeChecked();
    expect(api.to(ANSWERS, "POST")).toHaveLength(1);
  });
});

describe("SelectMeaningActivity — 1366×768 (R4.13, B33)", () => {
  it("el video, la pregunta, las 4 opciones y «Comprobar respuesta» se muestran juntos en la actividad activa", async () => {
    const { fixture } = v2mLesson();
    mockFetch(lessonServer(fixture).handler);
    renderLesson("M1-N1-L2");
    await lessonLoaded();

    // jsdom no calcula el diseño: aquí solo se verifica que todo está presente a la vez,
    // sin pasos intermedios; el encaje sin scroll se comprueba en Playwright (1366×768).
    expect(await screen.findAllByRole("radio")).toHaveLength(4);
    expect(screen.getByRole("button", { name: "Comprobar respuesta" })).toBeInTheDocument();
    const stimulus = Array.from(document.querySelectorAll("video")).filter(
      (v) => v.getAttribute("src") === SIGN_VIDEO.hola.src && v.getAttribute("preload") !== "auto",
    );
    expect(stimulus).toHaveLength(1);
    expect(WORDS.every((w) => screen.getAllByRole("radio").some((r) => (r.textContent ?? "").includes(w)))).toBe(true);
  });
});

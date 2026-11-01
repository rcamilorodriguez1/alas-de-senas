// ObserveActivity y ProduceActivity dentro de LessonPage (R4.7, R4.8).
import { screen, waitFor } from "@testing-library/react";
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
  mockMedia,
  observe,
  produce,
  renderLesson,
  SESSION_ID,
  SIGN_VIDEO,
  stubScrollIntoView,
} from "../../../test/lesson";

const ANSWERS = `/api/lesson-sessions/${SESSION_ID}/answers`;

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

describe("ObserveActivity", () => {
  it("muestra el video de la seña, la palabra, cómo se hace y el ejemplo de uso", async () => {
    const fixture = lessonFixture(LESSON_INFO.L1, [
      observe("M1-N1-L1-E01", 1, 0, "buenos días", {
        howTo: "Mano plana desde el mentón hacia adelante.",
        usageExample: "Buenos días, profesora.",
      }),
      observe("M1-N1-L1-E02", 2, 1, "gracias"),
    ]);
    mockFetch(lessonServer(fixture).handler);
    renderLesson();
    await lessonLoaded();

    const video = screen.getByLabelText("Video de la seña buenos días");
    expect(video).toBeInstanceOf(HTMLVideoElement);
    expect(video.getAttribute("src")).toBe(SIGN_VIDEO["buenos días"].src);
    expect(screen.getAllByText(containingText("buenos días")).length).toBeGreaterThan(0);
    expect(screen.getByText(containingText("Mano plana desde el mentón hacia adelante."))).toBeInTheDocument();
    expect(screen.getByText(containingText("Buenos días, profesora."))).toBeInTheDocument();
  });

  it("si howTo es null muestra «Descripción en revisión»", async () => {
    const fixture = lessonFixture(LESSON_INFO.L1, [
      observe("M1-N1-L1-E01", 1, 0, "señor", { howTo: null }),
      observe("M1-N1-L1-E02", 2, 1, "gracias"),
    ]);
    mockFetch(lessonServer(fixture).handler);
    renderLesson();
    await lessonLoaded();

    expect(screen.getByLabelText("Video de la seña señor")).toBeInTheDocument();
    expect(screen.getByText(containingText("Descripción en revisión"))).toBeInTheDocument();
  });

  it("«Continuar» envía {watched: true} y pasa al siguiente ejercicio", async () => {
    const user = userEvent.setup();
    const fixture = lessonFixture(LESSON_INFO.L1, [
      observe("M1-N1-L1-E01", 1, 0, "hola"),
      observe("M1-N1-L1-E02", 2, 1, "gracias"),
    ]);
    const api = mockFetch(lessonServer(fixture).handler);
    renderLesson();
    await lessonLoaded();

    await user.click(screen.getByRole("button", { name: "Continuar" }));

    await waitFor(() => expect(api.to(ANSWERS, "POST")).toHaveLength(1));
    expect(api.to(ANSWERS, "POST")[0].body).toEqual({ exerciseId: "M1-N1-L1-E01", answer: { watched: true } });
    expect(await screen.findByLabelText("Video de la seña gracias")).toBeInTheDocument();
  });

  it("R4.7: observar no cambia las vidas ni muestra acierto o error", async () => {
    const user = userEvent.setup();
    const fixture = lessonFixture(LESSON_INFO.L2, [
      observe("M1-N1-L2-E01", 1, 0, "hola"),
      observe("M1-N1-L2-E02", 2, 1, "gracias"),
    ]);
    mockFetch(lessonServer(fixture).handler);
    renderLesson("M1-N1-L2");
    await lessonLoaded();

    await user.click(screen.getByRole("button", { name: "Continuar" }));

    await screen.findByLabelText("Video de la seña gracias");
    expect(screen.getByLabelText("Vidas: 5")).toBeInTheDocument();
    expect(screen.queryByText(/Incorrecta|Correcta/)).not.toBeInTheDocument();
  });
});

describe("ProduceActivity — autoevaluación (R4.8)", () => {
  function produceLesson() {
    return lessonFixture(LESSON_INFO.L1, [
      produce("M1-N1-L1-E01", 1, 0, "hola"),
      observe("M1-N1-L1-E02", 2, 1, "gracias"),
    ]);
  }

  it("muestra el video de referencia y la pregunta «¿Te salió igual al video?»", async () => {
    mockFetch(lessonServer(produceLesson()).handler);
    renderLesson();
    await lessonLoaded();

    expect(await screen.findByText(containingText("¿Te salió igual al video?"))).toBeInTheDocument();
    expect(screen.getByLabelText("Video de la seña hola").getAttribute("src")).toBe(SIGN_VIDEO.hola.src);
    expect(screen.getByRole("button", { name: "Sí, me salió" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Necesito repasar" })).toBeInTheDocument();
  });

  it("«Sí, me salió» envía {method: self, ok: true}", async () => {
    const user = userEvent.setup();
    const api = mockFetch(lessonServer(produceLesson()).handler);
    renderLesson();
    await lessonLoaded();

    await user.click(await screen.findByRole("button", { name: "Sí, me salió" }));

    await waitFor(() => expect(api.to(ANSWERS, "POST")).toHaveLength(1));
    expect(api.to(ANSWERS, "POST")[0].body).toEqual({
      exerciseId: "M1-N1-L1-E01",
      answer: { method: "self", ok: true },
    });
    expect(await screen.findByLabelText("Video de la seña gracias")).toBeInTheDocument();
  });

  it("«Necesito repasar» envía {method: self, ok: false} y no muestra error", async () => {
    const user = userEvent.setup();
    const api = mockFetch(lessonServer(produceLesson()).handler);
    renderLesson();
    await lessonLoaded();

    await user.click(await screen.findByRole("button", { name: "Necesito repasar" }));

    await waitFor(() => expect(api.to(ANSWERS, "POST")).toHaveLength(1));
    expect(api.to(ANSWERS, "POST")[0].body).toEqual({
      exerciseId: "M1-N1-L1-E01",
      answer: { method: "self", ok: false },
    });
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
    expect(await screen.findByLabelText("Video de la seña gracias")).toBeInTheDocument();
  });

  it("no pide la cámara: no llama a getUserMedia", async () => {
    const getUserMedia = vi.fn();
    Object.defineProperty(navigator, "mediaDevices", { configurable: true, value: { getUserMedia } });
    try {
      mockFetch(lessonServer(produceLesson()).handler);
      renderLesson();
      await lessonLoaded();
      await screen.findByRole("button", { name: "Sí, me salió" });
      expect(getUserMedia).not.toHaveBeenCalled();
    } finally {
      Reflect.deleteProperty(navigator, "mediaDevices");
    }
  });
});

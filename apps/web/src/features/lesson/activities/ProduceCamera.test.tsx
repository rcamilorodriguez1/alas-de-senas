// «Produce la seña» con cámara (tarea 10.7, R4.8): solo si la seña está en labels.json.
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { FrameResult } from "../../../camera/session";
import { resetModelLabelsCache } from "../../../camera/labels";
import type { LessonExercise } from "../lesson-api";
import { ProduceActivity } from "./ProduceActivity";

const startCameraSession = vi.fn();
vi.mock("../../../camera/session", async (importOriginal) => {
  const actual = await importOriginal<typeof import("../../../camera/session")>();
  return { ...actual, startCameraSession: (...args: unknown[]) => startCameraSession(...args) };
});

const exercise = (cameraLabel: string | null): LessonExercise => ({
  id: "M1-N3-L3-E05",
  order: 5,
  activity: "PRODUCE",
  type: "PRODUCE",
  scored: false,
  group: 0,
  content: {
    type: "PRODUCE",
    video: { src: "/media/v/a.mp4", poster: "/media/p/a.webp", placeholder: true, source: "placeholder" },
    word: "A",
    cameraLabel,
  },
});

function stubLabels(labels: string[] | null) {
  vi.stubGlobal(
    "fetch",
    vi.fn(async (input: RequestInfo | URL) => {
      const url = String(input);
      if (url.endsWith("/labels.json")) {
        return labels ? new Response(JSON.stringify(labels), { status: 200 }) : new Response("", { status: 404 });
      }
      return new Response("{}", { status: 200 });
    }),
  );
}

beforeEach(() => {
  resetModelLabelsCache();
  startCameraSession.mockReset();
  vi.spyOn(HTMLMediaElement.prototype, "play").mockResolvedValue(undefined);
  vi.spyOn(HTMLMediaElement.prototype, "pause").mockImplementation(() => undefined);
  vi.spyOn(HTMLMediaElement.prototype, "load").mockImplementation(() => undefined);
});

afterEach(() => {
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
});

describe("ProduceActivity con cámara", () => {
  it("sin modelo entrenado solo ofrece autoevaluación", async () => {
    stubLabels(null);
    render(<ProduceActivity exercise={exercise("letra-a")} onSubmit={vi.fn()} onContinue={vi.fn()} />);
    expect(await screen.findByRole("button", { name: "Sí, me salió" })).toBeInTheDocument();
    await waitFor(() => expect(screen.queryByRole("button", { name: "Usar la cámara" })).not.toBeInTheDocument());
  });

  it("si la seña no está en labels.json no ofrece la cámara", async () => {
    stubLabels(["NINGUNA", "letra-b"]);
    render(<ProduceActivity exercise={exercise("letra-a")} onSubmit={vi.fn()} onContinue={vi.fn()} />);
    await new Promise((resolve) => setTimeout(resolve, 0));
    expect(screen.queryByRole("button", { name: "Usar la cámara" })).not.toBeInTheDocument();
  });

  it("si el modelo la conoce, al reconocerla envía method «camera» con la confianza", async () => {
    stubLabels(["NINGUNA", "letra-a"]);
    const user = userEvent.setup();
    const stop = vi.fn();
    const camera: { frame: ((result: FrameResult) => void) | null } = { frame: null };
    startCameraSession.mockImplementation(async (_video: HTMLVideoElement, onFrame: (r: FrameResult) => void) => {
      camera.frame = onFrame;
      return { classifier: { simulated: false }, stop };
    });
    const onSubmit = vi.fn(async () => ({
      correct: true, correctToken: null, correctTokens: [], correctWord: null, alreadyAnswered: false,
    }));
    const onContinue = vi.fn();
    render(<ProduceActivity exercise={exercise("letra-a")} onSubmit={onSubmit} onContinue={onContinue} />);

    await user.click(await screen.findByRole("button", { name: "Usar la cámara" }));
    await waitFor(() => expect(camera.frame).not.toBeNull());
    camera.frame?.({ points: null, features: null, detected: { label: "letra-b", confidence: 0.9 } });
    expect(onSubmit).not.toHaveBeenCalled();
    camera.frame?.({ points: null, features: null, detected: { label: "letra-a", confidence: 0.85 } });

    await waitFor(() => expect(onSubmit).toHaveBeenCalledWith({ method: "camera", ok: true, confidence: 0.85 }));
    await waitFor(() => expect(onContinue).toHaveBeenCalled());
    expect(stop).toHaveBeenCalled(); // la cámara se apaga al terminar
  });

  it("acepta una seña con la misma forma de mano: piden «B» y la cámara ve «4» (D-027)", async () => {
    stubLabels(["NINGUNA", "letra-b", "numero-4"]);
    const user = userEvent.setup();
    const camera: { frame: ((result: FrameResult) => void) | null } = { frame: null };
    startCameraSession.mockImplementation(async (_video: HTMLVideoElement, onFrame: (r: FrameResult) => void) => {
      camera.frame = onFrame;
      return { classifier: { simulated: false }, stop: vi.fn() };
    });
    const onSubmit = vi.fn(async () => ({
      correct: true, correctToken: null, correctTokens: [], correctWord: null, alreadyAnswered: false,
    }));
    render(<ProduceActivity exercise={exercise("letra-b")} onSubmit={onSubmit} onContinue={vi.fn()} />);

    await user.click(await screen.findByRole("button", { name: "Usar la cámara" }));
    await waitFor(() => expect(camera.frame).not.toBeNull());
    camera.frame?.({ points: null, features: null, detected: { label: "numero-4", confidence: 0.8 } });
    await waitFor(() => expect(onSubmit).toHaveBeenCalledWith({ method: "camera", ok: true, confidence: 0.8 }));
  });
});

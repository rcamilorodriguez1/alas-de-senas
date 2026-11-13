// Cámara holística: modo de 2 s y modo manual «Empezar / Terminar» (plan de mejora, etapa 6; D-045).
import { act, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { FIXED_CAPTURE, MANUAL_CAPTURE } from "../../camera/holistic/capture";
import type { GestureFrame, RecordedSample } from "../../camera/holistic/gesture-session";

const sample: RecordedSample = {
  frames: [],
  quality: { faceRatio: 1, domHandRatio: 1, poseRatio: 1 },
  check: { ok: true },
  switchedHand: false,
};

const end = vi.fn();
const cancel = vi.fn();
const capture = vi.fn();
const stop = vi.fn();
let pushFrame: (frame: GestureFrame) => void = () => undefined;
let settle: (value: RecordedSample) => void = () => undefined;

vi.mock("../../camera/holistic/gesture-session", () => ({
  startGestureSession: (_video: HTMLVideoElement, options: { onFrame: (frame: GestureFrame) => void }) => {
    pushFrame = options.onFrame;
    return Promise.resolve({ delegate: "CPU", record: vi.fn(), capture, stop });
  },
}));

import { COUNTDOWN_S, GestureCamera } from "./GestureCamera";

beforeEach(() => {
  vi.useFakeTimers({ toFake: ["setTimeout", "clearTimeout"] });
  for (const mock of [end, cancel, capture, stop]) mock.mockReset();
  capture.mockImplementation(() => ({
    result: new Promise<RecordedSample>((resolve) => {
      settle = resolve;
    }),
    end: () => {
      end();
      settle(sample);
    },
    cancel: () => {
      cancel();
      settle({ ...sample, check: { ok: false, reason: "Cancelaste la grabación." } });
    },
  }));
});

afterEach(() => {
  vi.useRealTimers();
});

async function startRecording(manual: boolean, onSample = vi.fn()) {
  const view = render(
    <GestureCamera dominantHand="right" onSample={onSample} recordText="Hacer la seña" manual={manual} />,
  );
  await act(async () => {
    fireEvent.click(screen.getByRole("button", { name: "Activar cámara" }));
    await Promise.resolve();
  });
  act(() => pushFrame({ overlay: null, guidance: [], ready: true, fps: 15, extractMs: 20 }));
  fireEvent.click(screen.getByRole("button", { name: "Hacer la seña" }));
  for (let i = 0; i < COUNTDOWN_S; i += 1) {
    act(() => {
      vi.advanceTimersByTime(1000);
    });
  }
  return { onSample, view };
}

describe("GestureCamera", () => {
  it("modo de 2 s (el de siempre): graba con la ventana fija y sin botón «Terminar»", async () => {
    await startRecording(false);
    expect(capture).toHaveBeenCalledWith(undefined, FIXED_CAPTURE);
    expect(screen.getByRole("status")).toHaveTextContent("¡Haz la seña!");
    expect(screen.queryByRole("button", { name: "Terminar" })).not.toBeInTheDocument();
  });

  it("modo manual: «Terminar» (con el foco) cierra la grabación y entrega la muestra", async () => {
    const { onSample } = await startRecording(true);
    expect(capture).toHaveBeenCalledWith(undefined, MANUAL_CAPTURE);
    const finish = screen.getByRole("button", { name: "Terminar" });
    expect(finish).toHaveFocus();
    expect(screen.getByText(/Pulsa «Terminar» al acabar \(máximo 4 s\)/)).toBeInTheDocument();
    await act(async () => {
      fireEvent.click(finish);
      await Promise.resolve();
    });
    expect(end).toHaveBeenCalledOnce();
    expect(onSample).toHaveBeenCalledWith(sample);
    expect(screen.getByRole("button", { name: "Hacer la seña" })).toBeInTheDocument();
  });

  it("modo manual: «Cancelar» descarta la grabación sin evaluarla", async () => {
    const { onSample } = await startRecording(true);
    await act(async () => {
      fireEvent.click(screen.getByRole("button", { name: "Cancelar" }));
      await Promise.resolve();
    });
    expect(cancel).toHaveBeenCalledOnce();
    expect(onSample).not.toHaveBeenCalled();
    expect(screen.getByRole("button", { name: "Hacer la seña" })).toBeInTheDocument();
  });
});

describe("GestureCamera en modo manual (revisión de D-045)", () => {
  it("cambiar de modo a mitad de la grabación no cambia la grabación en curso", async () => {
    const { view, onSample } = await startRecording(true);
    view.rerender(<GestureCamera dominantHand="right" onSample={onSample} recordText="Hacer la seña" manual={false} />);
    expect(screen.getByRole("button", { name: "Terminar" })).toBeInTheDocument();
  });

  it("al terminar, el foco vuelve a «Hacer la seña»", async () => {
    await startRecording(true);
    await act(async () => {
      fireEvent.click(screen.getByRole("button", { name: "Terminar" }));
      await Promise.resolve();
    });
    expect(screen.getByRole("button", { name: "Hacer la seña" })).toHaveFocus();
  });

  it("al cancelar avisa que la grabación se canceló", async () => {
    await startRecording(true);
    await act(async () => {
      fireEvent.click(screen.getByRole("button", { name: "Cancelar" }));
      await Promise.resolve();
    });
    expect(screen.getByText("Cancelaste la grabación.")).toBeInTheDocument();
  });

  it("salir de la página a mitad de una captura apaga la cámara y no entrega la muestra (R8.5)", async () => {
    const { view, onSample } = await startRecording(true);
    view.unmount();
    await act(async () => {
      settle(sample); // la sesión cierra la grabación como interrumpida
      await Promise.resolve();
    });
    expect(stop).toHaveBeenCalledOnce();
    expect(onSample).not.toHaveBeenCalled();
  });
});
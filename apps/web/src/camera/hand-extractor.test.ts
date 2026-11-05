// Singleton de HandLandmarker del alfabeto (revisión 10B): una creación fallida no descuadra el contador.
import { beforeEach, describe, expect, it, vi } from "vitest";

const instanceClose = vi.fn();
const createFromOptions = vi.fn();
vi.mock("@mediapipe/tasks-vision", () => ({
  FilesetResolver: { forVisionTasks: vi.fn().mockResolvedValue({}) },
  HandLandmarker: { createFromOptions: (...args: unknown[]) => createFromOptions(...args) },
}));

import { HandOnlyExtractorV1 } from "./hand-extractor";

beforeEach(() => {
  instanceClose.mockReset();
  createFromOptions.mockReset();
});

describe("HandOnlyExtractorV1.create", () => {
  it("si la carga falla y luego se reintenta con éxito, al salir el detector se cierra", async () => {
    createFromOptions.mockRejectedValueOnce(new Error("404 del modelo"));
    await expect(HandOnlyExtractorV1.create()).rejects.toThrow("404");
    createFromOptions.mockResolvedValueOnce({ close: instanceClose, detectForVideo: vi.fn() });
    const extractor = await HandOnlyExtractorV1.create();
    extractor.close();
    await vi.waitFor(() => expect(instanceClose).toHaveBeenCalledOnce());
  });
});

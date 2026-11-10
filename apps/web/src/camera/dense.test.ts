// Red densa en JavaScript (prueba de optimización D-038): debe dar la misma salida que TensorFlow.js
// con el modelo real del alfabeto, sin tocar el backend global de tfjs (lo usa también el 10B).
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import * as tf from "@tensorflow/tfjs";
import { afterAll, beforeAll, describe, expect, it } from "vitest";
import { DenseNetwork } from "./dense";

const MODEL_DIR = fileURLToPath(new URL("../../public/models/lsc-alfabeto", import.meta.url));

interface ModelJson {
  modelTopology: object;
  weightsManifest: { paths: string[]; weights: tf.io.WeightsManifestEntry[] }[];
}

function fileHandler(dir: string): tf.io.IOHandler {
  return {
    load: async () => {
      const json = JSON.parse(readFileSync(`${dir}/model.json`, "utf-8")) as ModelJson;
      const group = json.weightsManifest[0];
      const buffer = Buffer.concat(group.paths.map((p) => readFileSync(`${dir}/${p}`)));
      const weightData = buffer.buffer.slice(buffer.byteOffset, buffer.byteOffset + buffer.byteLength);
      return { modelTopology: json.modelTopology, weightSpecs: group.weights, weightData };
    },
  };
}

function sampleInput(seed: number): number[] {
  return Array.from({ length: 63 }, (_, i) => (((i + 1) * (seed + 7) * 37) % 101) / 50 - 1);
}

describe("DenseNetwork con el modelo real del alfabeto", () => {
  let model: tf.LayersModel;

  beforeAll(async () => {
    await tf.setBackend("cpu");
    model = await tf.loadLayersModel(fileHandler(MODEL_DIR));
  });

  afterAll(() => model.dispose());

  it("reconoce la arquitectura Dense/Dropout del modelo", () => {
    const network = DenseNetwork.fromModel(model);
    expect(network).not.toBeNull();
    expect(network?.inputSize).toBe(63);
    expect(network?.outputSize).toBe(30);
  });

  it("da la misma salida que TensorFlow.js", () => {
    const network = DenseNetwork.fromModel(model);
    if (!network) throw new Error("arquitectura no soportada");
    for (let seed = 0; seed < 20; seed += 1) {
      const input = sampleInput(seed);
      const expected = tf.tidy(() => (model.predict(tf.tensor2d([input])) as tf.Tensor).dataSync());
      const actual = network.predict(input);
      expect(actual.length).toBe(expected.length);
      for (let i = 0; i < expected.length; i += 1) expect(actual[i]).toBeCloseTo(expected[i], 5);
    }
  });

  it("la salida es una distribución (softmax): suma 1", () => {
    const network = DenseNetwork.fromModel(model);
    const output = network?.predict(sampleInput(3)) ?? new Float32Array();
    expect(output.reduce((sum, value) => sum + value, 0)).toBeCloseTo(1, 5);
  });

  it("rechaza una entrada de otro tamaño", () => {
    const network = DenseNetwork.fromModel(model);
    expect(() => network?.predict([1, 2, 3])).toThrow(RangeError);
  });
});

describe("DenseNetwork con arquitecturas no soportadas", () => {
  it("devuelve null si el modelo tiene una capa que no es Dense ni Dropout", () => {
    const model = tf.sequential({
      layers: [tf.layers.dense({ inputShape: [4], units: 3 }), tf.layers.batchNormalization()],
    });
    expect(DenseNetwork.fromModel(model)).toBeNull();
    model.dispose();
  });

  it("devuelve null con una activación desconocida", () => {
    const model = tf.sequential({
      layers: [tf.layers.dense({ inputShape: [4], units: 3, activation: "tanh" })],
    });
    expect(DenseNetwork.fromModel(model)).toBeNull();
    model.dispose();
  });

  it("acepta activación lineal y la calcula igual que tfjs", () => {
    const model = tf.sequential({
      layers: [
        tf.layers.dense({ inputShape: [4], units: 5, activation: "relu" }),
        tf.layers.dense({ units: 2, activation: "linear" }),
      ],
    });
    const network = DenseNetwork.fromModel(model);
    const input = [0.5, -1, 2, 0.25];
    const expected = tf.tidy(() => (model.predict(tf.tensor2d([input])) as tf.Tensor).dataSync());
    const actual = network?.predict(input) ?? new Float32Array();
    for (let i = 0; i < expected.length; i += 1) expect(actual[i]).toBeCloseTo(expected[i], 5);
    model.dispose();
  });
});

// Copiar a apps/web/src/camera/tfjs-compat.test.ts en la tarea 0.9 (no modificar la lógica).
// Verifica que los modelos convertidos desde Python (ml/smoke_tfjs.py) cargan en TensorFlow.js
// y dan la misma salida que en Python. Si falla, NO se debe entrenar nada todavía: revisar D-003.
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import * as tf from "@tensorflow/tfjs";
import { describe, expect, it } from "vitest";

const ROOT = fileURLToPath(new URL("../../../../ml/fixtures/tfjs-smoke", import.meta.url));

interface Reference { inputShape: number[]; expected: number[]; tolerance: number }
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

function fixedInput(shape: number[]): tf.Tensor {
  const size = shape.reduce((a, b) => a * b, 1);
  const values = Float32Array.from({ length: size }, (_, i) => ((i * 37) % 101) / 100 - 0.5);
  return tf.tensor(values, shape);
}

describe.each(["static", "sequence"])("modelo %s convertido desde Python", (name) => {
  it("carga en TensorFlow.js y coincide con la salida de Python", async () => {
    const dir = `${ROOT}/${name}`;
    const ref = JSON.parse(readFileSync(`${dir}/reference.json`, "utf-8")) as Reference;
    const model = await tf.loadLayersModel(fileHandler(dir));
    const output = model.predict(fixedInput(ref.inputShape)) as tf.Tensor;
    const values = Array.from(await output.data());
    expect(values).toHaveLength(ref.expected.length);
    values.forEach((v, i) => expect(Math.abs(v - ref.expected[i])).toBeLessThan(ref.tolerance));
    output.dispose();
    model.dispose();
  });
});

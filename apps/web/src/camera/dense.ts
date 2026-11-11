// Red densa calculada en JavaScript (D-038).
// El modelo del alfabeto es pequeño (63 → 128 → 64 → 30): calcularlo a mano tarda microsegundos y
// evita el viaje a la GPU de `dataSync()` en cada cuadro. No cambia el backend global de tfjs,
// que sigue usando el modelo de gestos del Grupo 10B en la misma página.
import type { LayersModel } from "@tensorflow/tfjs";

type Activation = "relu" | "softmax" | "linear";

interface DenseLayer {
  readonly inputs: number;
  readonly units: number;
  /** Pesos en el orden de Keras: kernel[i * units + j] = peso de la entrada i a la neurona j. */
  readonly kernel: Float32Array;
  readonly bias: Float32Array;
  readonly activation: Activation;
}

export interface DenseNetworkLike {
  readonly inputSize: number;
  readonly outputSize: number;
  predict(input: readonly number[]): Float32Array;
}

function isActivation(value: unknown): value is Activation {
  return value === "relu" || value === "softmax" || value === "linear";
}

export class DenseNetwork implements DenseNetworkLike {
  private constructor(private readonly layers: readonly DenseLayer[]) {}

  get inputSize(): number {
    return this.layers[0].inputs;
  }

  get outputSize(): number {
    return this.layers[this.layers.length - 1].units;
  }

  /** Copia los pesos de un modelo de tfjs; null si tiene capas que no son Dense ni Dropout. */
  static fromModel(model: LayersModel): DenseNetwork | null {
    const layers: DenseLayer[] = [];
    for (const layer of model.layers) {
      const kind = layer.getClassName();
      if (kind === "InputLayer" || kind === "Dropout") continue; // Dropout no hace nada al predecir
      if (kind !== "Dense") return null;
      const activation = layer.getConfig().activation;
      if (!isActivation(activation)) return null;
      const weights = layer.getWeights();
      if (weights.length !== 2 || weights[0].shape.length !== 2) return null;
      const [inputs, units] = weights[0].shape;
      layers.push({
        inputs,
        units,
        kernel: Float32Array.from(weights[0].dataSync()),
        bias: Float32Array.from(weights[1].dataSync()),
        activation,
      });
    }
    if (layers.length === 0) return null;
    for (let i = 1; i < layers.length; i += 1) {
      if (layers[i].inputs !== layers[i - 1].units) return null;
    }
    return new DenseNetwork(layers);
  }

  predict(input: readonly number[]): Float32Array {
    if (input.length !== this.inputSize) {
      throw new RangeError(`Se esperaban ${this.inputSize} valores y llegaron ${input.length}`);
    }
    let current: ArrayLike<number> = input;
    for (const layer of this.layers) current = applyLayer(layer, current);
    return current instanceof Float32Array ? current : Float32Array.from(current);
  }
}

function applyLayer(layer: DenseLayer, input: ArrayLike<number>): Float32Array {
  const output = Float32Array.from(layer.bias);
  for (let i = 0; i < layer.inputs; i += 1) {
    const value = input[i];
    if (value === 0) continue;
    const row = i * layer.units;
    for (let j = 0; j < layer.units; j += 1) output[j] += value * layer.kernel[row + j];
  }
  if (layer.activation === "relu") {
    for (let j = 0; j < output.length; j += 1) if (output[j] < 0) output[j] = 0;
  } else if (layer.activation === "softmax") {
    let max = -Infinity;
    for (const value of output) if (value > max) max = value;
    let sum = 0;
    for (let j = 0; j < output.length; j += 1) {
      output[j] = Math.exp(output[j] - max);
      sum += output[j];
    }
    for (let j = 0; j < output.length; j += 1) output[j] /= sum;
  }
  return output;
}

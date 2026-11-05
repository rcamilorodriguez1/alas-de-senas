// Retroalimentación básica de Tomi (anexo A.10): compara la muestra con el promedio de la seña en el
// entrenamiento (`meta.json` → prototypes). La misma fórmula calcula los promedios en Python.
import { BLENDSHAPES, LAYOUT, PRESENCE_OFFSET } from "./frame";
import type { Prototype } from "./sequence-classifier";

const BROW_UP = LAYOUT.blendshapes + BLENDSHAPES.indexOf("browInnerUp");

/** Distancia muñeca–nariz, altura de la muñeca (respecto a los hombros) y cejas, en promedio. */
export function summarize(frames: readonly Float32Array[]): Prototype | null {
  const withHand = frames.filter((f) => f[LAYOUT.dominant + PRESENCE_OFFSET] >= 0.5);
  if (withHand.length === 0) return null;
  let handFace = 0;
  let handY = 0;
  let browUp = 0;
  for (const f of withHand) {
    handFace += Math.hypot(f[LAYOUT.handFace], f[LAYOUT.handFace + 1]);
    handY += f[LAYOUT.dominant + PRESENCE_OFFSET - 2];
    browUp += f[BROW_UP];
  }
  const n = withHand.length;
  return { handFace: handFace / n, handY: handY / n, browUp: browUp / n };
}

export function tomiFeedback(frames: readonly Float32Array[], target: Prototype | undefined, faceFeatures: boolean): string {
  const sample = summarize(frames);
  if (!sample) return "No vi tu mano. Hazla dentro del cuadro, a la altura del pecho.";
  if (!target) return "Casi. Repite la seña con un movimiento claro, como en el video.";
  // Sin rostro en el modelo (faceFeatures false) sus promedios de cara son 0: esas reglas no aplican.
  if (faceFeatures && sample.handFace > target.handFace * 1.3 + 0.1) {
    return "La forma de la mano va bien; acerca la mano a la cara.";
  }
  if (faceFeatures && sample.handFace < target.handFace * 0.7 - 0.1) {
    return "Aleja un poco la mano de la cara, como en el video.";
  }
  if (sample.handY > target.handY + 0.4) return "Sube un poco la mano.";
  if (sample.handY < target.handY - 0.4) return "Baja un poco la mano.";
  if (faceFeatures && target.browUp > 0.3 && sample.browUp < target.browUp - 0.15) {
    return "Levanta las cejas: también es parte de la seña.";
  }
  return "Casi. Repite la seña con un movimiento claro, como en el video.";
}

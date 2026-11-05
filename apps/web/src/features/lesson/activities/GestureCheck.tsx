import { useCallback, useEffect, useRef, useState } from "react";
import { matchesTarget } from "../../../camera/equivalences";
import { tomiFeedback } from "../../../camera/holistic/feedback";
import type { RecordedSample } from "../../../camera/holistic/gesture-session";
import { loadSequenceClassifier, type SequenceClassifier } from "../../../camera/holistic/sequence-classifier";
import { useSessionStore } from "../../../lib/session-store";
import { GestureCamera } from "../../camera/GestureCamera";

const FACE_REQUIRED = { faceRequired: true } as const;
const FACE_OPTIONAL = { faceRequired: false } as const;

/** Seña con movimiento (anexo A.10): «3, 2, 1… ¡haz la seña!», 2 s y respuesta de Tomi. */
export function GestureCheck({ target, onRecognized }: { target: string; onRecognized: (confidence: number) => void }) {
  const dominantHand = useSessionStore((state) => (state.user?.dominantHand === "left" ? "left" : "right"));
  const classifier = useRef<Promise<SequenceClassifier | null> | null>(null);
  const done = useRef(false);
  const [message, setMessage] = useState<string | null>(null);
  const [faceFeatures, setFaceFeatures] = useState<boolean | null>(null);

  useEffect(() => {
    classifier.current = loadSequenceClassifier();
    const loading = classifier.current;
    void loading.then((model) => setFaceFeatures(model?.meta.faceFeatures ?? true));
    return () => {
      void loading.then((model) => model?.dispose()); // la memoria de tfjs se libera al salir
    };
  }, []);

  const onSample = useCallback(
    async (sample: RecordedSample) => {
      if (done.current) return;
      if (!sample.check.ok) {
        setMessage(`${sample.check.reason} Inténtalo otra vez.`);
        return;
      }
      const model = await classifier.current;
      if (!model) {
        setMessage("El modelo de gestos no está disponible. Usa la autoevaluación.");
        return;
      }
      const prediction = model.classify(sample.frames);
      if (matchesTarget(prediction.label, target)) {
        done.current = true;
        setMessage("¡Muy bien! Tomi reconoció la seña.");
        onRecognized(prediction.confidence);
        return;
      }
      setMessage(`Tomi dice: ${tomiFeedback(sample.frames, model.meta.prototypes[target], model.meta.faceFeatures)}`);
    },
    [onRecognized, target],
  );

  return (
    <div className="space-y-2">
      {faceFeatures === null ? (
        <p role="status" className="text-sm font-semibold text-[#45606A]">
          Preparando el reconocimiento…
        </p>
      ) : (
        // Si el modelo no usa la cara (LSC-54 viene pixelado), no se exige verla (D-025).
        <GestureCamera
          dominantHand={dominantHand}
          requireFace={faceFeatures}
          quality={faceFeatures ? FACE_REQUIRED : FACE_OPTIONAL}
          onSample={(sample) => void onSample(sample)}
          recordText="Hacer la seña"
        />
      )}
      <p role="status" className="min-h-6 text-sm font-semibold text-[#45606A]">
        {message ?? "Pulsa «Hacer la seña»: cuenta 3, 2, 1 y haz la seña completa en 2 segundos."}
      </p>
    </div>
  );
}

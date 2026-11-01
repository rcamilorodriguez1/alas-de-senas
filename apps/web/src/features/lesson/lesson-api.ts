import { apiRequest } from "../../lib/api";
import type { components } from "../../lib/api-types";

type Schemas = components["schemas"];
export type LessonStart = Schemas["LessonStartOut"];
export type LessonExercise = Schemas["PublicExerciseOut"];
export type LessonAnswerResult = Schemas["AnswerOut"];
/** Lo que una actividad necesita de la evaluación (lecciones y repaso, que no trae vidas). */
export type AnswerResult = Pick<
  LessonAnswerResult,
  "correct" | "correctToken" | "correctTokens" | "correctWord" | "alreadyAnswered"
>;
export type LessonCompletion = Schemas["LessonCompletionOut"];
export type Hearts = Schemas["HeartsOut"];
export type VideoRef = Schemas["VideoRef"];
export type AnswerBody = Schemas["AnswerIn"]["answer"];

export function startLessonSession(lessonId: string): Promise<LessonStart> {
  return apiRequest<LessonStart>("POST", `/lessons/${encodeURIComponent(lessonId)}/sessions`);
}

export function sendAnswer(
  sessionId: string,
  exerciseId: string,
  answer: AnswerBody,
): Promise<LessonAnswerResult> {
  return apiRequest<LessonAnswerResult>("POST", `/lesson-sessions/${sessionId}/answers`, {
    body: { exerciseId, answer },
  });
}

export function completeLessonSession(sessionId: string): Promise<LessonCompletion> {
  return apiRequest<LessonCompletion>("POST", `/lesson-sessions/${sessionId}/complete`);
}

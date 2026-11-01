import { apiRequest } from "../../lib/api";
import type { components } from "../../lib/api-types";

type Schemas = components["schemas"];
export type LessonStart = Schemas["LessonStartOut"];
export type LessonExercise = Schemas["PublicExerciseOut"];
export type AnswerResult = Schemas["AnswerOut"];
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
): Promise<AnswerResult> {
  return apiRequest<AnswerResult>("POST", `/lesson-sessions/${sessionId}/answers`, {
    body: { exerciseId, answer },
  });
}

export function completeLessonSession(sessionId: string): Promise<LessonCompletion> {
  return apiRequest<LessonCompletion>("POST", `/lesson-sessions/${sessionId}/complete`);
}

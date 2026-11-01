import { useQuery } from "@tanstack/react-query";
import { apiRequest } from "../../lib/api";
import { useSessionStore } from "../../lib/session-store";
import type { components } from "../../lib/api-types";
import type { AnswerBody } from "../lesson/lesson-api";

type Schemas = components["schemas"];
export type ReviewQueue = Schemas["ReviewQueueOut"];
export type ReviewStart = Schemas["ReviewStartOut"];
export type ReviewExercise = Schemas["ReviewExerciseOut"];
export type ReviewAnswer = Schemas["ReviewAnswerOut"];
export type ReviewCompletion = Schemas["ReviewCompletionOut"];

export const reviewQueueKey = ["reviews", "queue"] as const;

export function useReviewQueue() {
  const authenticated = useSessionStore((state) => state.status === "authenticated");
  return useQuery({
    queryKey: reviewQueueKey,
    enabled: authenticated,
    queryFn: () => apiRequest<ReviewQueue>("GET", "/reviews/queue"),
  });
}

export function startReview(): Promise<ReviewStart> {
  return apiRequest<ReviewStart>("POST", "/reviews/sessions");
}

export function sendReviewAnswer(
  sessionId: string,
  exerciseId: string,
  answer: AnswerBody,
): Promise<ReviewAnswer> {
  return apiRequest<ReviewAnswer>("POST", `/review-sessions/${sessionId}/answers`, {
    body: { exerciseId, answer },
  });
}

export function completeReview(sessionId: string): Promise<ReviewCompletion> {
  return apiRequest<ReviewCompletion>("POST", `/review-sessions/${sessionId}/complete`);
}

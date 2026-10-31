import { useQuery } from "@tanstack/react-query";
import { apiRequest } from "../../lib/api";
import type { components } from "../../lib/api-types";

export type LearningPath = components["schemas"]["LearningPathOut"];
export type LearningModule = components["schemas"]["ModuleOut"];
export type LearningNode = components["schemas"]["NodeSummaryOut"];
export type LearningLesson = components["schemas"]["LessonSummaryOut"];

export const learningPathKey = ["learning-path"] as const;

export function fetchLearningPath(): Promise<LearningPath> {
  return apiRequest<LearningPath>("GET", "/learning-path");
}

export function useLearningPath() {
  return useQuery({ queryKey: learningPathKey, queryFn: fetchLearningPath });
}

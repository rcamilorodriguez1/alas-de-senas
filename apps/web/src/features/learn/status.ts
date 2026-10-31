import type { LearningLesson, LearningNode } from "./learn-api";

/** El estado siempre se dice con texto, no solo con color (§9.5, accesibilidad R10.5). */
export const NODE_STATUS_TEXT: Record<LearningNode["status"], string> = {
  LOCKED: "Bloqueado",
  AVAILABLE: "Disponible",
  IN_PROGRESS: "En progreso",
  COMPLETED: "Completado",
  GOLDEN: "Dorado",
  COMING_SOON: "Próximamente",
};

export const LESSON_STATUS_TEXT: Record<LearningLesson["status"], string> = {
  LOCKED: "Bloqueada",
  AVAILABLE: "Disponible",
  IN_PROGRESS: "En progreso",
  COMPLETED: "Completada",
  GOLDEN: "Dorada",
  COMING_SOON: "Próximamente",
};

export const STATUS_STYLE: Record<LearningNode["status"], string> = {
  LOCKED: "bg-[#CBD5E1] text-[#45606A] border-slate-400",
  AVAILABLE: "bg-violet-600 text-white border-violet-800",
  IN_PROGRESS: "bg-violet-600 text-white border-violet-800",
  COMPLETED: "bg-emerald-500 text-white border-emerald-700",
  GOLDEN: "bg-[#FACC15] text-[#0E2A2F] border-yellow-600",
  COMING_SOON: "bg-[#CBD5E1] text-[#45606A] border-slate-400",
};

export function isOpenable(lesson: LearningLesson): boolean {
  return lesson.status !== "LOCKED";
}

import { useQuery } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { apiRequest } from "../../lib/api";
import type { components } from "../../lib/api-types";

export type Stats = components["schemas"]["StatsOut"];
export type AchievementStatus = components["schemas"]["AchievementStatusOut"];

export const statsKey = ["gamification", "stats"] as const;
export const achievementsKey = ["gamification", "achievements"] as const;

export function useStats() {
  return useQuery({
    queryKey: statsKey,
    queryFn: () => apiRequest<Stats>("GET", "/gamification/stats"),
  });
}

export function useAchievements() {
  return useQuery({
    queryKey: achievementsKey,
    queryFn: () => apiRequest<AchievementStatus[]>("GET", "/gamification/achievements"),
  });
}

export function buyStreakFreeze(): Promise<Stats> {
  return apiRequest<Stats>("POST", "/gamification/streak-freeze");
}

export function refillHearts(): Promise<Stats> {
  return apiRequest<Stats>("POST", "/gamification/hearts-refill");
}

/** «H:MM:SS» que falta hasta `target` (se actualiza cada segundo; 0:00:00 al llegar). */
export function useCountdown(target: string | null | undefined): string | null {
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    if (!target) return;
    const timer = window.setInterval(() => setNow(Date.now()), 1000);
    return () => window.clearInterval(timer);
  }, [target]);
  if (!target) return null;
  // Hacia arriba: «0:00:01» hasta que de verdad llega (no salta segundos).
  const total = Math.max(0, Math.ceil((Date.parse(target) - now) / 1000));
  const hours = Math.floor(total / 3600);
  const minutes = String(Math.floor((total % 3600) / 60)).padStart(2, "0");
  const seconds = String(total % 60).padStart(2, "0");
  return `${hours}:${minutes}:${seconds}`;
}

export function streakLabel(days: number): string {
  return `${days} ${days === 1 ? "día" : "días"}`;
}

import { useQuery } from "@tanstack/react-query";
import { apiRequest } from "../../lib/api";
import type { components } from "../../lib/api-types";

type Schemas = components["schemas"];
export type ProgressSummary = Schemas["ProgressSummaryOut"];
export type HistoryPage = Schemas["HistoryPageOut"];
export type Units = Schemas["UnitsOut"];

export const progressKey = ["progress"] as const;

export function useProgressSummary() {
  return useQuery({
    queryKey: [...progressKey, "summary"],
    queryFn: () => apiRequest<ProgressSummary>("GET", "/progress/summary"),
  });
}

export function useHistory(page: number) {
  return useQuery({
    queryKey: [...progressKey, "history", page],
    queryFn: () => apiRequest<HistoryPage>("GET", `/progress/history?page=${page}`),
  });
}

export function useUnits() {
  return useQuery({
    queryKey: [...progressKey, "units"],
    queryFn: () => apiRequest<Units>("GET", "/progress/units"),
  });
}

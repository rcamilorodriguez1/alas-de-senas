import { useQuery } from "@tanstack/react-query";
import { apiRequest } from "../../lib/api";
import type { components } from "../../lib/api-types";
import { useSessionStore } from "../../lib/session-store";

type Schemas = components["schemas"];
export type SignSearch = Schemas["SignSearchOut"];
export type SignCard = Schemas["SignCardOut"];
export type SignDetail = Schemas["SignDetailOut"];
export type DictionaryCategory = Schemas["CategoryOut"];

export const dictionaryKey = ["dictionary"] as const;
export const favoritesKey = [...dictionaryKey, "favorites"] as const;

export function useSignSearch(q: string, category: string, page: number) {
  const params = new URLSearchParams({ q, page: String(page) });
  if (category) params.set("category", category);
  return useQuery({
    queryKey: [...dictionaryKey, "search", q, category, page],
    queryFn: () =>
      apiRequest<SignSearch>("GET", `/dictionary/signs?${params.toString()}`),
    placeholderData: (previous) => previous,
  });
}

export function useCategories() {
  return useQuery({
    queryKey: [...dictionaryKey, "categories"],
    queryFn: () =>
      apiRequest<DictionaryCategory[]>("GET", "/dictionary/categories"),
  });
}

export function useSign(slug: string) {
  return useQuery({
    queryKey: [...dictionaryKey, "sign", slug],
    queryFn: () =>
      apiRequest<SignDetail>(
        "GET",
        `/dictionary/signs/${encodeURIComponent(slug)}`,
      ),
  });
}

export function useFavorites() {
  const authenticated = useSessionStore(
    (state) => state.status === "authenticated",
  );
  return useQuery({
    queryKey: favoritesKey,
    enabled: authenticated,
    queryFn: () => apiRequest<SignCard[]>("GET", "/dictionary/favorites"),
  });
}

export async function setFavorite(
  slug: string,
  favorite: boolean,
): Promise<void> {
  await apiRequest<undefined>(
    favorite ? "POST" : "DELETE",
    `/dictionary/favorites/${encodeURIComponent(slug)}`,
  );
}

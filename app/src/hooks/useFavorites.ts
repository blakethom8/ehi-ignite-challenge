import { useState, useCallback } from "react";

const STORAGE_KEY = "ehi-favorites";

function loadFavorites(): Set<string> {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return new Set();
    const parsed = JSON.parse(raw) as unknown;
    if (Array.isArray(parsed)) return new Set(parsed as string[]);
    return new Set();
  } catch {
    return new Set();
  }
}

function saveFavorites(favorites: Set<string>): void {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(Array.from(favorites)));
}

export function useFavorites() {
  const [favorites, setFavorites] = useState<Set<string>>(loadFavorites);

  const toggleFavorite = useCallback((id: string) => {
    setFavorites((prev) => {
      const next = new Set(prev);
      if (next.has(id)) {
        next.delete(id);
      } else {
        next.add(id);
      }
      saveFavorites(next);
      return next;
    });
  }, []);

  const isFavorite = useCallback(
    (id: string) => favorites.has(id),
    [favorites]
  );

  return { favorites, toggleFavorite, isFavorite };
}

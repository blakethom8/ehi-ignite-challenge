import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useAccessContext } from "../context/AccessContext";
import { migrateLegacyKey, storageNamespace } from "../storage";

const LEGACY_STORAGE_KEY = "ehi-favorites";

function loadFavorites(key: string): Set<string> {
  try {
    const raw = localStorage.getItem(key);
    if (!raw) return new Set();
    const parsed = JSON.parse(raw) as unknown;
    if (Array.isArray(parsed)) return new Set(parsed as string[]);
    return new Set();
  } catch {
    return new Set();
  }
}

function saveFavorites(key: string, favorites: Set<string>): void {
  try {
    localStorage.setItem(key, JSON.stringify(Array.from(favorites)));
  } catch {
    // best-effort
  }
}

export function useFavorites() {
  const { mode, user, activeDemoPatient, activePatientId, activeGuestRunId } = useAccessContext();
  const identity = useMemo<string | null>(() => {
    if (mode === "authenticated") return user?.id ?? null;
    if (mode === "demo") return activeDemoPatient?.id ?? activePatientId ?? null;
    if (mode === "guest") return activeGuestRunId ?? null;
    return null;
  }, [mode, user?.id, activeDemoPatient?.id, activePatientId, activeGuestRunId]);
  const storageKey = useMemo(
    () => storageNamespace(mode, identity, "favorites"),
    [mode, identity],
  );

  // One-shot legacy migration into the current namespace.
  const migratedKeyRef = useRef<string | null>(null);
  if (migratedKeyRef.current !== storageKey) {
    migrateLegacyKey(LEGACY_STORAGE_KEY, storageKey);
    migratedKeyRef.current = storageKey;
  }

  const [favorites, setFavorites] = useState<Set<string>>(() => loadFavorites(storageKey));

  // Re-hydrate when the namespace changes (mode/identity transition).
  useEffect(() => {
    setFavorites(loadFavorites(storageKey));
  }, [storageKey]);

  const toggleFavorite = useCallback((id: string) => {
    setFavorites((prev) => {
      const next = new Set(prev);
      if (next.has(id)) {
        next.delete(id);
      } else {
        next.add(id);
      }
      saveFavorites(storageKey, next);
      return next;
    });
  }, [storageKey]);

  const isFavorite = useCallback(
    (id: string) => favorites.has(id),
    [favorites]
  );

  return { favorites, toggleFavorite, isFavorite };
}

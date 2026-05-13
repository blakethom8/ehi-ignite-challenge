import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useAccessContext } from "../context/AccessContext";
import { migrateLegacyKey, storageNamespace } from "../storage";

const LEGACY_STORAGE_KEY = "ehi-favorites";

function loadFavorites(key: string, fallbackKey?: string): Set<string> {
  for (const candidateKey of [key, fallbackKey]) {
    if (!candidateKey) continue;
    try {
      const raw = localStorage.getItem(candidateKey);
      if (!raw) continue;
      const parsed = JSON.parse(raw) as unknown;
      if (Array.isArray(parsed)) return new Set(parsed as string[]);
      return new Set();
    } catch {
      continue;
    }
  }
  return new Set();
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
  const [favorites, setFavorites] = useState<Set<string>>(() => loadFavorites(storageKey, LEGACY_STORAGE_KEY));

  // Re-hydrate when the namespace changes (mode/identity transition).
  useEffect(() => {
    setFavorites(loadFavorites(storageKey, LEGACY_STORAGE_KEY));
  }, [storageKey]);

  useEffect(() => {
    if (migratedKeyRef.current === storageKey) return;
    migrateLegacyKey(LEGACY_STORAGE_KEY, storageKey);
    migratedKeyRef.current = storageKey;
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

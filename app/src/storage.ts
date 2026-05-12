// Centralized localStorage namespace helpers for the four-mode access model.
//
// Each mode owns a distinct prefix so cross-mode state does not leak. When a
// mode transition happens the previous namespace can be purged wholesale via
// `purgeWorkspaceState` / `purgeNamespacesByPrefix`.
//
// Namespace shape:
//   atlas:anon:<scope>
//   atlas:demo:<aliasOrSession>:<scope>
//   atlas:auth:<userId>:<scope>
//   atlas:guest:<runId>:<scope>

import type { AccessMode } from "./context/AccessContext";

export function storageNamespace(
  mode: AccessMode,
  userOrAlias: string | null,
  scope: string,
): string {
  switch (mode) {
    case "authenticated":
      return `atlas:auth:${userOrAlias ?? "anon"}:${scope}`;
    case "demo":
      return `atlas:demo:${userOrAlias ?? "anon"}:${scope}`;
    case "guest":
      return `atlas:guest:${userOrAlias ?? "anon"}:${scope}`;
    case "anonymous":
    default:
      return `atlas:anon:${scope}`;
  }
}

export function purgeNamespacesByPrefix(prefix: string): void {
  if (typeof window === "undefined") return;
  const keys = Object.keys(window.localStorage);
  for (const k of keys) {
    if (k.startsWith(prefix)) {
      window.localStorage.removeItem(k);
    }
  }
}

/**
 * Wipe cross-mode workspace state from localStorage.
 *
 * Called on AccessContext.clearAccess() and exitDemo() so leaving a mode
 * scrubs its persisted scratch (chat messages, agent settings, context
 * packages, favorites, etc.). Defaults to purging demo + guest namespaces
 * since those are the most likely sources of cross-mode bleed.
 *
 * Also removes the pre-Phase-2 legacy unscoped keys so existing users do not
 * carry stale settings forward unintentionally.
 */
export function purgeWorkspaceState(
  modesToPurge: AccessMode[] = ["demo", "guest"],
): void {
  if (typeof window === "undefined") return;
  for (const m of modesToPurge) {
    purgeNamespacesByPrefix(`atlas:${m}:`);
  }
  // Legacy unscoped Caspian session prefix (pre-Phase-2).
  purgeNamespacesByPrefix("atlas:caspian:");
  // Legacy unscoped chat/settings keys.
  try {
    window.localStorage.removeItem("ehi-agent-settings");
    window.localStorage.removeItem("ehi-provider-assistant-context-packages");
  } catch {
    // best-effort
  }
}

/**
 * One-shot migration from a legacy unscoped key to the current mode-scoped
 * key. Safe to call on every mount: it is idempotent and clears the legacy
 * key after copying.
 */
export function migrateLegacyKey(legacyKey: string, newKey: string): void {
  if (typeof window === "undefined") return;
  try {
    const legacy = window.localStorage.getItem(legacyKey);
    if (legacy !== null && window.localStorage.getItem(newKey) === null) {
      window.localStorage.setItem(newKey, legacy);
    }
    if (legacy !== null) {
      window.localStorage.removeItem(legacyKey);
    }
  } catch {
    // best-effort
  }
}

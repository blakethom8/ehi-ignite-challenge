import { useCallback, useEffect, useMemo, useState } from "react";
import { useAccessContext, type AccessMode } from "../../context/AccessContext";
import type { AgentSettings } from "../../context/ChatContext";
import { storageNamespace } from "../../storage";

const CASPIAN_DEFAULT_SETTINGS: AgentSettings = {
  model: "",
  mode: "anthropic",
  maxTokens: 1500,
};

function clampMaxTokens(value: unknown): number {
  const parsed = typeof value === "number" ? value : Number(value);
  if (!Number.isFinite(parsed)) return CASPIAN_DEFAULT_SETTINGS.maxTokens;
  return Math.min(Math.max(Math.round(parsed), 300), 4000);
}

function identityKey(
  mode: AccessMode,
  userId: string | null,
  activeDemoPatientId: string | null,
  activePatientId: string | null,
  activeGuestRunId: string | null,
): string | null {
  switch (mode) {
    case "authenticated":
      return userId ?? "anon";
    case "demo":
      return activeDemoPatientId ?? activePatientId ?? "anon";
    case "guest":
      return activeGuestRunId ?? "anon";
    case "anonymous":
    default:
      return null;
  }
}

function storageKeyFor(mode: AccessMode, identity: string | null): string | null {
  return storageNamespace(mode, identity, "caspian:agent-settings");
}

function readSettings(key: string | null): AgentSettings {
  if (!key) return CASPIAN_DEFAULT_SETTINGS;
  try {
    const raw = window.localStorage.getItem(key);
    if (!raw) return CASPIAN_DEFAULT_SETTINGS;
    const parsed = JSON.parse(raw);
    if (!parsed || typeof parsed !== "object") return CASPIAN_DEFAULT_SETTINGS;
    return {
      model: typeof parsed.model === "string" ? parsed.model : "",
      mode: typeof parsed.mode === "string" ? parsed.mode : CASPIAN_DEFAULT_SETTINGS.mode,
      maxTokens: clampMaxTokens(parsed.maxTokens),
    };
  } catch {
    return CASPIAN_DEFAULT_SETTINGS;
  }
}

export function useCaspianAgentSettings(): {
  settings: AgentSettings;
  setSettings: (next: AgentSettings) => void;
} {
  const { mode, user, activeDemoPatient, activePatientId, activeGuestRunId } = useAccessContext();
  const identity = identityKey(
    mode,
    user?.id ?? null,
    activeDemoPatient?.id ?? null,
    activePatientId,
    activeGuestRunId,
  );
  const key = useMemo(() => storageKeyFor(mode, identity), [mode, identity]);
  const [settings, setSettingsState] = useState<AgentSettings>(() => readSettings(key));

  useEffect(() => {
    setSettingsState(readSettings(key));
  }, [key]);

  const setSettings = useCallback(
    (next: AgentSettings) => {
      const normalized: AgentSettings = {
        model: next.model ?? "",
        mode: next.mode ?? "",
        maxTokens: clampMaxTokens(next.maxTokens),
      };
      setSettingsState(normalized);
      if (!key) return;
      try {
        window.localStorage.setItem(key, JSON.stringify(normalized));
      } catch {
        // Best-effort persistence only.
      }
    },
    [key],
  );

  return { settings, setSettings };
}

export const CASPIAN_AGENT_DEFAULTS = CASPIAN_DEFAULT_SETTINGS;

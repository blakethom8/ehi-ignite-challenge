import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from "react";
import { api } from "../api/client";
import { mockPatients } from "../api/mockData";
import { purgeNamespacesByPrefix, purgeWorkspaceState } from "../storage";
import type {
  AuthSessionResponse,
  AuthUser,
  Capabilities,
  DemoPatientOption,
} from "../types";

export type AccessMode = "anonymous" | "demo" | "authenticated" | "guest";

type AccessState = {
  mode: AccessMode;
  user: AuthUser | null;
  activePatientId: string | null;
  activePatientName: string | null;
  activeDemoPatient: DemoPatientOption | null;
  activeGuestRunId: string | null;
  expiresAt: string | null;
  availableDemoPatients: DemoPatientOption[];
  capabilities: Capabilities | null;
};

type AccessContextValue = AccessState & {
  isLoading: boolean;
  isUnlocked: boolean;
  isDemo: boolean;
  isGuest: boolean;
  signIn: (email: string, password: string) => Promise<void>;
  signUp: (email: string, password: string, displayName: string) => Promise<void>;
  enterDemoPatient: (patientId: string) => Promise<void>;
  exitDemo: () => Promise<void>;
  enterGuestMode: (runId: string) => void;
  exitGuestMode: () => void;
  setActivePatient: (patientId: string | null) => Promise<void>;
  clearAccess: () => Promise<void>;
  refreshSession: () => Promise<void>;
  refreshCapabilities: () => Promise<void>;
  updateDisplayName: (displayName: string) => Promise<void>;
  changePassword: (currentPassword: string, newPassword: string) => Promise<void>;
  deleteAccount: () => Promise<void>;
};

const AccessContext = createContext<AccessContextValue | null>(null);

const DEFAULT_STATE: AccessState = {
  mode: "anonymous",
  user: null,
  activePatientId: null,
  activePatientName: null,
  activeDemoPatient: null,
  activeGuestRunId: null,
  expiresAt: null,
  availableDemoPatients: [],
  capabilities: null,
};

const STORAGE_KEY = "atlas:access";
const useMockData = import.meta.env.VITE_USE_MOCK_DATA === "true";

function mockDemoOptions(): DemoPatientOption[] {
  return mockPatients.map((patient, index) => ({
    id: patient.id,
    name: patient.name,
    description: "Prepared synthetic demo chart for the public Atlas experience.",
    short_journey: [
      "Pre-op chart with medication safety and surgical-risk signals.",
      "Referral-style chart for trial-matching and specialty review.",
      "Longitudinal medication-burden chart with access and continuity questions.",
    ][index] ?? "Prepared synthetic demo chart.",
    metadata: {
      care_setting: ["Pre-op review", "Specialty referral", "Care coordination"][index] ?? "Prepared demo",
      clinical_focus: ["Surgical safety", "Trial matching", "Medication access"][index] ?? "Chart review",
      complexity: ["high", "medium", "medium"][index] ?? "medium",
      tags: [
        ["FHIR-only", "Risk flags"],
        ["FHIR-only", "Referral"],
        ["FHIR-only", "Polypharmacy"],
      ][index] ?? ["FHIR-only"],
    },
  }));
}

function mockSessionFromStorage(): Omit<AccessState, "capabilities"> {
  if (typeof window === "undefined") {
    return { ...DEFAULT_STATE, availableDemoPatients: mockDemoOptions() };
  }
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    const parsed = raw ? (JSON.parse(raw) as { mode?: string; activePatientId?: string | null }) : {};
    const mode: AccessMode =
      parsed.mode === "demo" || parsed.mode === "authenticated" ? (parsed.mode as AccessMode) : "anonymous";
    const patientId = typeof parsed.activePatientId === "string" ? parsed.activePatientId : null;
    const activePatientName = mockPatients.find((patient) => patient.id === patientId)?.name ?? null;
    return {
      mode,
      user: mode === "authenticated"
        ? {
            id: "mock-user",
            email: "account@example.com",
            display_name: "Atlas Account",
            role: "coordinator",
          }
        : null,
      activePatientId: patientId,
      activePatientName,
      activeDemoPatient: mockDemoOptions().find((patient) => patient.id === patientId) ?? null,
      activeGuestRunId: null,
      expiresAt: null,
      availableDemoPatients: mockDemoOptions(),
    };
  } catch {
    return { ...DEFAULT_STATE, availableDemoPatients: mockDemoOptions() };
  }
}

function writeMockSession(mode: AccessMode, activePatientId: string | null) {
  if (typeof window === "undefined") return;
  window.localStorage.setItem(STORAGE_KEY, JSON.stringify({ mode, activePatientId }));
}

function mapSession(session: AuthSessionResponse): Omit<AccessState, "capabilities" | "activeGuestRunId"> {
  return {
    mode: session.mode,
    user: session.user,
    activePatientId: session.active_patient_id,
    activePatientName: session.active_patient_name,
    activeDemoPatient: session.active_demo_patient ?? null,
    expiresAt: session.expires_at,
    availableDemoPatients: session.available_demo_patients,
  };
}

export function AccessProvider({ children }: { children: ReactNode }) {
  const [state, setState] = useState<AccessState>(DEFAULT_STATE);
  const [isLoading, setIsLoading] = useState(true);
  // Track the most recent mode we've fetched capabilities for so we don't
  // fire redundant requests on unrelated state updates.
  const lastCapabilitiesModeRef = useRef<AccessMode | null>(null);

  const applySession = useCallback((session: AuthSessionResponse) => {
    setState((prev) => ({
      ...prev,
      ...mapSession(session),
      // Returning to a real session always exits guest mode.
      activeGuestRunId: null,
    }));
  }, []);

  const refreshCapabilities = useCallback(async () => {
    try {
      const caps = await api.getCapabilities();
      setState((prev) => ({ ...prev, capabilities: caps }));
    } catch {
      // Leave capabilities as-is; useCapabilities() falls back to anonymous.
    }
  }, []);

  const refreshSession = useCallback(async () => {
    setIsLoading(true);
    try {
      applySession(await api.getAuthSession());
    } catch {
      const fallback = useMockData ? mockSessionFromStorage() : DEFAULT_STATE;
      setState((prev) => ({ ...prev, ...fallback, capabilities: prev.capabilities }));
    } finally {
      setIsLoading(false);
    }
  }, [applySession]);

  useEffect(() => {
    void refreshSession();
  }, [refreshSession]);

  // Fetch capabilities on every mode transition (and once on mount).
  useEffect(() => {
    if (lastCapabilitiesModeRef.current === state.mode && state.capabilities !== null) {
      return;
    }
    lastCapabilitiesModeRef.current = state.mode;
    void refreshCapabilities();
  }, [state.mode, state.capabilities, refreshCapabilities]);

  const enterGuestMode = useCallback((runId: string) => {
    setState((prev) => ({
      ...prev,
      mode: "guest",
      user: null,
      activePatientId: null,
      activePatientName: null,
      activeDemoPatient: null,
      activeGuestRunId: runId,
    }));
  }, []);

  const exitGuestMode = useCallback(() => {
    setState((prev) => ({
      ...prev,
      mode: "anonymous",
      activeGuestRunId: null,
    }));
    // Guest scratch (if any) lives under atlas:guest:; clear it explicitly.
    purgeNamespacesByPrefix("atlas:guest:");
  }, []);

  const value = useMemo<AccessContextValue>(
    () => ({
      ...state,
      isLoading,
      isUnlocked: state.mode !== "anonymous",
      isDemo: state.mode === "demo",
      isGuest: state.mode === "guest",
      signIn: async (email: string, password: string) => {
        if (useMockData) {
          writeMockSession("authenticated", null);
          const next = mockSessionFromStorage();
          setState((prev) => ({ ...prev, ...next, activeGuestRunId: null }));
          return;
        }
        applySession(await api.login(email, password));
      },
      signUp: async (email: string, password: string, displayName: string) => {
        if (useMockData) {
          writeMockSession("authenticated", null);
          const next = mockSessionFromStorage();
          setState((prev) => ({ ...prev, ...next, activeGuestRunId: null }));
          return;
        }
        applySession(await api.signup(email, password, displayName));
      },
      enterDemoPatient: async (patientId: string) => {
        if (useMockData) {
          writeMockSession("demo", patientId);
          const next = mockSessionFromStorage();
          setState((prev) => ({ ...prev, ...next, activeGuestRunId: null }));
          return;
        }
        applySession(await api.enterDemo(patientId));
      },
      exitDemo: async () => {
        // Clear demo-scoped local state before flipping mode so we don't leak
        // chat/messages/agent settings into the next session.
        purgeWorkspaceState(["demo"]);
        if (useMockData) {
          writeMockSession("anonymous", null);
          const next = mockSessionFromStorage();
          setState((prev) => ({ ...prev, ...next, activeGuestRunId: null }));
          return;
        }
        applySession(await api.exitDemo());
      },
      enterGuestMode,
      exitGuestMode,
      setActivePatient: async (patientId: string | null) => {
        if (useMockData) {
          writeMockSession(state.mode === "guest" ? "anonymous" : state.mode, patientId);
          const next = mockSessionFromStorage();
          setState((prev) => ({ ...prev, ...next, activeGuestRunId: null }));
          return;
        }
        applySession(await api.selectActivePatient(patientId));
      },
      clearAccess: async () => {
        // Wipe demo + guest cross-mode scratch on sign-out.
        purgeWorkspaceState(["demo", "guest"]);
        if (useMockData) {
          writeMockSession("anonymous", null);
          const next = mockSessionFromStorage();
          setState((prev) => ({ ...prev, ...next, activeGuestRunId: null }));
          return;
        }
        applySession(await api.logout());
      },
      updateDisplayName: async (displayName: string) => {
        if (useMockData) {
          setState((prev) => ({
            ...prev,
            user: prev.user ? { ...prev.user, display_name: displayName } : prev.user,
          }));
          return;
        }
        applySession(await api.updateAccountProfile(displayName));
      },
      changePassword: async (currentPassword: string, newPassword: string) => {
        if (useMockData) return;
        await api.changeAccountPassword(currentPassword, newPassword);
      },
      deleteAccount: async () => {
        purgeWorkspaceState(["demo", "guest"]);
        if (useMockData) {
          writeMockSession("anonymous", null);
          const next = mockSessionFromStorage();
          setState((prev) => ({ ...prev, ...next, activeGuestRunId: null }));
          return;
        }
        applySession(await api.deleteAccount());
      },
      refreshSession,
      refreshCapabilities,
    }),
    [isLoading, state, applySession, enterGuestMode, exitGuestMode, refreshSession, refreshCapabilities],
  );

  return <AccessContext.Provider value={value}>{children}</AccessContext.Provider>;
}

// eslint-disable-next-line react-refresh/only-export-components
export function useAccessContext() {
  const context = useContext(AccessContext);
  if (!context) {
    throw new Error("useAccessContext must be used within AccessProvider");
  }
  return context;
}

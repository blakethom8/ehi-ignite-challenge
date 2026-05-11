import {
  createContext,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import { api } from "../api/client";
import { mockPatients } from "../api/mockData";
import type { AuthSessionResponse, AuthUser, DemoPatientOption } from "../types";

export type AccessMode = "anonymous" | "demo" | "authenticated";

type AccessState = {
  mode: AccessMode;
  user: AuthUser | null;
  activePatientId: string | null;
  activePatientName: string | null;
  expiresAt: string | null;
  availableDemoPatients: DemoPatientOption[];
};

type AccessContextValue = AccessState & {
  isLoading: boolean;
  isUnlocked: boolean;
  isDemo: boolean;
  signIn: (email: string, password: string) => Promise<void>;
  enterDemoPatient: (patientId: string) => Promise<void>;
  setActivePatient: (patientId: string | null) => Promise<void>;
  clearAccess: () => Promise<void>;
  refreshSession: () => Promise<void>;
};

const AccessContext = createContext<AccessContextValue | null>(null);

const DEFAULT_STATE: AccessState = {
  mode: "anonymous",
  user: null,
  activePatientId: null,
  activePatientName: null,
  expiresAt: null,
  availableDemoPatients: [],
};

const STORAGE_KEY = "atlas:access";
const useMockData = import.meta.env.VITE_USE_MOCK_DATA === "true";

function mockDemoOptions(): DemoPatientOption[] {
  return mockPatients.map((patient) => ({
    id: patient.id,
    name: patient.name,
    description: "Frontend mock-mode demo patient.",
  }));
}

function mockSessionFromStorage(): AccessState {
  if (typeof window === "undefined") {
    return { ...DEFAULT_STATE, availableDemoPatients: mockDemoOptions() };
  }
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    const parsed = raw ? (JSON.parse(raw) as { mode?: string; activePatientId?: string | null }) : {};
    const mode = parsed.mode === "demo" || parsed.mode === "authenticated" ? parsed.mode : "anonymous";
    const patientId = typeof parsed.activePatientId === "string" ? parsed.activePatientId : null;
    const activePatientName = mockPatients.find((patient) => patient.id === patientId)?.name ?? null;
    return {
      mode,
      user: mode === "authenticated"
        ? {
            id: "mock-user",
            email: "clinician@atlas.local",
            display_name: "Atlas Clinician",
            role: "clinician",
          }
        : null,
      activePatientId: patientId,
      activePatientName,
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

function mapSession(session: AuthSessionResponse): AccessState {
  return {
    mode: session.mode,
    user: session.user,
    activePatientId: session.active_patient_id,
    activePatientName: session.active_patient_name,
    expiresAt: session.expires_at,
    availableDemoPatients: session.available_demo_patients,
  };
}

export function AccessProvider({ children }: { children: ReactNode }) {
  const [state, setState] = useState<AccessState>(DEFAULT_STATE);
  const [isLoading, setIsLoading] = useState(true);

  const applySession = (session: AuthSessionResponse) => {
    setState(mapSession(session));
  };

  const refreshSession = async () => {
    setIsLoading(true);
    try {
      applySession(await api.getAuthSession());
    } catch {
      setState(useMockData ? mockSessionFromStorage() : DEFAULT_STATE);
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    void refreshSession();
  }, []);

  const value = useMemo<AccessContextValue>(
    () => ({
      ...state,
      isLoading,
      isUnlocked: state.mode !== "anonymous",
      isDemo: state.mode === "demo",
      signIn: async (email: string, password: string) => {
        if (useMockData) {
          writeMockSession("authenticated", null);
          setState(mockSessionFromStorage());
          return;
        }
        applySession(await api.login(email, password));
      },
      enterDemoPatient: async (patientId: string) => {
        if (useMockData) {
          writeMockSession("demo", patientId);
          setState(mockSessionFromStorage());
          return;
        }
        applySession(await api.enterDemo(patientId));
      },
      setActivePatient: async (patientId: string | null) => {
        if (useMockData) {
          writeMockSession(state.mode, patientId);
          setState(mockSessionFromStorage());
          return;
        }
        applySession(await api.selectActivePatient(patientId));
      },
      clearAccess: async () => {
        if (useMockData) {
          writeMockSession("anonymous", null);
          setState(mockSessionFromStorage());
          return;
        }
        applySession(await api.logout());
      },
      refreshSession,
    }),
    [isLoading, state],
  );

  return <AccessContext.Provider value={value}>{children}</AccessContext.Provider>;
}

export function useAccessContext() {
  const context = useContext(AccessContext);
  if (!context) {
    throw new Error("useAccessContext must be used within AccessProvider");
  }
  return context;
}

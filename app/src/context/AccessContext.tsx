import {
  createContext,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import { mockPatients } from "../api/mockData";

export type AccessMode = "locked" | "demo" | "authenticated";

type AccessState = {
  mode: AccessMode;
  activePatientId: string | null;
};

type AccessContextValue = AccessState & {
  isUnlocked: boolean;
  isDemo: boolean;
  enterDemoPatient: (patientId: string) => void;
  setActivePatient: (patientId: string | null, mode?: AccessMode) => void;
  clearAccess: () => void;
};

const STORAGE_KEY = "atlas:access";
const AccessContext = createContext<AccessContextValue | null>(null);

const DEFAULT_STATE: AccessState = {
  mode: "locked",
  activePatientId: null,
};

function isKnownDemoPatient(patientId: string | null): boolean {
  return Boolean(patientId && mockPatients.some((patient) => patient.id === patientId));
}

function normalizeState(raw: unknown): AccessState {
  if (!raw || typeof raw !== "object") return DEFAULT_STATE;
  const candidate = raw as Partial<AccessState>;
  const patientId = typeof candidate.activePatientId === "string" ? candidate.activePatientId : null;
  const mode =
    candidate.mode === "demo" || candidate.mode === "authenticated" || candidate.mode === "locked"
      ? candidate.mode
      : "locked";

  if (mode === "demo" && !isKnownDemoPatient(patientId)) {
    return DEFAULT_STATE;
  }

  if (mode === "locked") {
    return DEFAULT_STATE;
  }

  return {
    mode,
    activePatientId: patientId,
  };
}

export function AccessProvider({ children }: { children: ReactNode }) {
  const [state, setState] = useState<AccessState>(() => {
    if (typeof window === "undefined") return DEFAULT_STATE;
    try {
      const raw = window.localStorage.getItem(STORAGE_KEY);
      return raw ? normalizeState(JSON.parse(raw)) : DEFAULT_STATE;
    } catch {
      return DEFAULT_STATE;
    }
  });

  useEffect(() => {
    if (typeof window === "undefined") return;
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify(state));
  }, [state]);

  const value = useMemo<AccessContextValue>(
    () => ({
      ...state,
      isUnlocked: state.mode !== "locked",
      isDemo: state.mode === "demo",
      enterDemoPatient: (patientId: string) => {
        if (!isKnownDemoPatient(patientId)) return;
        setState({ mode: "demo", activePatientId: patientId });
      },
      setActivePatient: (patientId: string | null, mode?: AccessMode) => {
        if (!patientId) {
          setState(DEFAULT_STATE);
          return;
        }
        if (mode === "demo" || isKnownDemoPatient(patientId)) {
          setState({ mode: "demo", activePatientId: patientId });
          return;
        }
        setState({ mode: mode === "locked" ? "locked" : "authenticated", activePatientId: patientId });
      },
      clearAccess: () => setState(DEFAULT_STATE),
    }),
    [state],
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

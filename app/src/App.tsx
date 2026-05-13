import { Suspense, lazy, useEffect, useState, type ReactNode } from "react";
import { BrowserRouter, Navigate, Route, Routes, useLocation, useNavigate } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { AppErrorBoundary } from "./components/AppErrorBoundary";
import { AppShell } from "./components/atlas/AppShell";
import { ChatProvider } from "./context/ChatContext";
import { AccessProvider, useAccessContext } from "./context/AccessContext";
import { ChatWidget } from "./components/ChatWidget";
import { useCapabilities } from "./hooks/useCapabilities";
import { AccountAccessPage } from "./pages/AccountAccess";
import { AdminUsersPage } from "./pages/Admin/Users";
import { AdminUserDetailPage } from "./pages/Admin/UserDetail";
import { AdminSessionsPage } from "./pages/Admin/Sessions";
import { AccountSettingsPage } from "./pages/AccountSettings";
import { DemoPatientSelection } from "./pages/DemoPatientSelection";
import { Landing } from "./pages/Landing";
import { GuestHarmonization } from "./pages/GuestHarmonization";
import { PlatformArchitecture } from "./pages/PlatformArchitecture";
import { PatientRecordPool } from "./pages/PatientRecordPool";
import { PatientRecordLayout } from "./pages/PatientRecord/PatientRecordLayout";
import { FhirChartsLayout } from "./pages/FhirCharts/FhirChartsLayout";
import { supportsPatientContext } from "./routing";
import { atlasShellRoutes, hasPatientScopedShellPath, isFullscreenWorkspacePath } from "./routes/atlasShell";
import { legacyRedirectRoutes } from "./routes/legacyRedirects";
import { resolveInvalidPatientRedirect, resolveSessionHomePath } from "./sessionRouting";
import type { AuthMode } from "./types";

// Demo-alias patient ids are the synthetic charts available to the
// anonymous + demo modes (see app/src/demoCatalog.ts). They never resolve
// against a real authenticated workspace, so we strip them when mode flips.
function isDemoAliasPatientId(patientId: string | null | undefined): boolean {
  return typeof patientId === "string" && patientId.startsWith("demo-");
}

function PageFallback() {
  return (
    <div className="flex min-h-[360px] items-center justify-center p-8">
      <div
        className="h-10 w-10 rounded-full border-4 border-[var(--line-1)]"
        style={{ borderTopColor: "var(--action)" }}
      />
    </div>
  );
}

function FullscreenPageFallback() {
  return (
    <div
      className="flex h-screen items-center justify-center p-8"
      style={{ background: "var(--bg-app)" }}
    >
      <div
        className="h-10 w-10 rounded-full border-4 border-[var(--line-1)]"
        style={{ borderTopColor: "var(--action)" }}
      />
    </div>
  );
}

// Atlas docs
const UsingAtlasRoutes = lazy(() => import("./pages/UsingAtlas/routes").then((module) => ({
  default: module.UsingAtlasRoutes,
})));

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      retry: 1,
      refetchOnWindowFocus: false,
    },
  },
});

function AppShellRoute({
  element,
  fullBleed,
}: {
  element: ReactNode;
  fullBleed?: boolean;
}) {
  const location = useLocation();
  const navigate = useNavigate();
  const { activePatientId, isLoading, mode, setActivePatient } = useAccessContext();
  const capabilities = useCapabilities();
  const routeKey = `${location.pathname}${location.search}`;
  const requestedPatientId = new URLSearchParams(location.search).get("patient");
  const canCarryPatientContext = supportsPatientContext(capabilities.mode);
  const stripPatient = shouldStripPatient(
    location.pathname,
    location.search,
    isLoading,
    capabilities.mode,
    requestedPatientId,
  );
  const hydratePatient = shouldHydratePatient(
    location.pathname,
    location.search,
    capabilities.mode,
    activePatientId,
  );
  const isPatientRecordRoute = location.pathname.startsWith("/patient-record");
  const isFhirChartsRoute = location.pathname.startsWith("/fhir-charts");
  const [isSyncingPatient, setIsSyncingPatient] = useState(false);

  useEffect(() => {
    if (isLoading || !canCarryPatientContext) return;
    if (!requestedPatientId || requestedPatientId === activePatientId) {
      setIsSyncingPatient(false);
      return;
    }
    // Guard against the race where signing in while on /caspian?patient=demo-…
    // tries to apply a demo alias to an authenticated session. Drop the param
    // and route to the authenticated home instead.
    if (mode === "authenticated" && isDemoAliasPatientId(requestedPatientId)) {
      setIsSyncingPatient(false);
      navigate(resolveSessionHomePath("authenticated", null), { replace: true });
      return;
    }
    let cancelled = false;
    setIsSyncingPatient(true);
    void setActivePatient(requestedPatientId)
      .catch(() => {
        if (cancelled) return;
        navigate(resolveInvalidPatientRedirect(mode), { replace: true });
      })
      .finally(() => {
        if (!cancelled) {
          setIsSyncingPatient(false);
        }
      });
    return () => {
      cancelled = true;
    };
  }, [activePatientId, canCarryPatientContext, isLoading, mode, navigate, requestedPatientId, setActivePatient]);

  useEffect(() => {
    if (fullBleed || !hydratePatient) return;
    const params = new URLSearchParams(location.search);
    params.set("patient", activePatientId as string);
    navigate({ pathname: location.pathname, search: `?${params.toString()}` }, { replace: true });
  }, [activePatientId, fullBleed, hydratePatient, location.pathname, location.search, navigate]);

  if (isLoading) {
    return fullBleed ? <FullscreenPageFallback /> : <PageFallback />;
  }

  if (isSyncingPatient) {
    return fullBleed ? <FullscreenPageFallback /> : <PageFallback />;
  }

  if (stripPatient) {
    return <Navigate replace to={location.pathname} />;
  }

  if (fullBleed) {
    if (hydratePatient) {
      const params = new URLSearchParams(location.search);
      params.set("patient", activePatientId as string);
      return <Navigate replace to={`${location.pathname}?${params.toString()}`} />;
    }
    return (
      <Suspense key={routeKey} fallback={<FullscreenPageFallback />}>
        {element}
      </Suspense>
    );
  }

  const routeContent = (
    <Suspense key={routeKey} fallback={<PageFallback />}>
      {element}
    </Suspense>
  );
  return (
    <AppShell>
      {isPatientRecordRoute ? (
        <PatientRecordLayout key={routeKey}>{routeContent}</PatientRecordLayout>
      ) : isFhirChartsRoute ? (
        <FhirChartsLayout key={routeKey}>{routeContent}</FhirChartsLayout>
      ) : (
        routeContent
      )}
    </AppShell>
  );
}

function AppShellRoutes() {
  const location = useLocation();
  const isFullscreenWorkspace = isFullscreenWorkspacePath(location.pathname);

  return (
    <>
      <Routes>
        <Route path="/" element={<Landing />} />
        <Route path="/demo" element={<DemoPatientSelection />} />
        <Route path="/account" element={<AccountAccessPage />} />
        <Route path="/account/settings" element={<AccountSettingsPage />} />
        <Route path="/admin" element={<Navigate to="/admin/users" replace />} />
        <Route path="/admin/users" element={<AdminUsersPage />} />
        <Route path="/admin/users/:userId" element={<AdminUserDetailPage />} />
        <Route path="/admin/sessions" element={<AdminSessionsPage />} />
        <Route path="/guest-harmonization" element={<GuestHarmonization />} />
        <Route path="/architecture" element={<PlatformArchitecture />} />
        <Route path="/records-pool" element={<PatientRecordPool />} />
        <Route path="/guided-tour" element={<Navigate to="/using-atlas" replace />} />
        <Route
          path="/using-atlas/*"
          element={<Suspense fallback={<PageFallback />}><UsingAtlasRoutes /></Suspense>}
        />
        {/* Legacy redirects — see .claude/handoff/atlas/README.md §Routing */}
        {legacyRedirectRoutes.map((route) => (
          <Route key={route.path} path={route.path} element={route.element} />
        ))}
        {/* Atlas IA routes — the five top-level modules */}
        {atlasShellRoutes.map((r) => (
          <Route
            key={r.path}
            path={r.path}
            element={<AppShellRoute element={r.element} fullBleed={r.fullBleed} />}
          />
        ))}
      </Routes>
      {!isFullscreenWorkspace && <ChatWidget />}
    </>
  );
}

function shouldHydratePatient(
  pathname: string,
  search: string,
  mode: AuthMode,
  activePatientId: string | null,
): boolean {
  if (!supportsPatientContext(mode) || !activePatientId) return false;
  if (!hasPatientScopedShellPath(pathname)) {
    return false;
  }
  const params = new URLSearchParams(search);
  return !params.has("patient");
}

function shouldStripPatient(
  pathname: string,
  search: string,
  isLoading: boolean,
  mode: AuthMode,
  requestedPatientId: string | null,
): boolean {
  if (isLoading) return false;
  if (!hasPatientScopedShellPath(pathname)) {
    return false;
  }
  const params = new URLSearchParams(search);
  if (!params.has("patient")) return false;
  // Modes without a real patient workspace never carry a patient param.
  if (!supportsPatientContext(mode)) return true;
  // Authenticated mode: strip demo aliases that survived a sign-in transition.
  if (mode === "authenticated" && isDemoAliasPatientId(requestedPatientId)) {
    return true;
  }
  return false;
}

export default function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <AppErrorBoundary>
          <AccessProvider>
            <ChatProvider>
              <AppShellRoutes />
            </ChatProvider>
          </AccessProvider>
        </AppErrorBoundary>
      </BrowserRouter>
    </QueryClientProvider>
  );
}

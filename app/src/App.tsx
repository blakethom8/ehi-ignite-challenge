import { Suspense, lazy, useEffect, type ComponentType } from "react";
import { BrowserRouter, Navigate, Route, Routes, useLocation, useNavigate, useParams } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { AppErrorBoundary } from "./components/AppErrorBoundary";
import { AppShell } from "./components/atlas/AppShell";
import { ChatProvider } from "./context/ChatContext";
import { AccessProvider, useAccessContext } from "./context/AccessContext";
import { ChatWidget } from "./components/ChatWidget";
import { AccountAccessPage } from "./pages/AccountAccess";
import { Landing } from "./pages/Landing";
import { GuestHarmonization } from "./pages/GuestHarmonization";
import { PlatformArchitecture } from "./pages/PlatformArchitecture";
import { PatientRecordPool } from "./pages/PatientRecordPool";
import { PatientRecordLayout } from "./pages/PatientRecord/PatientRecordLayout";
import { FhirChartsLayout } from "./pages/FhirCharts/FhirChartsLayout";
import { buildGroundTruthReviewPath } from "./routing";

function lazyNamed<TModule extends Record<string, unknown>>(
  loader: () => Promise<TModule>,
  exportName: keyof TModule,
) {
  return lazy(async () => {
    const module = await loader();
    return { default: module[exportName] as ComponentType };
  });
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

// Atlas shell pages (the five top-level modules)
const CaspianWorkspace = lazyNamed(() => import("./pages/Caspian/Workspace"), "CaspianWorkspace");
const PluginWorkspace = lazyNamed(() => import("./pages/Plugins/Workspace"), "PluginWorkspace");
const PluginsIndex = lazyNamed(() => import("./pages/Plugins/Index"), "PluginsIndex");

// Patient Record module — source-of-truth chart layer (absorbs Data Aggregator)
const PatientRecordOverview = lazyNamed(() => import("./pages/PatientRecord/Overview"), "PatientRecordOverview");
const PatientRecordHarmonize = lazyNamed(() => import("./pages/PatientRecord/Harmonize"), "HarmonizeView");
const PatientRecordMethodology = lazyNamed(() => import("./pages/PatientRecord/Methodology"), "AggregationMethodology");
const PatientRecordContext = lazyNamed(() => import("./pages/PatientRecord/Context"), "PatientContext");
const PatientRecordPublish = lazyNamed(() => import("./pages/PatientRecord/aggregator/PublishReadinessPage"), "PublishReadinessPage");
const PatientRecordSources = lazyNamed(() => import("./pages/PatientRecord/aggregator/SourceIntakePage"), "SourceIntakePage");
const PatientRecordWorkspaces = lazyNamed(() => import("./pages/PatientRecord/aggregator/WorkspaceLibraryPage"), "WorkspaceLibraryPage");
// FHIR Charts module — FHIR resource browser (former Explorer)
const FhirChartsOverview = lazyNamed(() => import("./pages/FhirCharts/Overview"), "FhirChartsOverview");
const FhirChartsTimeline = lazyNamed(() => import("./pages/FhirCharts/Timeline"), "FhirChartsTimeline");
const FhirChartsCorpus = lazyNamed(() => import("./pages/FhirCharts/Corpus"), "FhirChartsCorpus");
const FhirChartsSafety = lazyNamed(() => import("./pages/FhirCharts/Safety"), "FhirChartsSafety");
const FhirChartsImmunizations = lazyNamed(() => import("./pages/FhirCharts/Immunizations"), "FhirChartsImmunizations");
const FhirChartsConditions = lazyNamed(() => import("./pages/FhirCharts/Conditions"), "FhirChartsConditions");
const FhirChartsProcedures = lazyNamed(() => import("./pages/FhirCharts/Procedures"), "FhirChartsProcedures");
const FhirChartsClearance = lazyNamed(() => import("./pages/FhirCharts/Clearance"), "FhirChartsClearance");
const FhirChartsAnesthesia = lazyNamed(() => import("./pages/FhirCharts/Anesthesia"), "FhirChartsAnesthesia");
const FhirChartsDistributions = lazyNamed(() => import("./pages/FhirCharts/Distributions"), "FhirChartsDistributions");
const FhirChartsInteractions = lazyNamed(() => import("./pages/FhirCharts/Interactions"), "FhirChartsInteractions");
const FhirChartsAssistant = lazyNamed(() => import("./pages/FhirCharts/Assistant"), "FhirChartsAssistant");
const FhirChartsCareJourney = lazyNamed(() => import("./pages/FhirCharts/CareJourney"), "FhirChartsCareJourney");
const FhirChartsPatientData = lazyNamed(() => import("./pages/FhirCharts/PatientData"), "FhirChartsPatientData");
const FhirChartsHistory = lazyNamed(() => import("./pages/FhirCharts/History"), "FhirChartsHistory");
const FhirChartsLabs = lazyNamed(() => import("./pages/FhirCharts/Labs"), "FhirChartsLabs");
const FhirChartsJourney = lazyNamed(() => import("./pages/FhirCharts/Journey"), "PatientJourney");

// Internal Tools — runbooks, evals, labs, reviews (routed via /learn/*)
const InternalToolsOverview = lazyNamed(() => import("./pages/InternalTools/Overview"), "InternalToolsOverview");
const InternalToolsDefinitions = lazyNamed(() => import("./pages/InternalTools/Definitions"), "InternalToolsDefinitions");
const InternalToolsCoverage = lazyNamed(() => import("./pages/InternalTools/Coverage"), "InternalToolsCoverage");
const InternalToolsFhirPrimer = lazyNamed(() => import("./pages/InternalTools/FhirPrimer"), "InternalToolsFhirPrimer");
const InternalToolsQaEvalLab = lazyNamed(() => import("./pages/InternalTools/QaEvalLab"), "QaEvalLab");
const InternalToolsCcdaLab = lazyNamed(() => import("./pages/InternalTools/CcdaLab"), "CcdaPipelineLab");
const InternalToolsPipelineLab = lazyNamed(() => import("./pages/InternalTools/PipelineLab"), "PipelineLab");
const InternalToolsGroundTruth = lazyNamed(() => import("./pages/InternalTools/GroundTruthReview"), "GroundTruthReview");
const InternalToolsLabExplainer = lazyNamed(() => import("./pages/InternalTools/LabExplainer"), "LabExplainer");
const InternalToolsDataSharing = lazyNamed(() => import("./pages/InternalTools/DataSharing"), "DataSharing");
const InternalToolsTrialFinder = lazyNamed(() => import("./pages/InternalTools/skills/TrialFinder"), "TrialFinder");
const InternalToolsPatientMemory = lazyNamed(() => import("./pages/InternalTools/skills/PatientMemory"), "PatientMemoryView");

// Atlas docs
const UsingAtlasRoutes = lazyNamed(() => import("./pages/UsingAtlas/routes"), "UsingAtlasRoutes");

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      retry: 1,
      refetchOnWindowFocus: false,
    },
  },
});

type ShellRoute = {
  path: string;
  element: React.ReactNode;
  /** Atlas workspace shell pages render full-bleed and own their own layout. */
  fullBleed?: boolean;
};

function AppShellRoute({
  element,
  fullBleed,
}: {
  element: React.ReactNode;
  fullBleed?: boolean;
}) {
  const location = useLocation();
  const navigate = useNavigate();
  const { activePatientId, isLoading, isUnlocked, setActivePatient } = useAccessContext();
  const routeKey = `${location.pathname}${location.search}`;
  const stripPatient = shouldStripPatient(location.pathname, location.search, isUnlocked, isLoading);
  const hydratePatient = shouldHydratePatient(
    location.pathname,
    location.search,
    isUnlocked,
    activePatientId,
  );
  const isPatientRecordRoute = location.pathname.startsWith("/patient-record");
  const isFhirChartsRoute = location.pathname.startsWith("/fhir-charts");

  useEffect(() => {
    if (isLoading || !isUnlocked) return;
    const params = new URLSearchParams(location.search);
    const patientId = params.get("patient");
    if (!patientId || patientId === activePatientId) return;
    void setActivePatient(patientId);
  }, [activePatientId, isLoading, isUnlocked, location.search, setActivePatient]);

  useEffect(() => {
    if (fullBleed || !hydratePatient) return;
    const params = new URLSearchParams(location.search);
    params.set("patient", activePatientId as string);
    navigate({ pathname: location.pathname, search: `?${params.toString()}` }, { replace: true });
  }, [activePatientId, fullBleed, hydratePatient, location.pathname, location.search, navigate]);

  if (isLoading) {
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
  const isFullscreenWorkspace =
    location.pathname.startsWith("/caspian") ||
    location.pathname.startsWith("/workspaces/");

  // Atlas IA routes — the five top-level modules + their canonical sub-routes.
  const atlasRoutes: ShellRoute[] = [
    // Caspian (first-party agentic workspace)
    { path: "/caspian", element: <CaspianWorkspace />, fullBleed: true },
    { path: "/caspian/sessions/:sessionId", element: <CaspianWorkspace />, fullBleed: true },

    // Workspaces — the user-facing tab for installable plugins
    { path: "/workspaces", element: <PluginsIndex /> },
    { path: "/workspaces/:pluginId", element: <PluginWorkspace />, fullBleed: true },
    { path: "/workspaces/:pluginId/sessions/:sessionId", element: <PluginWorkspace />, fullBleed: true },

    // Patient Record — source-of-truth chart layer (absorbs Data Aggregator)
    { path: "/patient-record", element: <PatientRecordOverview /> },
    { path: "/patient-record/methodology", element: <PatientRecordMethodology /> },
    { path: "/patient-record/sources", element: <PatientRecordSources /> },
    { path: "/patient-record/harmonize", element: <PatientRecordHarmonize /> },
    { path: "/patient-record/cleaning", element: <PatientRecordHarmonize /> },
    { path: "/patient-record/workspaces", element: <PatientRecordWorkspaces /> },
    { path: "/patient-record/publish", element: <PatientRecordPublish /> },
    { path: "/patient-record/context", element: <PatientRecordContext /> },

    // FHIR Charts — FHIR resource browser (former Explorer + Journey)
    { path: "/fhir-charts", element: <FhirChartsOverview /> },
    { path: "/fhir-charts/timeline", element: <FhirChartsTimeline /> },
    { path: "/fhir-charts/labs", element: <FhirChartsLabs /> },
    { path: "/fhir-charts/history", element: <FhirChartsHistory /> },
    { path: "/fhir-charts/care-journey", element: <FhirChartsCareJourney /> },
    { path: "/fhir-charts/journey", element: <FhirChartsJourney /> },
    { path: "/fhir-charts/corpus", element: <FhirChartsCorpus /> },
    { path: "/fhir-charts/safety", element: <FhirChartsSafety /> },
    { path: "/fhir-charts/immunizations", element: <FhirChartsImmunizations /> },
    { path: "/fhir-charts/conditions", element: <FhirChartsConditions /> },
    { path: "/fhir-charts/procedures", element: <FhirChartsProcedures /> },
    { path: "/fhir-charts/clearance", element: <FhirChartsClearance /> },
    { path: "/fhir-charts/anesthesia", element: <FhirChartsAnesthesia /> },
    { path: "/fhir-charts/distributions", element: <FhirChartsDistributions /> },
    { path: "/fhir-charts/interactions", element: <FhirChartsInteractions /> },
    { path: "/fhir-charts/assistant", element: <FhirChartsAssistant /> },
    { path: "/fhir-charts/patient-data", element: <FhirChartsPatientData /> },

    // Learn — internal section (front door for InternalTools)
    { path: "/learn", element: <InternalToolsOverview /> },
    { path: "/learn/fhir-primer", element: <InternalToolsFhirPrimer /> },
    { path: "/learn/definitions", element: <InternalToolsDefinitions /> },
    { path: "/learn/coverage", element: <InternalToolsCoverage /> },
    { path: "/learn/ccda-lab", element: <InternalToolsCcdaLab /> },
    { path: "/learn/qa-eval-lab", element: <InternalToolsQaEvalLab /> },
    { path: "/learn/pipeline-lab", element: <InternalToolsPipelineLab /> },
    { path: "/learn/ground-truth-review", element: <InternalToolsGroundTruth /> },
    { path: "/learn/ground-truth-review/:runId", element: <InternalToolsGroundTruth /> },
    { path: "/learn/labs", element: <InternalToolsLabExplainer /> },
    { path: "/learn/data-sharing", element: <InternalToolsDataSharing /> },
    { path: "/learn/skills/trial-finder", element: <InternalToolsTrialFinder /> },
    { path: "/learn/skills/patients/memory", element: <InternalToolsPatientMemory /> },
  ];

  return (
    <>
      <Routes>
        <Route path="/" element={<Landing />} />
        <Route path="/account" element={<AccountAccessPage />} />
        <Route path="/guest-harmonization" element={<GuestHarmonization />} />
        <Route path="/architecture" element={<PlatformArchitecture />} />
        <Route path="/records-pool" element={<PatientRecordPool />} />
        <Route path="/guided-tour" element={<Navigate to="/using-atlas" replace />} />
        <Route
          path="/using-atlas/*"
          element={<Suspense fallback={<PageFallback />}><UsingAtlasRoutes /></Suspense>}
        />
        {/* Legacy redirects — see .claude/handoff/atlas/README.md §Routing */}
        {/* Tier A: fully-replaced products */}
        <Route path="/preop" element={<Navigate to="/caspian" replace />} />
        <Route path="/preop/*" element={<Navigate to="/caspian" replace />} />
        <Route path="/trials" element={<Navigate to="/workspaces/trial-finder" replace />} />
        <Route path="/ai-workspace/trial-finder" element={<Navigate to="/workspaces/trial-finder" replace />} />
        <Route path="/medication-access" element={<Navigate to="/workspaces/med-access" replace />} />
        <Route path="/marketplace" element={<Navigate to="/workspaces" replace />} />
        <Route path="/marketplace/overview" element={<Navigate to="/workspaces" replace />} />
        <Route path="/marketplace/workspace" element={<Navigate to="/workspaces" replace />} />
        <Route path="/marketplace/publish" element={<Navigate to="/workspaces" replace />} />
        <Route path="/grants" element={<Navigate to="/workspaces" replace />} />
        <Route path="/research-opportunities" element={<Navigate to="/workspaces" replace />} />
        <Route path="/payer-check" element={<Navigate to="/workspaces" replace />} />
        {/* Tier B: Patient Record absorbs the former Data Aggregator */}
        <Route path="/data-aggregator" element={<Navigate to="/patient-record" replace />} />
        <Route path="/data-aggregator/*" element={<Navigate to="/patient-record" replace />} />
        <Route path="/charts" element={<Navigate to="/patient-record" replace />} />
        <Route path="/record" element={<Navigate to="/patient-record" replace />} />
        <Route path="/aggregate" element={<Navigate to="/patient-record/methodology" replace />} />
        <Route path="/aggregate/methodology" element={<Navigate to="/patient-record/methodology" replace />} />
        <Route path="/aggregate/sources" element={<Navigate to="/patient-record/sources" replace />} />
        <Route path="/aggregate/workspaces" element={<Navigate to="/patient-record/workspaces" replace />} />
        <Route path="/aggregate/cleaning" element={<Navigate to="/patient-record/cleaning" replace />} />
        <Route path="/aggregate/harmonize" element={<Navigate to="/patient-record/harmonize" replace />} />
        <Route path="/aggregate/context" element={<Navigate to="/patient-record/context" replace />} />
        <Route path="/aggregate/publish" element={<Navigate to="/patient-record/publish" replace />} />
        {/* Tier C: Explorer becomes FHIR Charts */}
        <Route path="/explorer" element={<Navigate to="/fhir-charts" replace />} />
        <Route path="/explorer/timeline" element={<Navigate to="/fhir-charts/timeline" replace />} />
        <Route path="/explorer/labs" element={<Navigate to="/fhir-charts/labs" replace />} />
        <Route path="/explorer/history" element={<Navigate to="/fhir-charts/history" replace />} />
        <Route path="/explorer/care-journey" element={<Navigate to="/fhir-charts/care-journey" replace />} />
        <Route path="/explorer/corpus" element={<Navigate to="/fhir-charts/corpus" replace />} />
        <Route path="/explorer/safety" element={<Navigate to="/fhir-charts/safety" replace />} />
        <Route path="/explorer/immunizations" element={<Navigate to="/fhir-charts/immunizations" replace />} />
        <Route path="/explorer/conditions" element={<Navigate to="/fhir-charts/conditions" replace />} />
        <Route path="/explorer/procedures" element={<Navigate to="/fhir-charts/procedures" replace />} />
        <Route path="/explorer/clearance" element={<Navigate to="/fhir-charts/clearance" replace />} />
        <Route path="/explorer/anesthesia" element={<Navigate to="/fhir-charts/anesthesia" replace />} />
        <Route path="/explorer/distributions" element={<Navigate to="/fhir-charts/distributions" replace />} />
        <Route path="/explorer/interactions" element={<Navigate to="/fhir-charts/interactions" replace />} />
        <Route path="/explorer/assistant" element={<Navigate to="/fhir-charts/assistant" replace />} />
        <Route path="/explorer/patient-data" element={<Navigate to="/fhir-charts/patient-data" replace />} />
        {/* Tier C: Clinical Insights folds into Caspian workflows */}
        <Route path="/clinical-insights" element={<Navigate to="/caspian" replace />} />
        <Route path="/clinical-insights/overview" element={<Navigate to="/caspian" replace />} />
        <Route path="/clinical-insights/packages" element={<Navigate to="/caspian" replace />} />
        <Route path="/clinical-insights/context-library" element={<Navigate to="/caspian" replace />} />
        <Route path="/clinical-insights/favorites" element={<Navigate to="/caspian" replace />} />
        <Route path="/clinical-insights/create" element={<Navigate to="/caspian" replace />} />
        {/* Tier C: Analysis + pipeline tools fold into Learn */}
        <Route path="/analysis" element={<Navigate to="/learn" replace />} />
        <Route path="/analysis/fhir-primer" element={<Navigate to="/learn/fhir-primer" replace />} />
        <Route path="/analysis/definitions" element={<Navigate to="/learn/definitions" replace />} />
        <Route path="/analysis/coverage" element={<Navigate to="/learn/coverage" replace />} />
        <Route path="/analysis/ccda-testing-lab" element={<Navigate to="/learn/ccda-lab" replace />} />
        <Route path="/analysis/qa-eval-lab" element={<Navigate to="/learn/qa-eval-lab" replace />} />
        <Route path="/pipeline-lab" element={<Navigate to="/learn/pipeline-lab" replace />} />
        <Route path="/ccda-lab" element={<Navigate to="/learn/ccda-lab" replace />} />
        <Route path="/ground-truth-review" element={<Navigate to={buildGroundTruthReviewPath()} replace />} />
        <Route path="/ground-truth-review/:runId" element={<LegacyGroundTruthReviewRedirect />} />
        {/* Stragglers retired during the IA cleanup. */}
        <Route path="/platform" element={<Navigate to="/" replace />} />
        <Route path="/journey" element={<Navigate to="/fhir-charts/journey" replace />} />
        <Route path="/sharing" element={<Navigate to="/learn/data-sharing" replace />} />
        <Route path="/second-opinion" element={<Navigate to="/learn/data-sharing" replace />} />
        <Route path="/marketplace/settings" element={<Navigate to="/workspaces" replace />} />
        <Route path="/skills/trial-finder" element={<Navigate to="/learn/skills/trial-finder" replace />} />
        <Route path="/skills/patients/memory" element={<Navigate to="/learn/skills/patients/memory" replace />} />
        <Route path="/clinical-insights/labs" element={<Navigate to="/learn/labs" replace />} />
        {/* Atlas IA routes — the five top-level modules */}
        {atlasRoutes.map((r) => (
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

function LegacyGroundTruthReviewRedirect() {
  const { runId } = useParams();
  return <Navigate to={buildGroundTruthReviewPath(runId)} replace />;
}

function shouldHydratePatient(
  pathname: string,
  search: string,
  isUnlocked: boolean,
  activePatientId: string | null,
): boolean {
  if (!isUnlocked || !activePatientId) return false;
  if (
    !pathname.startsWith("/patient-record") &&
    !pathname.startsWith("/fhir-charts") &&
    !pathname.startsWith("/caspian") &&
    !pathname.startsWith("/workspaces")
  ) {
    return false;
  }
  const params = new URLSearchParams(search);
  return !params.has("patient");
}

function shouldStripPatient(pathname: string, search: string, isUnlocked: boolean, isLoading: boolean): boolean {
  if (isLoading) return false;
  if (isUnlocked) return false;
  if (
    !pathname.startsWith("/patient-record") &&
    !pathname.startsWith("/fhir-charts") &&
    !pathname.startsWith("/caspian") &&
    !pathname.startsWith("/workspaces")
  ) {
    return false;
  }
  const params = new URLSearchParams(search);
  return params.has("patient");
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

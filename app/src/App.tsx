import { Suspense, lazy, type ComponentType } from "react";
import { BrowserRouter, Navigate, Routes, Route, useLocation } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { AppErrorBoundary } from "./components/AppErrorBoundary";
import { AppShell } from "./components/atlas/AppShell";
import { ChatProvider } from "./context/ChatContext";
import { ChatWidget } from "./components/ChatWidget";
import { Landing } from "./pages/Landing";
import { PlatformArchitecture } from "./pages/PlatformArchitecture";
import { PatientRecordPool } from "./pages/PatientRecordPool";
import { GuidedTour } from "./pages/GuidedTour";

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

const PlatformEntry = lazyNamed(() => import("./pages/PlatformEntry"), "PlatformEntry");
const ExplorerOverview = lazyNamed(() => import("./pages/Explorer/Overview"), "ExplorerOverview");
const ExplorerTimeline = lazyNamed(() => import("./pages/Explorer/Timeline"), "ExplorerTimeline");
const ExplorerCorpus = lazyNamed(() => import("./pages/Explorer/Corpus"), "ExplorerCorpus");
const ExplorerSafety = lazyNamed(() => import("./pages/Explorer/Safety"), "ExplorerSafety");
const ExplorerImmunizations = lazyNamed(() => import("./pages/Explorer/Immunizations"), "ExplorerImmunizations");
const ExplorerConditions = lazyNamed(() => import("./pages/Explorer/Conditions"), "ExplorerConditions");
const ExplorerProcedures = lazyNamed(() => import("./pages/Explorer/Procedures"), "ExplorerProcedures");
const ExplorerClearance = lazyNamed(() => import("./pages/Explorer/Clearance"), "ExplorerClearance");
const ExplorerAnesthesia = lazyNamed(() => import("./pages/Explorer/Anesthesia"), "ExplorerAnesthesia");
const ExplorerDistributions = lazyNamed(() => import("./pages/Explorer/Distributions"), "ExplorerDistributions");
const ExplorerInteractions = lazyNamed(() => import("./pages/Explorer/Interactions"), "ExplorerInteractions");
const ExplorerAssistant = lazyNamed(() => import("./pages/Explorer/Assistant"), "ExplorerAssistant");
const ExplorerCareJourney = lazyNamed(() => import("./pages/Explorer/CareJourney"), "ExplorerCareJourney");
const ExplorerPatientData = lazyNamed(() => import("./pages/Explorer/PatientData"), "ExplorerPatientData");
const ExplorerHistory = lazyNamed(() => import("./pages/Explorer/History"), "ExplorerHistory");
const ExplorerLabs = lazyNamed(() => import("./pages/Explorer/Labs"), "ExplorerLabs");
const PatientJourney = lazyNamed(() => import("./pages/Journey/PatientJourney"), "PatientJourney");
const PatientRecordOverview = lazyNamed(() => import("./pages/Modules/PatientRecordOverview"), "PatientRecordOverview");
const DataSharing = lazyNamed(() => import("./pages/Modules/DataSharing"), "DataSharing");
const PublishReadinessPage = lazyNamed(() => import("./pages/Modules/DataAggregator/PublishReadinessPage"), "PublishReadinessPage");
const SourceIntakePage = lazyNamed(() => import("./pages/Modules/DataAggregator/SourceIntakePage"), "SourceIntakePage");
const WorkspaceLibraryPage = lazyNamed(() => import("./pages/Modules/DataAggregator/WorkspaceLibraryPage"), "WorkspaceLibraryPage");
const HarmonizeView = lazyNamed(() => import("./pages/Modules/HarmonizeView"), "HarmonizeView");
const LabExplainer = lazyNamed(() => import("./pages/Modules/LabExplainer"), "LabExplainer");
const CcdaPipelineLab = lazyNamed(() => import("./pages/Modules/CcdaPipelineLab"), "CcdaPipelineLab");
const TrialFinder = lazyNamed(() => import("./pages/Modules/TrialFinder"), "TrialFinder");
const PatientMemoryView = lazyNamed(() => import("./pages/Modules/PatientMemoryView"), "PatientMemoryView");
const PatientContext = lazyNamed(() => import("./pages/Modules/PatientContext"), "PatientContext");
const AggregationMethodology = lazyNamed(() => import("./pages/Modules/AggregationMethodology"), "AggregationMethodology");
const AnalysisOverview = lazyNamed(() => import("./pages/Analysis/Overview"), "AnalysisOverview");
const AnalysisDefinitions = lazyNamed(() => import("./pages/Analysis/Definitions"), "AnalysisDefinitions");
const AnalysisCoverage = lazyNamed(() => import("./pages/Analysis/Coverage"), "AnalysisCoverage");
const AnalysisFhirPrimer = lazyNamed(() => import("./pages/Analysis/FhirPrimer"), "AnalysisFhirPrimer");
const QaEvalLab = lazyNamed(() => import("./pages/Analysis/QaEvalLab"), "QaEvalLab");
const PipelineLab = lazyNamed(() => import("./pages/PipelineLab/Leaderboard"), "PipelineLab");
const GroundTruthReview = lazyNamed(() => import("./pages/GroundTruthReview/ReferenceReview"), "GroundTruthReview");
const UsingAtlasRoutes = lazyNamed(() => import("./pages/UsingAtlas/routes"), "UsingAtlasRoutes");
const CaspianWorkspace = lazyNamed(() => import("./pages/Atlas/CaspianWorkspace"), "CaspianWorkspace");
const PackageWorkspace = lazyNamed(() => import("./pages/Atlas/PackageWorkspace"), "PackageWorkspace");
const MarketplaceIndex = lazyNamed(() => import("./pages/Atlas/MarketplaceIndex"), "MarketplaceIndex");

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
  if (fullBleed) {
    return (
      <Suspense fallback={<FullscreenPageFallback />}>{element}</Suspense>
    );
  }
  return (
    <AppShell>
      <Suspense fallback={<PageFallback />}>{element}</Suspense>
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

    // Workspaces (marketplace packages)
    { path: "/workspaces", element: <MarketplaceIndex /> },
    { path: "/workspaces/:packageId", element: <PackageWorkspace />, fullBleed: true },
    { path: "/workspaces/:packageId/sessions/:sessionId", element: <PackageWorkspace />, fullBleed: true },

    // Patient Record — source-of-truth chart layer (folds in former Data Aggregator)
    { path: "/patient-record", element: <PatientRecordOverview /> },
    { path: "/patient-record/methodology", element: <AggregationMethodology /> },
    { path: "/patient-record/sources", element: <SourceIntakePage /> },
    { path: "/patient-record/harmonize", element: <HarmonizeView /> },
    { path: "/patient-record/cleaning", element: <HarmonizeView /> },
    { path: "/patient-record/workspaces", element: <WorkspaceLibraryPage /> },
    { path: "/patient-record/publish", element: <PublishReadinessPage /> },
    { path: "/patient-record/context", element: <PatientContext /> },

    // FHIR Charts — FHIR resource browser (former Explorer)
    { path: "/fhir-charts", element: <ExplorerOverview /> },
    { path: "/fhir-charts/timeline", element: <ExplorerTimeline /> },
    { path: "/fhir-charts/labs", element: <ExplorerLabs /> },
    { path: "/fhir-charts/history", element: <ExplorerHistory /> },
    { path: "/fhir-charts/care-journey", element: <ExplorerCareJourney /> },
    { path: "/fhir-charts/corpus", element: <ExplorerCorpus /> },
    { path: "/fhir-charts/safety", element: <ExplorerSafety /> },
    { path: "/fhir-charts/immunizations", element: <ExplorerImmunizations /> },
    { path: "/fhir-charts/conditions", element: <ExplorerConditions /> },
    { path: "/fhir-charts/procedures", element: <ExplorerProcedures /> },
    { path: "/fhir-charts/clearance", element: <ExplorerClearance /> },
    { path: "/fhir-charts/anesthesia", element: <ExplorerAnesthesia /> },
    { path: "/fhir-charts/distributions", element: <ExplorerDistributions /> },
    { path: "/fhir-charts/interactions", element: <ExplorerInteractions /> },
    { path: "/fhir-charts/assistant", element: <ExplorerAssistant /> },
    { path: "/fhir-charts/patient-data", element: <ExplorerPatientData /> },

    // Learn — internal section (runbooks, evals, methodology)
    { path: "/learn", element: <AnalysisOverview /> },
    { path: "/learn/fhir-primer", element: <AnalysisFhirPrimer /> },
    { path: "/learn/definitions", element: <AnalysisDefinitions /> },
    { path: "/learn/coverage", element: <AnalysisCoverage /> },
    { path: "/learn/ccda-lab", element: <CcdaPipelineLab /> },
    { path: "/learn/qa-eval-lab", element: <QaEvalLab /> },
    { path: "/learn/pipeline-lab", element: <PipelineLab /> },
    { path: "/learn/ground-truth-review", element: <GroundTruthReview /> },
    { path: "/learn/ground-truth-review/:runId", element: <GroundTruthReview /> },
  ];

  // Routes that don't map into the five-module IA but are still reachable.
  const supportRoutes: ShellRoute[] = [
    { path: "/platform", element: <PlatformEntry /> },
    { path: "/journey", element: <PatientJourney /> },
    { path: "/skills/trial-finder", element: <TrialFinder /> },
    { path: "/skills/patients/memory", element: <PatientMemoryView /> },
    { path: "/sharing", element: <DataSharing /> },
    { path: "/second-opinion", element: <DataSharing /> },
    { path: "/marketplace/settings", element: <DataSharing /> },
    // Clinical Insights folds into Caspian workflows, but keep these pages
    // reachable for the alternate-view links until the migration completes.
    { path: "/clinical-insights/labs", element: <LabExplainer /> },
  ];

  return (
    <>
      <Routes>
        <Route path="/" element={<Landing />} />
        <Route path="/architecture" element={<PlatformArchitecture />} />
        <Route path="/records-pool" element={<PatientRecordPool />} />
        <Route path="/guided-tour" element={<GuidedTour />} />
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
        <Route path="/ground-truth-review" element={<Navigate to="/learn/ground-truth-review" replace />} />
        <Route path="/ground-truth-review/:runId" element={<Navigate to="/learn/ground-truth-review" replace />} />
        {/* Atlas IA routes */}
        {atlasRoutes.map((r) => (
          <Route
            key={r.path}
            path={r.path}
            element={<AppShellRoute element={r.element} fullBleed={r.fullBleed} />}
          />
        ))}
        {/* Support routes outside the five-module IA */}
        {supportRoutes.map((r) => (
          <Route
            key={r.path}
            path={r.path}
            element={<AppShellRoute element={r.element} />}
          />
        ))}
      </Routes>
      {!isFullscreenWorkspace && <ChatWidget />}
    </>
  );
}

export default function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <AppErrorBoundary>
          <ChatProvider>
            <AppShellRoutes />
          </ChatProvider>
        </AppErrorBoundary>
      </BrowserRouter>
    </QueryClientProvider>
  );
}

import { Suspense, lazy, type ComponentType } from "react";
import { BrowserRouter, Routes, Route } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { AppErrorBoundary } from "./components/AppErrorBoundary";
import { Layout } from "./components/Layout";
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
      <div className="h-12 w-12 rounded-full border-4 border-[#dfe4ea] border-t-[#5b76fe]" />
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
const PreOpOverview = lazyNamed(() => import("./pages/Modules/PreOpOverview"), "PreOpOverview");
const ClinicalTrials = lazyNamed(() => import("./pages/Modules/ClinicalTrials"), "ClinicalTrials");
const MedicationAccess = lazyNamed(() => import("./pages/Modules/MedicationAccess"), "MedicationAccess");
const Marketplace = lazyNamed(() => import("./pages/Modules/Marketplace"), "Marketplace");
const MarketplaceConcept = lazyNamed(() => import("./pages/Modules/MarketplaceConcept"), "MarketplaceConcept");
const DataSharing = lazyNamed(() => import("./pages/Modules/DataSharing"), "DataSharing");
const DataCatalog = lazyNamed(() => import("./pages/Modules/DataCatalog"), "DataCatalog");
const PublishReadinessPage = lazyNamed(() => import("./pages/Modules/DataAggregator/PublishReadinessPage"), "PublishReadinessPage");
const SourceIntakePage = lazyNamed(() => import("./pages/Modules/DataAggregator/SourceIntakePage"), "SourceIntakePage");
const WorkspaceLibraryPage = lazyNamed(() => import("./pages/Modules/DataAggregator/WorkspaceLibraryPage"), "WorkspaceLibraryPage");
const HarmonizeView = lazyNamed(() => import("./pages/Modules/HarmonizeView"), "HarmonizeView");
const ClinicalInsights = lazyNamed(() => import("./pages/Modules/ClinicalInsights"), "ClinicalInsights");
const LabExplainer = lazyNamed(() => import("./pages/Modules/LabExplainer"), "LabExplainer");
const CcdaPipelineLab = lazyNamed(() => import("./pages/Modules/CcdaPipelineLab"), "CcdaPipelineLab");
const TrialFinder = lazyNamed(() => import("./pages/Modules/TrialFinder"), "TrialFinder");
const PatientMemoryView = lazyNamed(() => import("./pages/Modules/PatientMemoryView"), "PatientMemoryView");
const PatientContext = lazyNamed(() => import("./pages/Modules/PatientContext"), "PatientContext");
const AggregationMethodology = lazyNamed(() => import("./pages/Modules/AggregationMethodology"), "AggregationMethodology");
const AnalysisOverview = lazyNamed(() => import("./pages/Analysis/Overview"), "AnalysisOverview");
const AnalysisMethodology = lazyNamed(() => import("./pages/Analysis/Methodology"), "AnalysisMethodology");
const AnalysisDefinitions = lazyNamed(() => import("./pages/Analysis/Definitions"), "AnalysisDefinitions");
const AnalysisCoverage = lazyNamed(() => import("./pages/Analysis/Coverage"), "AnalysisCoverage");
const AnalysisFlightSchool = lazyNamed(() => import("./pages/Analysis/FlightSchool"), "AnalysisFlightSchool");
const AnalysisFhirPrimer = lazyNamed(() => import("./pages/Analysis/FhirPrimer"), "AnalysisFhirPrimer");
const QaEvalLab = lazyNamed(() => import("./pages/Analysis/QaEvalLab"), "QaEvalLab");
const PipelineLab = lazyNamed(() => import("./pages/PipelineLab/Leaderboard"), "PipelineLab");
const GroundTruthReview = lazyNamed(() => import("./pages/GroundTruthReview/ReferenceReview"), "GroundTruthReview");
const UsingAtlasRoutes = lazyNamed(() => import("./pages/UsingAtlas/routes"), "UsingAtlasRoutes");
const TrialFinderWorkspace = lazyNamed(() => import("./pages/AIWorkspace/TrialFinderWorkspace"), "TrialFinderWorkspace");

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      retry: 1,
      refetchOnWindowFocus: false,
    },
  },
});

export default function App() {
  const routes = [
    { path: "/platform", element: <PlatformEntry /> },
    { path: "/charts", element: <PatientRecordOverview /> },
    { path: "/record", element: <PatientRecordOverview /> },
    { path: "/aggregate", element: <AggregationMethodology /> },
    { path: "/aggregate/methodology", element: <AggregationMethodology /> },
    { path: "/aggregate/workspaces", element: <WorkspaceLibraryPage /> },
    { path: "/aggregate/sources", element: <SourceIntakePage /> },
    { path: "/aggregate/cleaning", element: <HarmonizeView /> },
    { path: "/aggregate/context", element: <PatientContext /> },
    { path: "/aggregate/harmonize", element: <HarmonizeView /> },
    { path: "/aggregate/publish", element: <PublishReadinessPage /> },
    { path: "/clinical-insights/overview", element: <ClinicalInsights /> },
    { path: "/clinical-insights", element: <ClinicalInsights /> },
    { path: "/clinical-insights/packages", element: <ClinicalInsights /> },
    { path: "/clinical-insights/context-library", element: <ClinicalInsights /> },
    { path: "/clinical-insights/favorites", element: <ClinicalInsights /> },
    { path: "/clinical-insights/create", element: <ClinicalInsights /> },
    { path: "/clinical-insights/labs", element: <LabExplainer /> },
    { path: "/marketplace", element: <Marketplace /> },
    { path: "/marketplace/overview", element: <Marketplace /> },
    { path: "/marketplace/workspace", element: <Marketplace /> },
    { path: "/marketplace/settings", element: <DataSharing /> },
    { path: "/marketplace/publish", element: <MarketplaceConcept /> },
    { path: "/explorer", element: <ExplorerOverview /> },
    { path: "/explorer/timeline", element: <ExplorerTimeline /> },
    { path: "/explorer/labs", element: <ExplorerLabs /> },
    { path: "/explorer/history", element: <ExplorerHistory /> },
    { path: "/explorer/care-journey", element: <ExplorerCareJourney /> },
    { path: "/explorer/corpus", element: <ExplorerCorpus /> },
    { path: "/explorer/safety", element: <ExplorerSafety /> },
    { path: "/explorer/immunizations", element: <ExplorerImmunizations /> },
    { path: "/explorer/conditions", element: <ExplorerConditions /> },
    { path: "/explorer/procedures", element: <ExplorerProcedures /> },
    { path: "/explorer/clearance", element: <ExplorerClearance /> },
    { path: "/explorer/anesthesia", element: <ExplorerAnesthesia /> },
    { path: "/explorer/distributions", element: <ExplorerDistributions /> },
    { path: "/explorer/interactions", element: <ExplorerInteractions /> },
    { path: "/explorer/assistant", element: <ExplorerAssistant /> },
    { path: "/explorer/patient-data", element: <ExplorerPatientData /> },
    { path: "/preop", element: <PreOpOverview /> },
    { path: "/preop/clearance", element: <ExplorerClearance /> },
    { path: "/preop/medication-holds", element: <ExplorerSafety /> },
    { path: "/preop/anesthesia-handoff", element: <ExplorerAnesthesia /> },
    { path: "/journey", element: <PatientJourney /> },
    { path: "/trials", element: <ClinicalTrials /> },
    { path: "/skills/trial-finder", element: <TrialFinder /> },
    { path: "/skills/patients/memory", element: <PatientMemoryView /> },
    { path: "/medication-access", element: <MedicationAccess /> },
    { path: "/grants", element: <MarketplaceConcept /> },
    { path: "/research-opportunities", element: <MarketplaceConcept /> },
    { path: "/payer-check", element: <MarketplaceConcept /> },
    { path: "/sharing", element: <DataSharing /> },
    { path: "/second-opinion", element: <DataSharing /> },
    { path: "/analysis", element: <AnalysisOverview /> },
    { path: "/analysis/fhir-primer", element: <AnalysisFhirPrimer /> },
    { path: "/analysis/methodology", element: <AnalysisMethodology /> },
    { path: "/analysis/definitions", element: <AnalysisDefinitions /> },
    { path: "/analysis/coverage", element: <AnalysisCoverage /> },
    { path: "/analysis/flight-school", element: <AnalysisFlightSchool /> },
    { path: "/analysis/ccda-testing-lab", element: <CcdaPipelineLab /> },
    { path: "/analysis/qa-eval-lab", element: <QaEvalLab /> },
    { path: "/pipeline-lab", element: <PipelineLab /> },
    { path: "/ccda-lab", element: <CcdaPipelineLab /> },
    { path: "/ground-truth-review", element: <GroundTruthReview /> },
    { path: "/ground-truth-review/:runId", element: <GroundTruthReview /> },
    { path: "/ai-workspace/trial-finder", element: <TrialFinderWorkspace /> },
    { path: "/catalog", element: <DataCatalog /> },
  ];

  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <AppErrorBoundary>
          <ChatProvider>
            <Routes>
              <Route path="/" element={<Landing />} />
              <Route path="/architecture" element={<PlatformArchitecture />} />
              <Route path="/records-pool" element={<PatientRecordPool />} />
              <Route path="/guided-tour" element={<GuidedTour />} />
              <Route path="/using-atlas/*" element={<Suspense fallback={<PageFallback />}><UsingAtlasRoutes /></Suspense>} />
              {routes.map((route) => (
                <Route
                  key={route.path}
                  path={route.path}
                  element={
                    <Layout>
                      <Suspense fallback={<PageFallback />}>
                        {route.element}
                      </Suspense>
                    </Layout>
                  }
                />
              ))}
            </Routes>
            <ChatWidget />
          </ChatProvider>
        </AppErrorBoundary>
      </BrowserRouter>
    </QueryClientProvider>
  );
}

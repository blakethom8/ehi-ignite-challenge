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
import { PlatformEntry } from "./pages/PlatformEntry";
import { ExplorerOverview } from "./pages/Explorer/Overview";
import { ExplorerTimeline } from "./pages/Explorer/Timeline";
import { ExplorerCorpus } from "./pages/Explorer/Corpus";
import { ExplorerSafety } from "./pages/Explorer/Safety";
import { ExplorerImmunizations } from "./pages/Explorer/Immunizations";
import { ExplorerConditions } from "./pages/Explorer/Conditions";
import { ExplorerProcedures } from "./pages/Explorer/Procedures";
import { ExplorerClearance } from "./pages/Explorer/Clearance";
import { ExplorerAnesthesia } from "./pages/Explorer/Anesthesia";
import { ExplorerDistributions } from "./pages/Explorer/Distributions";
import { ExplorerInteractions } from "./pages/Explorer/Interactions";
import { ExplorerAssistant } from "./pages/Explorer/Assistant";
import { ExplorerCareJourney } from "./pages/Explorer/CareJourney";
import { ExplorerPatientData } from "./pages/Explorer/PatientData";
import { ExplorerHistory } from "./pages/Explorer/History";
import { PatientJourney } from "./pages/Journey/PatientJourney";
import { PatientRecordOverview } from "./pages/Modules/PatientRecordOverview";
import { PreOpOverview } from "./pages/Modules/PreOpOverview";
import { ClinicalTrials } from "./pages/Modules/ClinicalTrials";
import { MedicationAccess } from "./pages/Modules/MedicationAccess";
import { Marketplace } from "./pages/Modules/Marketplace";
import { MarketplaceConcept } from "./pages/Modules/MarketplaceConcept";
import { DataSharing } from "./pages/Modules/DataSharing";
import { DataCatalog } from "./pages/Modules/DataCatalog";
import { DataAggregator } from "./pages/Modules/DataAggregator";
import { ClinicalInsights } from "./pages/Modules/ClinicalInsights";
import { PatientContext } from "./pages/Modules/PatientContext";
import { AggregationMethodology } from "./pages/Modules/AggregationMethodology";
import { AnalysisOverview } from "./pages/Analysis/Overview";
import { AnalysisMethodology } from "./pages/Analysis/Methodology";
import { AnalysisDefinitions } from "./pages/Analysis/Definitions";
import { AnalysisCoverage } from "./pages/Analysis/Coverage";
import { AnalysisFlightSchool } from "./pages/Analysis/FlightSchool";
import { AnalysisFhirPrimer } from "./pages/Analysis/FhirPrimer";

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
    { path: "/aggregate/sources", element: <DataAggregator /> },
    { path: "/aggregate/cleaning", element: <DataAggregator /> },
    { path: "/aggregate/context", element: <PatientContext /> },
    { path: "/aggregate/publish", element: <DataAggregator /> },
    { path: "/clinical-insights", element: <ClinicalInsights /> },
    { path: "/clinical-insights/packages", element: <ClinicalInsights /> },
    { path: "/clinical-insights/context-library", element: <ClinicalInsights /> },
    { path: "/clinical-insights/favorites", element: <ClinicalInsights /> },
    { path: "/clinical-insights/create", element: <ClinicalInsights /> },
    { path: "/marketplace", element: <Marketplace /> },
    { path: "/marketplace/overview", element: <Marketplace /> },
    { path: "/marketplace/workspace", element: <Marketplace /> },
    { path: "/marketplace/settings", element: <DataSharing /> },
    { path: "/marketplace/publish", element: <MarketplaceConcept /> },
    { path: "/explorer", element: <ExplorerOverview /> },
    { path: "/explorer/timeline", element: <ExplorerTimeline /> },
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
              {routes.map((route) => (
                <Route
                  key={route.path}
                  path={route.path}
                  element={<Layout>{route.element}</Layout>}
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

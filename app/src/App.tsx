import { BrowserRouter, Routes, Route } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { Layout } from "./components/Layout";
import { ChatProvider } from "./context/ChatContext";
import { ChatWidget } from "./components/ChatWidget";
import { Landing } from "./pages/Landing";
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
import { JourneyPlaceholder } from "./pages/Journey/Placeholder";
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
    { path: "/explorer", element: <ExplorerOverview /> },
    { path: "/explorer/timeline", element: <ExplorerTimeline /> },
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
    { path: "/journey", element: <JourneyPlaceholder /> },
    { path: "/analysis", element: <AnalysisOverview /> },
    { path: "/analysis/fhir-primer", element: <AnalysisFhirPrimer /> },
    { path: "/analysis/methodology", element: <AnalysisMethodology /> },
    { path: "/analysis/definitions", element: <AnalysisDefinitions /> },
    { path: "/analysis/coverage", element: <AnalysisCoverage /> },
    { path: "/analysis/flight-school", element: <AnalysisFlightSchool /> },
  ];

  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <ChatProvider>
          <Routes>
            <Route path="/" element={<Landing />} />
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
      </BrowserRouter>
    </QueryClientProvider>
  );
}

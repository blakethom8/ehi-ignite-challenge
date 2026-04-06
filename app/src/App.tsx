import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { Layout } from "./components/Layout";
import { ExplorerOverview } from "./pages/Explorer/Overview";
import { ExplorerTimeline } from "./pages/Explorer/Timeline";
import { ExplorerCorpus } from "./pages/Explorer/Corpus";
import { ExplorerSafety } from "./pages/Explorer/Safety";
import { ExplorerImmunizations } from "./pages/Explorer/Immunizations";
import { ExplorerConditions } from "./pages/Explorer/Conditions";
import { ExplorerProcedures } from "./pages/Explorer/Procedures";
import { JourneyPlaceholder } from "./pages/Journey/Placeholder";

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      retry: 1,
      refetchOnWindowFocus: false,
    },
  },
});

export default function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <Layout>
          <Routes>
            <Route path="/" element={<Navigate to="/explorer" replace />} />
            <Route path="/explorer" element={<ExplorerOverview />} />
            <Route path="/explorer/timeline" element={<ExplorerTimeline />} />
            <Route path="/explorer/corpus" element={<ExplorerCorpus />} />
            <Route path="/explorer/safety" element={<ExplorerSafety />} />
            <Route path="/explorer/immunizations" element={<ExplorerImmunizations />} />
            <Route path="/explorer/conditions" element={<ExplorerConditions />} />
            <Route path="/explorer/procedures" element={<ExplorerProcedures />} />
            <Route path="/journey" element={<JourneyPlaceholder />} />
          </Routes>
        </Layout>
      </BrowserRouter>
    </QueryClientProvider>
  );
}

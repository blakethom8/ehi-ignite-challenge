import { Navigate, type RouteProps, useParams } from "react-router-dom";
import { buildGroundTruthReviewPath } from "../routing";

export type RedirectRoute = Pick<RouteProps, "path" | "element">;

export const legacyRedirectRoutes: RedirectRoute[] = [
  // Tier A: fully-replaced products
  { path: "/preop", element: <Navigate to="/caspian" replace /> },
  { path: "/preop/*", element: <Navigate to="/caspian" replace /> },
  { path: "/trials", element: <Navigate to="/workspaces/trial-finder" replace /> },
  { path: "/ai-workspace/trial-finder", element: <Navigate to="/workspaces/trial-finder" replace /> },
  { path: "/medication-access", element: <Navigate to="/workspaces/med-access" replace /> },
  { path: "/marketplace", element: <Navigate to="/workspaces" replace /> },
  { path: "/marketplace/overview", element: <Navigate to="/workspaces" replace /> },
  { path: "/marketplace/workspace", element: <Navigate to="/workspaces" replace /> },
  { path: "/marketplace/publish", element: <Navigate to="/workspaces" replace /> },
  { path: "/grants", element: <Navigate to="/workspaces" replace /> },
  { path: "/research-opportunities", element: <Navigate to="/workspaces" replace /> },
  { path: "/payer-check", element: <Navigate to="/workspaces" replace /> },

  // Tier B: Patient Record absorbs the former Data Aggregator
  { path: "/data-aggregator", element: <Navigate to="/patient-record" replace /> },
  { path: "/data-aggregator/*", element: <Navigate to="/patient-record" replace /> },
  { path: "/charts", element: <Navigate to="/patient-record" replace /> },
  { path: "/record", element: <Navigate to="/patient-record" replace /> },
  { path: "/aggregate", element: <Navigate to="/patient-record/methodology" replace /> },
  { path: "/aggregate/methodology", element: <Navigate to="/patient-record/methodology" replace /> },
  { path: "/aggregate/sources", element: <Navigate to="/patient-record/sources" replace /> },
  { path: "/aggregate/workspaces", element: <Navigate to="/patient-record/workspaces" replace /> },
  { path: "/aggregate/cleaning", element: <Navigate to="/patient-record/cleaning" replace /> },
  { path: "/aggregate/harmonize", element: <Navigate to="/patient-record/harmonize" replace /> },
  { path: "/aggregate/context", element: <Navigate to="/patient-record/context" replace /> },
  { path: "/aggregate/publish", element: <Navigate to="/patient-record/publish" replace /> },

  // Tier C: Explorer becomes FHIR Charts
  { path: "/explorer", element: <Navigate to="/fhir-charts" replace /> },
  { path: "/explorer/timeline", element: <Navigate to="/fhir-charts/timeline" replace /> },
  { path: "/explorer/labs", element: <Navigate to="/fhir-charts/labs" replace /> },
  { path: "/explorer/history", element: <Navigate to="/fhir-charts/history" replace /> },
  { path: "/explorer/care-journey", element: <Navigate to="/fhir-charts/care-journey" replace /> },
  { path: "/explorer/corpus", element: <Navigate to="/fhir-charts/corpus" replace /> },
  { path: "/explorer/safety", element: <Navigate to="/fhir-charts/safety" replace /> },
  { path: "/explorer/immunizations", element: <Navigate to="/fhir-charts/immunizations" replace /> },
  { path: "/explorer/conditions", element: <Navigate to="/fhir-charts/conditions" replace /> },
  { path: "/explorer/procedures", element: <Navigate to="/fhir-charts/procedures" replace /> },
  { path: "/explorer/clearance", element: <Navigate to="/fhir-charts/clearance" replace /> },
  { path: "/explorer/anesthesia", element: <Navigate to="/fhir-charts/anesthesia" replace /> },
  { path: "/explorer/distributions", element: <Navigate to="/fhir-charts/distributions" replace /> },
  { path: "/explorer/interactions", element: <Navigate to="/fhir-charts/interactions" replace /> },
  { path: "/explorer/assistant", element: <Navigate to="/fhir-charts/assistant" replace /> },
  { path: "/explorer/patient-data", element: <Navigate to="/fhir-charts/patient-data" replace /> },

  // Tier C: Clinical Insights folds into Caspian workflows
  { path: "/clinical-insights", element: <Navigate to="/caspian" replace /> },
  { path: "/clinical-insights/overview", element: <Navigate to="/caspian" replace /> },
  { path: "/clinical-insights/packages", element: <Navigate to="/caspian" replace /> },
  { path: "/clinical-insights/context-library", element: <Navigate to="/caspian" replace /> },
  { path: "/clinical-insights/favorites", element: <Navigate to="/caspian" replace /> },
  { path: "/clinical-insights/create", element: <Navigate to="/caspian" replace /> },

  // Tier C: Analysis + pipeline tools fold into Learn
  { path: "/analysis", element: <Navigate to="/learn" replace /> },
  { path: "/analysis/fhir-primer", element: <Navigate to="/learn/fhir-primer" replace /> },
  { path: "/analysis/definitions", element: <Navigate to="/learn/definitions" replace /> },
  { path: "/analysis/coverage", element: <Navigate to="/learn/coverage" replace /> },
  { path: "/analysis/ccda-testing-lab", element: <Navigate to="/learn/ccda-lab" replace /> },
  { path: "/analysis/qa-eval-lab", element: <Navigate to="/learn/qa-eval-lab" replace /> },
  { path: "/pipeline-lab", element: <Navigate to="/learn/pipeline-lab" replace /> },
  { path: "/ccda-lab", element: <Navigate to="/learn/ccda-lab" replace /> },
  { path: "/ground-truth-review", element: <Navigate to={buildGroundTruthReviewPath()} replace /> },
  { path: "/ground-truth-review/:runId", element: <LegacyGroundTruthReviewRedirect /> },

  // Stragglers retired during the IA cleanup.
  { path: "/platform", element: <Navigate to="/" replace /> },
  { path: "/journey", element: <Navigate to="/fhir-charts/journey" replace /> },
  { path: "/sharing", element: <Navigate to="/learn/data-sharing" replace /> },
  { path: "/second-opinion", element: <Navigate to="/learn/data-sharing" replace /> },
  { path: "/marketplace/settings", element: <Navigate to="/workspaces" replace /> },
  { path: "/skills/trial-finder", element: <Navigate to="/learn/skills/trial-finder" replace /> },
  { path: "/skills/patients/memory", element: <Navigate to="/learn/skills/patients/memory" replace /> },
  { path: "/clinical-insights/labs", element: <Navigate to="/learn/labs" replace /> },
];

function LegacyGroundTruthReviewRedirect() {
  const { runId } = useParams();
  return <Navigate to={buildGroundTruthReviewPath(runId)} replace />;
}

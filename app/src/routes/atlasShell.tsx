import { lazy, type ComponentType, type ReactNode } from "react";
import { Navigate, useLocation } from "react-router-dom";

export type ShellRoute = {
  path: string;
  element: ReactNode;
  /** Atlas workspace shell pages render full-bleed and own their own layout. */
  fullBleed?: boolean;
};

function lazyNamed<TModule extends Record<string, unknown>>(
  loader: () => Promise<TModule>,
  exportName: keyof TModule,
) {
  return lazy(async () => {
    const module = await loader();
    return { default: module[exportName] as ComponentType };
  });
}

// Atlas shell pages (the five top-level modules)
const CaspianWorkspace = lazyNamed(() => import("../pages/Caspian/Workspace"), "CaspianWorkspace");
const PluginWorkspace = lazyNamed(() => import("../pages/Plugins/Workspace"), "PluginWorkspace");
const PluginsIndex = lazyNamed(() => import("../pages/Plugins/Index"), "PluginsIndex");

// Patient Record module — source-of-truth chart layer (absorbs Data Aggregator)
const PatientRecordOverview = lazyNamed(() => import("../pages/PatientRecord/Overview"), "PatientRecordOverview");
const PatientRecordHarmonize = lazyNamed(() => import("../pages/PatientRecord/Harmonize"), "HarmonizeView");
const PatientRecordMethodology = lazyNamed(() => import("../pages/PatientRecord/Methodology"), "AggregationMethodology");
const PatientRecordContext = lazyNamed(() => import("../pages/PatientRecord/Context"), "PatientContext");
const PatientRecordPublish = lazyNamed(() => import("../pages/PatientRecord/aggregator/PublishReadinessPage"), "PublishReadinessPage");
const PatientRecordSources = lazyNamed(() => import("../pages/PatientRecord/aggregator/SourceIntakePage"), "SourceIntakePage");
const PatientRecordSnapshots = lazyNamed(() => import("../pages/PatientRecord/Snapshots"), "PatientRecordSnapshots");

// FHIR Charts module — FHIR resource browser (former Explorer)
const FhirChartsOverview = lazyNamed(() => import("../pages/FhirCharts/Overview"), "FhirChartsOverview");
const FhirChartsTimeline = lazyNamed(() => import("../pages/FhirCharts/Timeline"), "FhirChartsTimeline");
const FhirChartsCorpus = lazyNamed(() => import("../pages/FhirCharts/Corpus"), "FhirChartsCorpus");
const FhirChartsSafety = lazyNamed(() => import("../pages/FhirCharts/Safety"), "FhirChartsSafety");
const FhirChartsImmunizations = lazyNamed(() => import("../pages/FhirCharts/Immunizations"), "FhirChartsImmunizations");
const FhirChartsConditions = lazyNamed(() => import("../pages/FhirCharts/Conditions"), "FhirChartsConditions");
const FhirChartsProcedures = lazyNamed(() => import("../pages/FhirCharts/Procedures"), "FhirChartsProcedures");
const FhirChartsClearance = lazyNamed(() => import("../pages/FhirCharts/Clearance"), "FhirChartsClearance");
const FhirChartsAnesthesia = lazyNamed(() => import("../pages/FhirCharts/Anesthesia"), "FhirChartsAnesthesia");
const FhirChartsDistributions = lazyNamed(() => import("../pages/FhirCharts/Distributions"), "FhirChartsDistributions");
const FhirChartsInteractions = lazyNamed(() => import("../pages/FhirCharts/Interactions"), "FhirChartsInteractions");
const FhirChartsAssistant = lazyNamed(() => import("../pages/FhirCharts/Assistant"), "FhirChartsAssistant");
const FhirChartsCareJourney = lazyNamed(() => import("../pages/FhirCharts/CareJourney"), "FhirChartsCareJourney");
const FhirChartsPatientData = lazyNamed(() => import("../pages/FhirCharts/PatientData"), "FhirChartsPatientData");
const FhirChartsHistory = lazyNamed(() => import("../pages/FhirCharts/History"), "FhirChartsHistory");
const FhirChartsLabs = lazyNamed(() => import("../pages/FhirCharts/Labs"), "FhirChartsLabs");
const FhirChartsJourney = lazyNamed(() => import("../pages/FhirCharts/Journey"), "PatientJourney");

// Internal Tools — runbooks, evals, labs, reviews (routed via /learn/*)
const InternalToolsOverview = lazyNamed(() => import("../pages/InternalTools/Overview"), "InternalToolsOverview");
const InternalToolsDefinitions = lazyNamed(() => import("../pages/InternalTools/Definitions"), "InternalToolsDefinitions");
const InternalToolsCoverage = lazyNamed(() => import("../pages/InternalTools/Coverage"), "InternalToolsCoverage");
const InternalToolsFhirPrimer = lazyNamed(() => import("../pages/InternalTools/FhirPrimer"), "InternalToolsFhirPrimer");
const InternalToolsQaEvalLab = lazyNamed(() => import("../pages/InternalTools/QaEvalLab"), "QaEvalLab");
const InternalToolsCcdaLab = lazyNamed(() => import("../pages/InternalTools/CcdaLab"), "CcdaPipelineLab");
const InternalToolsPipelineLab = lazyNamed(() => import("../pages/InternalTools/PipelineLab"), "PipelineLab");
const InternalToolsGroundTruth = lazyNamed(() => import("../pages/InternalTools/GroundTruthReview"), "GroundTruthReview");
const InternalToolsLabExplainer = lazyNamed(() => import("../pages/InternalTools/LabExplainer"), "LabExplainer");
const InternalToolsDataSharing = lazyNamed(() => import("../pages/InternalTools/DataSharing"), "DataSharing");
const InternalToolsAudit = lazyNamed(() => import("../pages/InternalTools/Audit"), "InternalToolsAudit");
const InternalToolsTrialFinder = lazyNamed(() => import("../pages/InternalTools/skills/TrialFinder"), "TrialFinder");
const InternalToolsPatientMemory = lazyNamed(() => import("../pages/InternalTools/skills/PatientMemory"), "PatientMemoryView");

export const atlasShellRoutes: ShellRoute[] = [
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
  { path: "/patient-record/workspaces", element: <PatientRecordWorkspaceRedirect /> },
  { path: "/patient-record/publish", element: <PatientRecordPublish /> },
  { path: "/patient-record/snapshots", element: <PatientRecordSnapshots /> },
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
  { path: "/learn/audit", element: <InternalToolsAudit /> },
  { path: "/learn/skills/trial-finder", element: <InternalToolsTrialFinder /> },
  { path: "/learn/skills/patients/memory", element: <InternalToolsPatientMemory /> },
];

export function isFullscreenWorkspacePath(pathname: string): boolean {
  return pathname.startsWith("/caspian") || pathname.startsWith("/workspaces/");
}

export function hasPatientScopedShellPath(pathname: string): boolean {
  return (
    pathname.startsWith("/patient-record") ||
    pathname.startsWith("/fhir-charts") ||
    pathname.startsWith("/caspian") ||
    pathname.startsWith("/workspaces")
  );
}

function PatientRecordWorkspaceRedirect() {
  const location = useLocation();
  return <Navigate to={`/patient-record${location.search}`} replace />;
}

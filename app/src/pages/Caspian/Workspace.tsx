import { useEffect, useMemo, useState } from "react";
import { useNavigate, useParams, useSearchParams } from "react-router-dom";
import { ShieldCheck } from "lucide-react";
import { AppShell } from "../../components/atlas/AppShell";
import { CaspianChatPane } from "../../components/atlas/CaspianChatPane";
import { DemoPatientPicker } from "../../components/atlas/DemoPatientPicker";
import { StartStateCard } from "../../components/atlas/StartStateCard";
import { WorkspaceFrame, type WorkspaceFrameControls } from "../../components/atlas/WorkspaceFrame";
import {
  WORKSPACES,
  type Session,
  type WorkbenchTab,
  type Workflow as WorkspaceWorkflow,
} from "../../components/atlas/data";
import { useCaspianAssistantSession } from "../../components/atlas/useCaspianAssistantSession";
import { useCaspianAgentSettings } from "../../components/atlas/useCaspianAgentSettings";
import { useCaspianFiles } from "../../components/atlas/useCaspianFiles";
import type { WorkflowId } from "../../types";

const CASPIAN_WORKFLOWS: WorkspaceWorkflow[] = [
  {
    id: "preop_review_v1",
    title: "Run pre-op review",
    desc: "Surfaces medication holds, anesthesia notes, recent labs, and clearance recommendation.",
    tags: ["pre-surgery", "evidence-grounded"],
  },
  {
    id: "medication_safety_v1",
    title: "Medication safety audit",
    desc: "Interactions, contraindications, dosing against renal function and active conditions.",
    tags: ["safety"],
  },
  {
    id: "longitudinal_synthesis_v1",
    title: "Longitudinal synthesis",
    desc: "Multi-year condition trajectory across encounters.",
    tags: ["narrative"],
  },
];

function buildFileTab(fileId: string): WorkbenchTab {
  const leaf = fileId.split("/").pop() ?? fileId;
  return {
    id: fileId,
    label: leaf,
    icon: iconForName(leaf),
    kind: "workspace-file",
    renderer: "workspace.file",
  };
}

function iconForName(name: string): string {
  if (name.endsWith(".json")) return "Braces";
  if (name.endsWith(".csv")) return "FileSpreadsheet";
  return "FileText";
}

export function CaspianWorkspace() {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const { sessionId } = useParams();
  const workspace = WORKSPACES["caspian"];
  const resolvedSessionId = sessionId ?? "current";
  const patientId = searchParams.get("patient");
  const sessions = useMemo(() => buildCaspianSessions(resolvedSessionId), [resolvedSessionId]);
  const activeSession = sessions[0] ?? null;
  const [paneControls, setPaneControls] = useState<WorkspaceFrameControls | null>(null);
  const files = useCaspianFiles(patientId);
  const agentSettings = useCaspianAgentSettings();
  const assistant = useCaspianAssistantSession(patientId, resolvedSessionId, {
    onFilesChanged: () => files.refetchTree(),
    agentSettings: agentSettings.settings,
  });

  // When a workflow run completes, route the newly produced artifact tab into
  // the workbench: open the tab (and the workbench pane if it is collapsed).
  // Also refresh the files tree so workflow-runs/<…>.md shows up.
  useEffect(() => {
    const tabId = assistant.workflow.latestTabId;
    if (!tabId || !paneControls) return;
    const tab = assistant.workflow.tabs.find((t) => t.id === tabId);
    if (!tab) return;
    paneControls.openTab(tab);
    if (!paneControls.panes.workbench) {
      paneControls.togglePane("workbench");
    }
    files.refetchTree();
    assistant.acknowledgeLatestWorkflow();
  }, [
    assistant.workflow.latestTabId,
    assistant.workflow.tabs,
    paneControls,
    files,
    assistant.acknowledgeLatestWorkflow,
  ]);

  // Build a merged canvas: workflow artifacts (keyed by their tab id) +
  // an `__files` envelope giving the file renderer access to the hook verbs.
  const baseCanvas = useMemo(() => {
    const merged: Record<string, unknown> = { ...assistant.workflow.canvas };
    merged.__files = {
      openFile: files.openFile,
      saveFile: files.saveFile,
      refreshFile: files.refreshFile,
      saveAsNote: files.saveAsNote,
    };
    return merged;
  }, [
    assistant.workflow.canvas,
    files.openFile,
    files.saveFile,
    files.refreshFile,
    files.saveAsNote,
  ]);

  // Layer the cached file blobs on top (keyed by file path === tab id).
  // Subscribes to files.openContent so the canvas updates as fetches resolve.
  const canvasWithFiles = useFilesIntoCanvas(baseCanvas, files);

  if (!patientId) {
    return (
      <AppShell
        contained={false}
        crumbs={[
          { label: "Caspian" },
          { label: "Start", active: true },
        ]}
      >
        <StartStateCard
          icon={ShieldCheck}
          eyebrow="Caspian"
          title="Choose a sample chart before opening Caspian."
          body="Caspian works best when it opens with a chart already selected. Pick a sample chart first so you can review the record, ask focused questions, and inspect supporting evidence in one place."
          bullets={[
            "Start with one chart so the conversation stays grounded in a single record.",
            "Keep answers, citations, and trace tied to the same review session.",
            "Avoid opening the full workspace before there is a chart to review.",
          ]}
          aside={
            <DemoPatientPicker
              destination={(demoPatientId) => `/caspian?patient=${encodeURIComponent(demoPatientId)}`}
              title="Open Caspian with a sample chart"
            />
          }
        />
      </AppShell>
    );
  }

  const triggerWorkflow = (workflowId: WorkflowId) => {
    assistant.runWorkflow(workflowId);
  };

  return (
    <AppShell
      contained={false}
      crumbs={[
        { label: "Caspian" },
        {
          label: activeSession?.title ?? "Session",
          active: true,
        },
      ]}
      showPaneToggles
      panes={paneControls?.panes}
      onTogglePane={(p) => paneControls?.togglePane(p)}
      onRunWorkflow={() => triggerWorkflow("preop_review_v1")}
    >
      <WorkspaceFrame
        workspace={workspace}
        activeSessionId={resolvedSessionId}
        onSelectSession={(id) => {
          if (id === "__home__") {
            navigate("/caspian");
            return;
          }
          navigate(`/caspian/sessions/${id}`);
        }}
        onControlsChange={setPaneControls}
        surface={{
          sessions,
          workflows: CASPIAN_WORKFLOWS,
          onRunWorkflow: (id) => triggerWorkflow(id as WorkflowId),
          pendingWorkflowId: assistant.workflow.pendingWorkflowId,
          seedTabs: assistant.workflow.tabs,
          canvas: canvasWithFiles,
          filesTree: files.tree,
          getFileTab: buildFileTab,
          chatPane: (
            <CaspianChatPane
              patientId={patientId}
              sessionTitle={activeSession?.title ?? "Session"}
              messages={assistant.messages}
              isPending={assistant.isPending || assistant.workflow.isPending}
              error={assistant.error ?? assistant.workflow.error}
              activeCitationId={paneControls?.activeCitationId ?? null}
              onSubmit={assistant.submitQuestion}
              onReset={assistant.resetConversation}
              agentSettings={agentSettings.settings}
              onUpdateAgentSettings={agentSettings.setSettings}
              onCitationClick={(id) => {
                paneControls?.focusCitation(id);
                paneControls?.setInspectorTab("evidence");
              }}
              onOpenTrace={() => {
                if (!paneControls?.panes.inspector) {
                  paneControls?.togglePane("inspector");
                }
                paneControls?.setInspectorTab("trace");
              }}
              onOpenFile={(path) => {
                const tab = buildFileTab(path);
                paneControls?.openTab(tab);
                if (!paneControls?.panes.workbench) {
                  paneControls?.togglePane("workbench");
                }
                // Kick off the read so the canvas blob lands.
                void files.openFile(path);
              }}
            />
          ),
          inspector: {
            patientId,
            citations: assistant.inspector.citations,
            trace: assistant.inspector.latestTrace,
            traceByCitationId: assistant.inspector.traceByCitationId,
            contextItems: assistant.inspector.contextItems,
          },
        }}
      />
    </AppShell>
  );
}

/**
 * Pull every file blob the hook has cached onto the canvas keyed by file path.
 * Subscribes to `files.openContent` so the canvas reference changes whenever
 * a blob is added or saved.
 */
function useFilesIntoCanvas(
  base: Record<string, unknown>,
  files: ReturnType<typeof useCaspianFiles>,
): Record<string, unknown> {
  const blobs = files.openContent;
  return useMemo(() => ({ ...base, ...blobs }), [base, blobs]);
}

function buildCaspianSessions(sessionId: string): Session[] {
  return [
    {
      id: sessionId,
      title: sessionId === "current" ? "Clinical review" : humanizeSessionId(sessionId),
      state: "running",
      meta: "active workspace session",
      workflow: "preop",
    },
  ];
}

function humanizeSessionId(sessionId: string): string {
  return sessionId
    .replace(/[-_]+/g, " ")
    .replace(/\b\w/g, (value) => value.toUpperCase());
}

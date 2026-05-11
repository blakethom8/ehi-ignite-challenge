import { useMemo, useState } from "react";
import { useNavigate, useParams, useSearchParams } from "react-router-dom";
import { ShieldCheck } from "lucide-react";
import { AppShell } from "../../components/atlas/AppShell";
import { CaspianChatPane } from "../../components/atlas/CaspianChatPane";
import { DemoPatientPicker } from "../../components/atlas/DemoPatientPicker";
import { StartStateCard } from "../../components/atlas/StartStateCard";
import { WorkspaceFrame, type WorkspaceFrameControls } from "../../components/atlas/WorkspaceFrame";
import { SESSIONS, WORKSPACES } from "../../components/atlas/data";
import { useCaspianAssistantSession } from "../../components/atlas/useCaspianAssistantSession";

export function CaspianWorkspace() {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const { sessionId } = useParams();
  const workspace = WORKSPACES["caspian"];
  const sessions = SESSIONS["caspian"];
  const defaultSessionId = sessions[0]?.id ?? null;
  const resolvedSessionId = sessionId ?? defaultSessionId;
  const patientId = searchParams.get("patient");
  const activeSession = useMemo(
    () => sessions.find((session) => session.id === resolvedSessionId) ?? sessions[0] ?? null,
    [resolvedSessionId, sessions],
  );
  const [paneControls, setPaneControls] = useState<WorkspaceFrameControls | null>(null);
  const assistant = useCaspianAssistantSession(patientId, resolvedSessionId);

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
          title="Choose a patient before opening the clinical workspace."
          body="Caspian should start as a focused clinical reasoning workspace with the patient context already in place. Select a demo patient first so the shell opens with a grounded chart, evidence flow, and live assistant session."
          bullets={[
            "Open the workspace only after the patient context is explicit.",
            "Keep citations, trace, and reasoning tied to one chart from the start.",
            "Avoid dropping first-time users into a dense five-pane shell with no patient selected.",
          ]}
          aside={
            <DemoPatientPicker
              destination={(demoPatientId) => `/caspian?patient=${encodeURIComponent(demoPatientId)}`}
              title="Open Caspian in demo mode"
            />
          }
        />
      </AppShell>
    );
  }

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
      onRunWorkflow={() => undefined}
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
          chatPane: (
            <CaspianChatPane
              patientId={patientId}
              sessionTitle={activeSession?.title ?? "Session"}
              messages={assistant.messages}
              isPending={assistant.isPending}
              error={assistant.error}
              activeCitationId={paneControls?.activeCitationId ?? null}
              onSubmit={assistant.submitQuestion}
              onReset={assistant.resetConversation}
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
            />
          ),
          inspector: {
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

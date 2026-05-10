import { useMemo, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { AppShell } from "../../components/atlas/AppShell";
import { WorkspaceFrame } from "../../components/atlas/WorkspaceFrame";
import { SESSIONS, WORKSPACES } from "../../components/atlas/data";
import type { PaneVisibility, WorkspaceId } from "../../components/atlas/types";

export function PluginWorkspace() {
  const navigate = useNavigate();
  const { pluginId = "trial-finder", sessionId } = useParams();
  const workspace =
    WORKSPACES[pluginId as WorkspaceId] ?? WORKSPACES["trial-finder"];
  const sessions = SESSIONS[workspace.id] ?? [];
  const defaultSessionId = sessions[0]?.id ?? null;
  const activeSession = useMemo(
    () => sessions.find((session) => session.id === sessionId) ?? null,
    [sessionId, sessions],
  );
  const [paneControls, setPaneControls] = useState<{
    panes: PaneVisibility;
    togglePane: (p: keyof PaneVisibility) => void;
  } | null>(null);

  return (
    <AppShell
      contained={false}
      crumbs={[
        { label: "Workspaces" },
        { label: workspace.title },
        sessionId
          ? { label: activeSession?.title ?? sessionId, active: true }
          : { label: "Package home", active: true },
      ]}
      showPaneToggles
      panes={paneControls?.panes}
      onTogglePane={(p) => paneControls?.togglePane(p)}
      onRunWorkflow={() => undefined}
    >
      <WorkspaceFrame
        workspace={workspace}
        activeSessionId={sessionId ?? "__home__"}
        onSelectSession={(id) => {
          if (id === "__home__") {
            navigate(`/workspaces/${workspace.id}`);
            return;
          }
          navigate(`/workspaces/${workspace.id}/sessions/${id}`);
        }}
        showPluginHome={!sessionId}
        onStartRun={() => {
          if (defaultSessionId) {
            navigate(`/workspaces/${workspace.id}/sessions/${defaultSessionId}`);
          }
        }}
        onControlsChange={setPaneControls}
      />
    </AppShell>
  );
}

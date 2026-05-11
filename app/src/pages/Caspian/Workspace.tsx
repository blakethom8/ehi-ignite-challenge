import { useMemo, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { AppShell } from "../../components/atlas/AppShell";
import { WorkspaceFrame } from "../../components/atlas/WorkspaceFrame";
import { SESSIONS, WORKSPACES } from "../../components/atlas/data";
import type { PaneVisibility } from "../../components/atlas/types";

export function CaspianWorkspace() {
  const navigate = useNavigate();
  const { sessionId } = useParams();
  const workspace = WORKSPACES["caspian"];
  const sessions = SESSIONS["caspian"];
  const defaultSessionId = sessions[0]?.id ?? null;
  const resolvedSessionId = sessionId ?? defaultSessionId;
  const activeSession = useMemo(
    () => sessions.find((session) => session.id === resolvedSessionId) ?? sessions[0] ?? null,
    [resolvedSessionId, sessions],
  );
  const [paneControls, setPaneControls] = useState<{
    panes: PaneVisibility;
    togglePane: (p: keyof PaneVisibility) => void;
  } | null>(null);

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
      />
    </AppShell>
  );
}

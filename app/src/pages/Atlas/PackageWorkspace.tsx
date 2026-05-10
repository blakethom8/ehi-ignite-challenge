import { useRef, useState } from "react";
import { useParams } from "react-router-dom";
import { AppShell } from "../../components/atlas/AppShell";
import { WorkspaceFrame } from "../../components/atlas/WorkspaceFrame";
import { WORKSPACES } from "../../components/atlas/data";
import type { PaneVisibility, WorkspaceId } from "../../components/atlas/types";

export function PackageWorkspace() {
  const { packageId = "trial-finder", sessionId } = useParams();
  const workspace =
    WORKSPACES[packageId as WorkspaceId] ?? WORKSPACES["trial-finder"];
  const controlsRef = useRef<{
    panes: PaneVisibility;
    togglePane: (p: keyof PaneVisibility) => void;
  } | null>(null);
  const [, force] = useState(0);

  return (
    <AppShell
      contained={false}
      crumbs={[
        { label: "Workspaces" },
        { label: workspace.title },
        sessionId
          ? { label: sessionId, active: true }
          : { label: "Package home", active: true },
      ]}
      showPaneToggles
      panes={controlsRef.current?.panes}
      onTogglePane={(p) => {
        controlsRef.current?.togglePane(p);
        force((n) => n + 1);
      }}
      onRunWorkflow={() => undefined}
    >
      <WorkspaceFrame
        workspace={workspace}
        showPackageHome={!sessionId}
        controlsRef={controlsRef}
      />
    </AppShell>
  );
}

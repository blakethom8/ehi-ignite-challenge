import { useRef, useState } from "react";
import { AppShell } from "../../components/atlas/AppShell";
import { WorkspaceFrame } from "../../components/atlas/WorkspaceFrame";
import { WORKSPACES } from "../../components/atlas/data";
import type { PaneVisibility } from "../../components/atlas/types";

export function CaspianWorkspace() {
  const workspace = WORKSPACES["caspian"];
  const controlsRef = useRef<{
    panes: PaneVisibility;
    togglePane: (p: keyof PaneVisibility) => void;
  } | null>(null);
  const [, force] = useState(0);

  return (
    <AppShell
      contained={false}
      crumbs={[
        { label: "Caspian" },
        { label: "Pre-op clearance — Hollister", active: true },
      ]}
      showPaneToggles
      panes={controlsRef.current?.panes}
      onTogglePane={(p) => {
        controlsRef.current?.togglePane(p);
        force((n) => n + 1);
      }}
      onRunWorkflow={() => undefined}
    >
      <WorkspaceFrame workspace={workspace} controlsRef={controlsRef} />
    </AppShell>
  );
}

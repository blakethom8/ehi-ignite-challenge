import { useParams } from "react-router-dom";
import { AppShell } from "../../components/atlas/AppShell";
import { PlaceholderShell } from "./PlaceholderShell";

export function PackageWorkspace() {
  const { packageId = "trial-finder" } = useParams();
  return (
    <AppShell
      contained={false}
      crumbs={[
        { label: "Workspaces" },
        { label: packageId, active: true },
      ]}
      showPaneToggles
      onRunWorkflow={() => undefined}
    >
      <PlaceholderShell
        eyebrow={`Marketplace package · ${packageId}`}
        title="The package workspace shell lands here in Phase 3"
        body="Marketplace packages enter on a package home (permissions ledger, workflows, recent runs). Starting a workflow opens the active session view inside the same shell."
        ctaLabel="Open the legacy Trial Finder workspace"
        ctaHref="/ai-workspace/trial-finder"
      />
    </AppShell>
  );
}

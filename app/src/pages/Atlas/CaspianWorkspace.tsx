import { AppShell } from "../../components/atlas/AppShell";
import { PlaceholderShell } from "./PlaceholderShell";

export function CaspianWorkspace() {
  return (
    <AppShell
      contained={false}
      crumbs={[
        { label: "Caspian" },
        { label: "Pre-op clearance — Hollister", active: true },
      ]}
      showPaneToggles
      onRunWorkflow={() => undefined}
    >
      <PlaceholderShell
        eyebrow="First-party workspace · Caspian"
        title="The clinical workspace lands here in Phase 3"
        body="Caspian is the first-party agentic workspace. Phase 3 brings the five-pane shell: sessions, chat, workbench, files, inspector. The dark chrome above is final."
        ctaLabel="Open the legacy Clinical Insights view"
        ctaHref="/clinical-insights"
      />
    </AppShell>
  );
}

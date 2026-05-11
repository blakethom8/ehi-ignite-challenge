import { useEffect, useState } from "react";
import { useMatch, useNavigate, useParams } from "react-router-dom";
import { AppShell } from "../../components/atlas/AppShell";
import { PluginRunPanel } from "../../components/atlas/PluginRunPanel";
import { WorkspaceFrame } from "../../components/atlas/WorkspaceFrame";
import { useManifest } from "../../components/atlas/manifests";
import { pluginsApi } from "../../api/plugins";
import { WORKSPACES } from "../../components/atlas/data";
import type { PaneVisibility, WorkspaceId } from "../../components/atlas/types";

/**
 * Plugin workspace route container.
 *
 * /workspaces/:pluginId               → PluginHome via WorkspaceFrame
 * /workspaces/:pluginId/sessions/r_*  → live PluginRunPanel against the backend
 * /workspaces/:pluginId/sessions/X    → legacy WorkspaceFrame (fixture sessions)
 */
export function PluginWorkspace() {
  const navigate = useNavigate();
  const { pluginId = "trial-finder", sessionId } = useParams();
  const sessionRouteMatch = useMatch("/workspaces/:pluginId/sessions/:sessionId");
  const effectiveSessionId = sessionRouteMatch?.params.sessionId ?? sessionId;
  const workspace = WORKSPACES[pluginId as WorkspaceId] ?? WORKSPACES["trial-finder"];
  const manifestQuery = useManifest(pluginId);
  const [paneControls, setPaneControls] = useState<{
    panes: PaneVisibility;
    togglePane: (p: keyof PaneVisibility) => void;
  } | null>(null);
  const [starting, setStarting] = useState(false);
  const [startError, setStartError] = useState<string | null>(null);

  const isLiveRun = Boolean(effectiveSessionId && effectiveSessionId.startsWith("r_"));
  const openPluginPath = (path: string) => {
    window.location.assign(path);
  };

  // Auto-start a backend run when the user clicked "Start" from PluginHome.
  // PluginHome calls onStartRun() with a workflowId; we POST the run and
  // navigate to its live route.
  const onStartRun = async (workflowId?: string) => {
    if (!manifestQuery.data || starting) return;
    setStarting(true);
    setStartError(null);
    try {
      const run = await pluginsApi.startRun({
        pluginId: manifestQuery.data.id,
        workflowId,
        title: workflowId
          ? `${workflowId} — ${manifestQuery.data.displayName}`
          : `Run — ${manifestQuery.data.displayName}`,
      });
      openPluginPath(`/workspaces/${manifestQuery.data.id}/sessions/${run.id}`);
    } catch (e: unknown) {
      setStartError(e instanceof Error ? e.message : String(e));
    } finally {
      setStarting(false);
    }
  };

  // Defensive: navigate home if pluginId isn't a real manifest.
  useEffect(() => {
    if (!manifestQuery.isLoading && manifestQuery.isError && !manifestQuery.data) {
      // Stay on page; show the error rather than redirecting silently.
    }
  }, [manifestQuery]);

  return (
    <AppShell
      contained={false}
      crumbs={[
        { label: "Workspaces" },
        { label: manifestQuery.data?.displayName ?? workspace.title },
        effectiveSessionId
          ? { label: isLiveRun ? `Run ${effectiveSessionId}` : effectiveSessionId, active: true }
          : { label: "Plugin home", active: true },
      ]}
      showPaneToggles
      panes={paneControls?.panes}
      onTogglePane={(p) => paneControls?.togglePane(p)}
      onRunWorkflow={() => undefined}
    >
      {isLiveRun && manifestQuery.data ? (
        <PluginRunPanel
          manifest={manifestQuery.data}
          runId={effectiveSessionId as string}
          onRevoke={() => undefined}
        />
      ) : (
        <>
          {startError && (
            <div
              className="absolute left-1/2 top-16 z-50 -translate-x-1/2 rounded border px-3 py-2 text-[12px]"
              style={{ background: "rgba(220,38,38,0.08)", borderColor: "rgba(220,38,38,0.4)", color: "var(--ink-1)" }}
            >
              Failed to start run: {startError}
            </div>
          )}
          <WorkspaceFrame
            workspace={workspace}
            activeSessionId={effectiveSessionId ?? "__home__"}
            onSelectSession={(id) => {
              if (id === "__home__") {
                navigate(`/workspaces/${workspace.id}`);
                return;
              }
              openPluginPath(`/workspaces/${workspace.id}/sessions/${id}`);
            }}
            showPluginHome={!effectiveSessionId}
            onStartRun={(workflowId) => {
              void onStartRun(workflowId);
            }}
            onControlsChange={setPaneControls}
          />
        </>
      )}
    </AppShell>
  );
}

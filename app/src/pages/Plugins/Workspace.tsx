import { useEffect, useMemo, useState } from "react";
import { useMatch, useNavigate, useParams, useSearchParams } from "react-router-dom";
import { AppShell } from "../../components/atlas/AppShell";
import { PluginRunChatPane } from "../../components/atlas/PluginRunChatPane";
import { WorkspaceFrame, type WorkspaceFrameControls } from "../../components/atlas/WorkspaceFrame";
import { useManifest, useRunsForPlugin } from "../../components/atlas/manifests";
import {
  buildPluginRunSessions,
  buildPluginRunWorkspaceSurface,
  buildPluginWorkspaceScaffold,
} from "../../components/atlas/pluginRunWorkspace";
import { usePluginRun } from "../../components/atlas/usePluginRun";
import { pluginsApi } from "../../api/plugins";
import { WORKSPACES } from "../../components/atlas/data";
import type { WorkspaceId } from "../../components/atlas/types";

/**
 * Plugin workspace route container.
 *
 * /workspaces/:pluginId               → PluginHome via WorkspaceFrame
 * /workspaces/:pluginId/sessions/r_*  → live backend run inside WorkspaceFrame
 * /workspaces/:pluginId/sessions/X    → fixture/demo session inside WorkspaceFrame
 */
export function PluginWorkspace() {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const { pluginId = "trial-finder", sessionId } = useParams();
  const sessionRouteMatch = useMatch("/workspaces/:pluginId/sessions/:sessionId");
  const effectiveSessionId = sessionRouteMatch?.params.sessionId ?? sessionId;
  const workspace = WORKSPACES[pluginId as WorkspaceId] ?? WORKSPACES["trial-finder"];
  const manifestQuery = useManifest(pluginId);
  const runsQuery = useRunsForPlugin(pluginId);
  const [paneControls, setPaneControls] = useState<WorkspaceFrameControls | null>(null);
  const [starting, setStarting] = useState(false);
  const [startError, setStartError] = useState<string | null>(null);
  const patientId = searchParams.get("patient");

  const isLiveRun = Boolean(effectiveSessionId && effectiveSessionId.startsWith("r_"));
  const liveRunBundle = usePluginRun(isLiveRun ? (effectiveSessionId as string) : null);
  const openPluginPath = (path: string) => {
    const next = new URL(path, window.location.origin);
    if (patientId && !next.searchParams.has("patient")) {
      next.searchParams.set("patient", patientId);
    }
    window.location.assign(`${next.pathname}${next.search}`);
  };

  // Auto-start a backend run when the user clicked "Start" from PluginHome.
  // PluginHome calls onStartRun() with a workflowId; we POST the run and
  // navigate to its live route.
  const onStartRun = async (workflowId?: string) => {
    if (!manifestQuery.data || starting) return;
    if (!patientId) {
      setStartError("Choose a patient before starting this workflow.");
      return;
    }
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

  const liveSurface = useMemo(() => {
    if (!isLiveRun || !manifestQuery.data || !liveRunBundle.run) return null;
    return buildPluginRunWorkspaceSurface({
      manifest: manifestQuery.data,
      run: liveRunBundle.run,
      runs: runsQuery.data ?? [],
      events: liveRunBundle.events,
      approvals: liveRunBundle.approvals,
      canvas: liveRunBundle.canvas,
    });
  }, [isLiveRun, liveRunBundle.approvals, liveRunBundle.canvas, liveRunBundle.events, liveRunBundle.run, manifestQuery.data, runsQuery.data]);

  const liveScaffold = useMemo(
    () =>
      isLiveRun && manifestQuery.data
        ? buildPluginWorkspaceScaffold(manifestQuery.data)
        : null,
    [isLiveRun, manifestQuery.data],
  );

  const resolvedWorkspace = liveSurface?.workspace ?? workspace;

  return (
    <AppShell
      contained={false}
      crumbs={[
        { label: "Workspaces" },
        { label: manifestQuery.data?.displayName ?? resolvedWorkspace.title },
        effectiveSessionId
          ? { label: isLiveRun ? `Run ${effectiveSessionId}` : effectiveSessionId, active: true }
          : { label: "Plugin home", active: true },
      ]}
      showPaneToggles
      panes={paneControls?.panes}
      onTogglePane={(p) => paneControls?.togglePane(p)}
      onRunWorkflow={() => undefined}
    >
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
          workspace={resolvedWorkspace}
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
          surface={
            manifestQuery.data && (liveSurface || liveScaffold)
              ? {
                  chatPane: (
                    <PluginRunChatPane
                      manifest={manifestQuery.data}
                      runId={effectiveSessionId as string}
                      bundle={liveRunBundle}
                      onOpenArtifact={(tab) => {
                        paneControls?.togglePane("workbench");
                        paneControls?.openTab(tab);
                      }}
                    />
                  ),
                  sessions:
                    !effectiveSessionId && runsQuery.data
                      ? buildPluginRunSessions(runsQuery.data)
                      : liveSurface?.sessions,
                  filesTree: liveSurface?.filesTree ?? liveScaffold?.filesTree,
                  seedTabs: liveSurface?.tabs ?? liveScaffold?.tabs,
                  canvas: liveSurface?.canvas ?? liveScaffold?.canvas,
                  runId: effectiveSessionId as string,
                  getFileTab: (fileId) =>
                    liveSurface?.fileTabs[fileId] ??
                    liveScaffold?.fileTabs[fileId] ??
                    null,
                  pluginHome: {
                    canStartRun: Boolean(patientId),
                    startHint: patientId
                      ? undefined
                      : "Choose a patient before starting a workspace run.",
                  },
                }
              : undefined
          }
        />
      </>
    </AppShell>
  );
}

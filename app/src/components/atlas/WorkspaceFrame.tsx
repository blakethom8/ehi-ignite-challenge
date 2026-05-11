import { type ReactNode, useCallback, useEffect, useMemo, useRef, useState } from "react";
import { ChatPane } from "./ChatPane";
import { ContextStrip } from "./ContextStrip";
import type { FileTreeNode, Session, WorkbenchTab, Workflow } from "./data";
import { FilesPane } from "./FilesPane";
import { InspectorPane } from "./InspectorPane";
import { PluginHome } from "./PluginHome";
import { SessionsPane } from "./SessionsPane";
import { WorkbenchPane } from "./WorkbenchPane";
import { useManifest } from "./manifests";
import { useWorkspaceState } from "./useWorkspaceState";
import type { PaneSizes, Workspace } from "./types";
import type { Citation } from "./data";
import type { TraceDetail } from "../../types";
import type { InspectorContextItem } from "./InspectorPane";

const MIN_SIZES: Record<keyof PaneSizes, number> = {
  sessionsW: 200,
  chatW: 320,
  rightW: 240,
  filesH: 15,
};

const MAX_SIZES: Record<keyof PaneSizes, number> = {
  sessionsW: 480,
  chatW: 720,
  rightW: 520,
  filesH: 85,
};

type WorkspaceFrameProps = {
  workspace: Workspace;
  /** Forces showing the package home view instead of the active session. */
  showPluginHome?: boolean;
  /** Optional route-driven active session id. */
  activeSessionId?: string | "__home__" | null;
  /** Optional route-driven session switcher. */
  onSelectSession?: (id: string | "__home__") => void;
  /** Optional route-driven run launcher. */
  onStartRun?: (workflowId?: string) => void;
  /** Map external pane controls into the frame. */
  onControlsChange?: (controls: {
    panes: ReturnType<typeof useWorkspaceState>["panes"];
    togglePane: ReturnType<typeof useWorkspaceState>["togglePane"];
    openTab: ReturnType<typeof useWorkspaceState>["openTab"];
    focusCitation: ReturnType<typeof useWorkspaceState>["handleCitation"];
    activeCitationId: ReturnType<typeof useWorkspaceState>["citationId"];
    setInspectorTab: ReturnType<typeof useWorkspaceState>["setInspectorTab"];
  }) => void;
  /** Optional live/runtime surface that replaces fixture-backed content within the shared shell. */
  surface?: {
    chatPane?: ReactNode;
    sessions?: Session[];
    workflows?: Workflow[];
    filesTree?: FileTreeNode[];
    seedTabs?: WorkbenchTab[];
    canvas?: Record<string, unknown>;
    runId?: string | null;
    getFileTab?: (fileId: string) => WorkbenchTab | null;
    getActionTab?: (target: string) => WorkbenchTab | null;
    pluginHome?: {
      canStartRun?: boolean;
      startHint?: string;
    };
    inspector?: {
      citations?: Record<string, Citation>;
      trace?: TraceDetail | null;
      traceByCitationId?: Record<string, TraceDetail | null>;
      contextItems?: InspectorContextItem[];
    };
  };
};

export type WorkspaceFrameControls = NonNullable<WorkspaceFrameProps["onControlsChange"]> extends (
  controls: infer T,
) => void
  ? T
  : never;

export function WorkspaceFrame({
  workspace,
  showPluginHome,
  activeSessionId,
  onSelectSession,
  onStartRun,
  onControlsChange,
  surface,
}: WorkspaceFrameProps) {
  const state = useWorkspaceState(workspace.id, {
    seedTabs: surface?.seedTabs,
    canvas: surface?.canvas,
    filesTree: surface?.filesTree,
    getFileTab: surface?.getFileTab,
    getActionTab: surface?.getActionTab,
  });
  const isPlugin = workspace.family === "plugin";
  const manifestQuery = useManifest(isPlugin ? workspace.id : undefined);
  const stageRef = useRef<HTMLDivElement>(null);
  const rightStackRef = useRef<HTMLDivElement>(null);
  const [stageWidth, setStageWidth] = useState(0);

  useEffect(() => {
    const node = stageRef.current;
    if (!node) return;
    const syncWidth = () => {
      setStageWidth(node.getBoundingClientRect().width);
    };
    syncWidth();
    const observer = new ResizeObserver(syncWidth);
    observer.observe(node);
    return () => observer.disconnect();
  }, []);

  const responsivePanes = useMemo(() => {
    const next = { ...state.panes };
    if (!showPluginHome && stageWidth > 0) {
      if (stageWidth < 1180) {
        if (next.files || next.inspector) {
          const preferred =
            state.rightPaneFocus === "inspector" && next.inspector
              ? "inspector"
              : next.files
                ? "files"
                : "inspector";
          next.files = preferred === "files" && next.files;
          next.inspector = preferred === "inspector" && next.inspector;
        }
      }
      if (stageWidth < 900 && next.chat && next.workbench) {
        next.sessions = false;
      }
    }
    return next;
  }, [showPluginHome, stageWidth, state.panes, state.rightPaneFocus]);

  const handlePaneControl = useCallback(
    (pane: keyof typeof state.panes) => {
      if (
        (pane === "files" || pane === "inspector") &&
        stageWidth > 0 &&
        stageWidth < 1180 &&
        state.panes.files &&
        state.panes.inspector &&
        state.panes[pane] &&
        state.rightPaneFocus !== pane
      ) {
        state.showPane(pane);
        return;
      }
      state.togglePane(pane);
    },
    [stageWidth, state],
  );

  useEffect(() => {
    onControlsChange?.({
      panes: responsivePanes,
      togglePane: handlePaneControl,
      openTab: state.openTab,
      focusCitation: state.handleCitation,
      activeCitationId: state.citationId,
      setInspectorTab: state.setInspectorTab,
    });
  }, [handlePaneControl, onControlsChange, responsivePanes, state.citationId, state.handleCitation, state.openTab, state.setInspectorTab]);

  const onDragStart = useCallback(
    (axis: "v" | "h", key: keyof PaneSizes) =>
      (e: React.MouseEvent) => {
        e.preventDefault();
        const startX = e.clientX;
        const start = state.sizes[key];
        document.body.classList.add(
          axis === "v" ? "atlas-resizing-v" : "atlas-resizing-h",
        );
        const onMove = (ev: MouseEvent) => {
          if (axis === "v") {
            let delta = ev.clientX - startX;
            if (key === "rightW") delta = -delta;
            const next = Math.max(
              MIN_SIZES[key],
              Math.min(MAX_SIZES[key], start + delta),
            );
            state.setSizes((s) => ({ ...s, [key]: next }));
          } else {
            const rect = rightStackRef.current?.getBoundingClientRect();
            if (!rect) return;
            const pct = Math.max(
              MIN_SIZES.filesH,
              Math.min(
                MAX_SIZES.filesH,
                ((ev.clientY - rect.top) / rect.height) * 100,
              ),
            );
            state.setSizes((s) => ({ ...s, filesH: pct }));
          }
        };
        const onUp = () => {
          document.body.classList.remove("atlas-resizing-v", "atlas-resizing-h");
          window.removeEventListener("mousemove", onMove);
          window.removeEventListener("mouseup", onUp);
        };
        window.addEventListener("mousemove", onMove);
        window.addEventListener("mouseup", onUp);
      },
    [state],
  );

  const showRightStack = responsivePanes.files || responsivePanes.inspector;
  const showActiveSession = !showPluginHome;
  const resolvedSessionId =
    activeSessionId ?? state.activeSessionId;
  useEffect(() => {
    if (activeSessionId === undefined) return;
    state.setActiveSessionId(activeSessionId === "__home__" ? null : activeSessionId);
  }, [activeSessionId, state.setActiveSessionId]);
  const handleSelectSession =
    onSelectSession ??
    ((id: string | "__home__") =>
      state.setActiveSessionId(id === "__home__" ? null : id));
  const handleStartRun = onStartRun ?? (() => state.setActiveSessionId(null));
  const sessionsWidth =
    stageWidth > 0
      ? Math.min(
          state.sizes.sessionsW,
          Math.max(MIN_SIZES.sessionsW, Math.floor(stageWidth * 0.28)),
        )
      : state.sizes.sessionsW;
  const chatWidth =
    responsivePanes.chat && responsivePanes.workbench && stageWidth > 0
      ? Math.min(
          state.sizes.chatW,
          Math.max(
            MIN_SIZES.chatW,
            Math.floor(stageWidth * (showRightStack ? 0.38 : 0.44)),
          ),
        )
      : state.sizes.chatW;
  const rightWidth =
    showRightStack && stageWidth > 0
      ? Math.min(
          state.sizes.rightW,
          Math.max(220, Math.floor(stageWidth * 0.28)),
        )
      : state.sizes.rightW;

  return (
    <div
      className="flex min-h-0 flex-1 flex-col overflow-hidden"
      style={{ background: "var(--bg-app)" }}
    >
      <ContextStrip workspace={workspace} />
      <div
        ref={stageRef}
        className="flex min-h-0 flex-1 overflow-hidden"
        style={{ background: "var(--bg-app)" }}
      >
        {responsivePanes.sessions && (
          <>
            <div
              style={{
                width: sessionsWidth,
                flex: "0 0 auto",
                minWidth: MIN_SIZES.sessionsW,
              }}
            >
              <SessionsPane
                workspace={workspace}
                sessions={surface?.sessions}
                workflows={surface?.workflows}
                activeSessionId={showPluginHome ? "__home__" : resolvedSessionId}
                onSelectSession={handleSelectSession}
              />
            </div>
            <div
              className="atlas-resizer-v"
              onMouseDown={onDragStart("v", "sessionsW")}
            />
          </>
        )}
        {showActiveSession ? (
          <>
            {responsivePanes.chat && (
              <div
                style={{
                  width: chatWidth,
                  flex: responsivePanes.workbench ? "0 0 auto" : "1 1 auto",
                  minWidth: MIN_SIZES.chatW,
                }}
                className="min-h-0"
              >
                {surface?.chatPane ?? (
                  <ChatPane
                    workspace={workspace}
                    messages={state.chats[workspace.id] ?? []}
                    onSend={state.handleSend}
                    onCitationClick={state.handleCitation}
                    onReferenceClick={state.handleReference}
                    onAction={state.handleAction}
                    activeCitationId={state.citationId}
                  />
                )}
              </div>
            )}
            {responsivePanes.chat && responsivePanes.workbench && (
              <div
                className="atlas-resizer-v"
                onMouseDown={onDragStart("v", "chatW")}
              />
            )}
            {responsivePanes.workbench && (
              <div className="min-h-0 flex-1">
                <WorkbenchPane
                  workspace={workspace}
                  tabs={state.tabs}
                  activeTabId={state.activeTabId}
                  onSelectTab={state.handleSelectTab}
                  onCloseTab={state.handleCloseTab}
                  onCitationClick={state.handleCitation}
                  activeCitationId={state.citationId}
                  runId={surface?.runId ?? null}
                  canvas={state.canvas}
                />
              </div>
            )}
            {showRightStack && (responsivePanes.chat || responsivePanes.workbench) && (
              <div
                className="atlas-resizer-v"
                onMouseDown={onDragStart("v", "rightW")}
              />
            )}
            {showRightStack && (
              <div
                ref={rightStackRef}
                className="min-h-0"
                style={{
                  width: rightWidth,
                  flex: "0 0 auto",
                  minWidth: MIN_SIZES.rightW,
                  display: "grid",
                  gridTemplateRows:
                    responsivePanes.files && responsivePanes.inspector
                      ? `${state.sizes.filesH}% 5px ${100 - state.sizes.filesH}%`
                      : "1fr",
                  borderLeft: "1px solid var(--line-1)",
                  background: "var(--surface-1)",
                }}
              >
                {responsivePanes.files && (
                <FilesPane
                  workspaceId={workspace.id}
                  onOpen={state.handleOpenFile}
                  activeFileId={state.activeFileId}
                  tree={surface?.filesTree}
                />
                )}
                {responsivePanes.files && responsivePanes.inspector && (
                  <div
                    className="atlas-resizer-h"
                    onMouseDown={onDragStart("h", "filesH")}
                  />
                )}
                {responsivePanes.inspector && (
                  <InspectorPane
                    citationId={state.citationId}
                    activeTab={state.inspectorTab}
                    onTabChange={state.setInspectorTab}
                    citations={surface?.inspector?.citations}
                    trace={surface?.inspector?.trace}
                    traceByCitationId={surface?.inspector?.traceByCitationId}
                    contextItems={surface?.inspector?.contextItems}
                  />
                )}
              </div>
            )}
          </>
        ) : (
          manifestQuery.data ? (
            <PluginHome
              manifest={manifestQuery.data}
              onStartRun={(workflowId) => handleStartRun(workflowId)}
              canStartRun={surface?.pluginHome?.canStartRun}
              startHint={surface?.pluginHome?.startHint}
            />
          ) : (
            <div
              className="grid h-full place-items-center text-[12.5px]"
              style={{ color: "var(--ink-3)" }}
            >
              {manifestQuery.isLoading
                ? "Loading plugin manifest…"
                : `Plugin not installed: ${workspace.id}`}
            </div>
          )
        )}
      </div>
    </div>
  );
}

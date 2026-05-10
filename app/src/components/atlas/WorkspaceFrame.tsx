import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { ChatPane } from "./ChatPane";
import { ContextStrip } from "./ContextStrip";
import { FilesPane } from "./FilesPane";
import { InspectorPane } from "./InspectorPane";
import { PluginHome } from "./PluginHome";
import { SessionsPane } from "./SessionsPane";
import { WorkbenchPane } from "./WorkbenchPane";
import { useWorkspaceState } from "./useWorkspaceState";
import type { PaneSizes, Workspace } from "./types";

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
  onStartRun?: () => void;
  /** Map external pane controls into the frame. */
  onControlsChange?: (controls: {
    panes: ReturnType<typeof useWorkspaceState>["panes"];
    togglePane: ReturnType<typeof useWorkspaceState>["togglePane"];
  }) => void;
};

export function WorkspaceFrame({
  workspace,
  showPluginHome,
  activeSessionId,
  onSelectSession,
  onStartRun,
  onControlsChange,
}: WorkspaceFrameProps) {
  const state = useWorkspaceState(workspace.id);
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
    });
  }, [handlePaneControl, onControlsChange, responsivePanes]);

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
                <ChatPane
                  workspace={workspace}
                  messages={state.chats[workspace.id] ?? []}
                  onSend={state.handleSend}
                  onCitationClick={state.handleCitation}
                  onAction={state.handleAction}
                  activeCitationId={state.citationId}
                />
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
                />
                )}
                {responsivePanes.files && responsivePanes.inspector && (
                  <div
                    className="atlas-resizer-h"
                    onMouseDown={onDragStart("h", "filesH")}
                  />
                )}
                {responsivePanes.inspector && (
                  <InspectorPane citationId={state.citationId} />
                )}
              </div>
            )}
          </>
        ) : (
          <PluginHome
            workspace={workspace}
            onStartRun={handleStartRun}
          />
        )}
      </div>
    </div>
  );
}

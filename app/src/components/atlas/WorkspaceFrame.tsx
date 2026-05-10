import { useCallback, useRef } from "react";
import { ChatPane } from "./ChatPane";
import { ContextStrip } from "./ContextStrip";
import { FilesPane } from "./FilesPane";
import { InspectorPane } from "./InspectorPane";
import { PackageHome } from "./PackageHome";
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
  showPackageHome?: boolean;
  /** Map external pane controls into the frame. */
  controlsRef?: React.MutableRefObject<{
    panes: ReturnType<typeof useWorkspaceState>["panes"];
    togglePane: ReturnType<typeof useWorkspaceState>["togglePane"];
  } | null>;
};

export function WorkspaceFrame({
  workspace,
  showPackageHome,
  controlsRef,
}: WorkspaceFrameProps) {
  const state = useWorkspaceState(workspace.id);
  const stageRef = useRef<HTMLDivElement>(null);
  const rightStackRef = useRef<HTMLDivElement>(null);

  if (controlsRef) {
    controlsRef.current = { panes: state.panes, togglePane: state.togglePane };
  }

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

  const showRightStack = state.panes.files || state.panes.inspector;
  const showActiveSession = !showPackageHome;

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
        {state.panes.sessions && (
          <>
            <div
              style={{
                width: state.sizes.sessionsW,
                flex: "0 0 auto",
                minWidth: MIN_SIZES.sessionsW,
              }}
            >
              <SessionsPane
                workspace={workspace}
                activeSessionId={
                  showPackageHome ? "__home__" : state.activeSessionId
                }
                onSelectSession={(id) => state.setActiveSessionId(id === "__home__" ? null : id)}
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
            {state.panes.chat && (
              <div
                style={{
                  width: state.sizes.chatW,
                  flex: state.panes.workbench ? "0 0 auto" : "1 1 auto",
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
            {state.panes.chat && state.panes.workbench && (
              <div
                className="atlas-resizer-v"
                onMouseDown={onDragStart("v", "chatW")}
              />
            )}
            {state.panes.workbench && (
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
            {showRightStack && (state.panes.chat || state.panes.workbench) && (
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
                  width: state.sizes.rightW,
                  flex: "0 0 auto",
                  minWidth: MIN_SIZES.rightW,
                  display: "grid",
                  gridTemplateRows:
                    state.panes.files && state.panes.inspector
                      ? `${state.sizes.filesH}% 5px ${100 - state.sizes.filesH}%`
                      : "1fr",
                  borderLeft: "1px solid var(--line-1)",
                  background: "var(--surface-1)",
                }}
              >
                {state.panes.files && (
                  <FilesPane
                    workspaceId={workspace.id}
                    onOpen={state.handleOpenFile}
                  />
                )}
                {state.panes.files && state.panes.inspector && (
                  <div
                    className="atlas-resizer-h"
                    onMouseDown={onDragStart("h", "filesH")}
                  />
                )}
                {state.panes.inspector && (
                  <InspectorPane citationId={state.citationId} />
                )}
              </div>
            )}
          </>
        ) : (
          <PackageHome
            workspace={workspace}
            onStartRun={() => state.setActiveSessionId(null)}
          />
        )}
      </div>
    </div>
  );
}

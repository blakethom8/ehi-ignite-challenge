import { useCallback, useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import { Link } from "react-router-dom";
import {
  ArrowLeft,
  ChevronsLeft,
  ChevronsRight,
  Info,
  Maximize2,
  Minimize2,
  PanelLeftClose,
  RotateCcw,
  X,
} from "lucide-react";
import type { WorkspaceDefinition, WorkspaceSurfaceDefinition } from "./contracts";

type SurfaceLayout = {
  open: boolean;
  collapsed: boolean;
  width: number;
};

type LayoutState = Record<string, SurfaceLayout>;

type WorkspaceFrameProps = {
  definition: WorkspaceDefinition;
  storageKey: string;
  renderSurface: (surface: WorkspaceSurfaceDefinition) => ReactNode;
};

function defaultLayout(definition: WorkspaceDefinition): LayoutState {
  return Object.fromEntries(
    definition.defaultSurfaces.map((surface) => [
      surface.id,
      {
        open: surface.defaultOpen,
        collapsed: false,
        width: surface.defaultWidth,
      },
    ]),
  );
}

function loadLayout(storageKey: string, definition: WorkspaceDefinition): LayoutState {
  const fallback = defaultLayout(definition);
  if (typeof window === "undefined") return fallback;
  try {
    const parsed = JSON.parse(window.localStorage.getItem(storageKey) || "{}") as Partial<LayoutState>;
    return Object.fromEntries(
      definition.defaultSurfaces.map((surface) => {
        const saved = parsed[surface.id];
        return [
          surface.id,
          {
            open: saved?.open ?? surface.defaultOpen,
            collapsed: saved?.collapsed ?? false,
            width: Math.max(surface.minWidth, saved?.width ?? surface.defaultWidth),
          },
        ];
      }),
    );
  } catch {
    return fallback;
  }
}

function roleTone(role: WorkspaceSurfaceDefinition["role"]): string {
  if (role === "chat") return "bg-[#5b76fe]";
  if (role === "inspector") return "bg-[#9b72cf]";
  if (role === "management") return "bg-[#00b473]";
  if (role === "source") return "bg-[#e6a43a]";
  if (role === "artifact") return "bg-[#667085]";
  return "bg-[#8aa6ff]";
}

export function WorkspaceFrame({ definition, storageKey, renderSurface }: WorkspaceFrameProps) {
  const [layout, setLayout] = useState<LayoutState>(() => loadLayout(storageKey, definition));
  const [fullscreenSurfaceId, setFullscreenSurfaceId] = useState<string | null>(null);
  const [overviewOpen, setOverviewOpen] = useState(false);
  const dragRef = useRef<{ surfaceId: string; startX: number; startWidth: number } | null>(null);

  const surfacesById = useMemo(
    () => Object.fromEntries(definition.defaultSurfaces.map((surface) => [surface.id, surface])),
    [definition.defaultSurfaces],
  );

  useEffect(() => {
    window.localStorage.setItem(storageKey, JSON.stringify(layout));
  }, [layout, storageKey]);

  useEffect(() => {
    const onPointerMove = (event: PointerEvent) => {
      const drag = dragRef.current;
      if (!drag) return;
      const surface = surfacesById[drag.surfaceId];
      if (!surface) return;
      const width = Math.max(surface.minWidth, drag.startWidth + event.clientX - drag.startX);
      setLayout((current) => ({
        ...current,
        [drag.surfaceId]: {
          ...current[drag.surfaceId],
          width,
        },
      }));
    };
    const onPointerUp = () => {
      dragRef.current = null;
      document.body.style.cursor = "";
      document.body.style.userSelect = "";
    };
    window.addEventListener("pointermove", onPointerMove);
    window.addEventListener("pointerup", onPointerUp);
    return () => {
      window.removeEventListener("pointermove", onPointerMove);
      window.removeEventListener("pointerup", onPointerUp);
    };
  }, [surfacesById]);

  const updateSurface = useCallback((surfaceId: string, patch: Partial<SurfaceLayout>) => {
    setLayout((current) => ({
      ...current,
      [surfaceId]: {
        ...current[surfaceId],
        ...patch,
      },
    }));
  }, []);

  const resetLayout = useCallback(() => {
    setFullscreenSurfaceId(null);
    setLayout(defaultLayout(definition));
  }, [definition]);

  const openSurfaces = definition.defaultSurfaces.filter((surface) => layout[surface.id]?.open);
  const visibleSurfaces = fullscreenSurfaceId
    ? definition.defaultSurfaces.filter((surface) => surface.id === fullscreenSurfaceId)
    : openSurfaces;

  return (
    <div className="flex h-screen min-h-0 flex-col overflow-hidden bg-[#f4f6fa] text-[#1c1c1e]">
      <div className="shrink-0 border-b border-[#e3e7ef] bg-white/95 px-4 py-3">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="flex min-w-0 items-center gap-3">
            <Link
              to="/clinical-insights"
              aria-label="Exit workspace"
              title="Exit workspace"
              className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg border border-[#dfe4ea] bg-white text-[#667085] transition hover:border-[#cfd7ff] hover:text-[#1c1c1e]"
            >
              <ArrowLeft size={16} />
            </Link>
            <div className="min-w-0">
              <div className="flex items-center gap-2">
                <span className="h-2 w-2 rounded-full bg-[#00b473]" />
                <span className="text-[11px] font-semibold uppercase text-[#667085]">Clinical trials</span>
              </div>
              <h1 className="mt-0.5 truncate text-lg font-semibold text-[#111827]">{definition.title}</h1>
            </div>
          </div>

          <div className="flex min-w-0 flex-1 items-center justify-end gap-3">
            <div className="hidden min-w-0 items-center gap-1 overflow-x-auto rounded-xl border border-[#e3e7ef] bg-[#f7f8fb] p-1 lg:flex">
              {definition.defaultSurfaces.map((surface) => {
                const state = layout[surface.id];
                const open = state?.open ?? false;
                return (
                  <button
                    key={surface.id}
                    type="button"
                    onClick={() => updateSurface(surface.id, { open: !open, collapsed: false })}
                    className={`inline-flex shrink-0 items-center gap-2 rounded-lg px-3 py-1.5 text-xs font-semibold transition ${
                      open
                        ? "bg-white text-[#1c1c1e] shadow-[rgb(224_226_232)_0px_0px_0px_1px]"
                        : "text-[#667085] hover:bg-white/70 hover:text-[#1c1c1e]"
                    }`}
                  >
                    <span className={`h-1.5 w-1.5 rounded-full ${roleTone(surface.role)}`} />
                    {surface.title}
                  </button>
                );
              })}
            </div>
            <button
              type="button"
              onClick={() => setOverviewOpen(true)}
              title="Overview"
              className="flex h-9 w-9 items-center justify-center rounded-lg border border-[#dfe4ea] bg-white text-[#667085] transition hover:border-[#cfd7ff] hover:text-[#1c1c1e]"
            >
              <Info size={16} />
            </button>
            <button
              type="button"
              onClick={resetLayout}
              title="Reset layout"
              className="flex h-9 w-9 items-center justify-center rounded-lg border border-[#dfe4ea] bg-white text-[#667085] transition hover:border-[#cfd7ff] hover:text-[#1c1c1e]"
            >
              <RotateCcw size={16} />
            </button>
          </div>
        </div>

        <div className="mt-3 flex gap-1 overflow-x-auto pb-1 lg:hidden">
          {definition.defaultSurfaces.map((surface) => {
            const state = layout[surface.id];
            const open = state?.open ?? false;
            return (
              <button
                key={surface.id}
                type="button"
                onClick={() => updateSurface(surface.id, { open: !open, collapsed: false })}
                className={`inline-flex shrink-0 items-center gap-2 rounded-lg px-3 py-1.5 text-xs font-semibold ${
                  open
                    ? "bg-white text-[#1c1c1e] shadow-[rgb(224_226_232)_0px_0px_0px_1px]"
                    : "text-[#667085] hover:bg-white/70 hover:text-[#1c1c1e]"
                }`}
              >
                <span className={`h-1.5 w-1.5 rounded-full ${roleTone(surface.role)}`} />
                {surface.title}
              </button>
            );
          })}
        </div>
      </div>

      <div className="flex min-h-0 flex-1 gap-3 overflow-x-auto overflow-y-hidden p-3">
        {visibleSurfaces.length === 0 ? (
          <div className="flex flex-1 items-center justify-center p-8">
            <div className="max-w-md border border-[#dfe4ea] bg-white p-6 text-center">
              <div className="text-base font-semibold text-[#1d2433]">No surfaces are open</div>
              <div className="mt-2 text-sm text-[#667085]">Use the surface switcher above to reopen chat, canvas, inspector, or management panes.</div>
            </div>
          </div>
        ) : (
          visibleSurfaces.map((surface) => {
            const state = layout[surface.id] ?? { open: surface.defaultOpen, collapsed: false, width: surface.defaultWidth };
            const fullscreen = fullscreenSurfaceId === surface.id;
            const width = fullscreen ? "100%" : state.collapsed ? 56 : state.width;
            return (
              <section
                key={surface.id}
                className="group relative flex shrink-0 flex-col overflow-hidden rounded-xl border border-[#e1e6ef] bg-white shadow-[rgba(17,24,39,0.04)_0px_12px_28px]"
                style={{ width }}
              >
                <div className="flex h-11 shrink-0 items-center gap-2 border-b border-[#eef2f6] bg-white px-3">
                  <button
                    type="button"
                    onClick={() => updateSurface(surface.id, { collapsed: !state.collapsed })}
                    disabled={!surface.canCollapse}
                    title={state.collapsed ? "Expand pane" : "Collapse pane"}
                    className="flex h-7 w-7 items-center justify-center rounded-lg text-[#667085] hover:bg-[#f5f6f8] disabled:cursor-not-allowed disabled:opacity-30"
                  >
                    {state.collapsed ? <ChevronsRight size={16} /> : <ChevronsLeft size={16} />}
                  </button>
                  {!state.collapsed && (
                    <>
                      <div className="min-w-0 flex-1">
                        <div className="truncate text-sm font-semibold text-[#1d2433]">{surface.title}</div>
                      </div>
                      {surface.canFullscreen && (
                        <button
                          type="button"
                          onClick={() => setFullscreenSurfaceId(fullscreen ? null : surface.id)}
                          title={fullscreen ? "Restore pane" : "Fullscreen pane"}
                          className="flex h-7 w-7 items-center justify-center rounded-lg text-[#667085] hover:bg-[#f5f6f8]"
                        >
                          {fullscreen ? <Minimize2 size={15} /> : <Maximize2 size={15} />}
                        </button>
                      )}
                      <button
                        type="button"
                        onClick={() => updateSurface(surface.id, { open: false })}
                        title="Close pane"
                        className="flex h-7 w-7 items-center justify-center rounded-lg text-[#667085] hover:bg-[#fff5f5] hover:text-[#b42318]"
                      >
                        <PanelLeftClose size={15} />
                      </button>
                    </>
                  )}
                </div>
                {state.collapsed ? (
                  <button
                    type="button"
                    onClick={() => updateSurface(surface.id, { collapsed: false })}
                    className="flex flex-1 items-start justify-center px-2 py-4 text-xs font-semibold uppercase tracking-wide text-[#667085]"
                    style={{ writingMode: "vertical-rl" }}
                  >
                    {surface.title}
                  </button>
                ) : (
                  <div className="min-h-0 flex-1 overflow-auto">{renderSurface(surface)}</div>
                )}
                {!fullscreen && !state.collapsed && (
                  <div
                    role="separator"
                    aria-label={`Resize ${surface.title}`}
                    onPointerDown={(event) => {
                      dragRef.current = { surfaceId: surface.id, startX: event.clientX, startWidth: state.width };
                      document.body.style.cursor = "col-resize";
                      document.body.style.userSelect = "none";
                    }}
                    className="absolute right-0 top-0 h-full w-1 cursor-col-resize hover:bg-[#5b76fe]"
                  />
                )}
              </section>
            );
          })
        )}
      </div>

      {overviewOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/30 p-4">
          <div className="max-h-[88vh] w-full max-w-2xl overflow-auto rounded bg-white shadow-xl">
            <div className="flex items-start justify-between gap-4 border-b border-[#eef2f6] p-5">
              <div>
                <div className="text-xs font-semibold uppercase text-[#5b76fe]">Workspace overview</div>
                <h2 className="mt-1 text-lg font-semibold text-[#111827]">{definition.title}</h2>
              </div>
              <button
                type="button"
                onClick={() => setOverviewOpen(false)}
                className="flex h-8 w-8 items-center justify-center rounded text-[#667085] hover:bg-[#f5f6f8]"
              >
                <X size={18} />
              </button>
            </div>
            <div className="space-y-5 p-5 text-sm text-[#4a5168]">
              <p>{definition.description}</p>
              <div>
                <div className="font-semibold text-[#1d2433]">Agent access</div>
                <div className="mt-2 grid gap-2 sm:grid-cols-2">
                  {definition.sourceGroups.flatMap((group) =>
                    group.sources.map((source) => (
                      <div key={source.id} className="border border-[#e8edf3] bg-[#fbfcff] p-3">
                        <div className="font-medium text-[#1d2433]">{source.label}</div>
                        <div className="mt-1 text-xs text-[#667085]">{source.location}</div>
                      </div>
                    )),
                  )}
                </div>
              </div>
              <div>
                <div className="font-semibold text-[#1d2433]">Tools and approvals</div>
                <div className="mt-2 grid gap-2">
                  {definition.tools.map((tool) => (
                    <div key={tool.id} className="flex items-start justify-between gap-3 border border-[#e8edf3] bg-white p-3">
                      <div>
                        <div className="font-medium text-[#1d2433]">{tool.label}</div>
                        <div className="mt-1 text-xs text-[#667085]">{tool.description}</div>
                      </div>
                      <span className="shrink-0 rounded bg-[#f5f7fb] px-2 py-1 text-xs font-semibold text-[#667085]">
                        {tool.permission}
                      </span>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

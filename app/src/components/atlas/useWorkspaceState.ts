import { useCallback, useEffect, useState } from "react";
import {
  FIXTURE_CANVAS,
  FILE_TREES,
  INITIAL_CHAT,
  INITIAL_TABS,
  getActionTab,
  getFileTab,
  type ChatMessage,
  type FileNode,
  type FileTreeNode,
  type WorkbenchTab,
} from "./data";
import type { PaneSizes, PaneVisibility, WorkspaceId } from "./types";

const DEFAULT_PANES: PaneVisibility = {
  sessions: true,
  chat: true,
  workbench: true,
  files: true,
  inspector: true,
};

const CASPIAN_DEFAULT_PANES: PaneVisibility = {
  sessions: true,
  chat: true,
  workbench: false,
  files: false,
  inspector: false,
};

const DEFAULT_SIZES: PaneSizes = {
  sessionsW: 248,
  chatW: 480,
  rightW: 300,
  filesH: 50,
};

const LEGACY_PANES_STORAGE_KEY = "atlas:panes";
const LEGACY_SIZES_STORAGE_KEY = "atlas:sizes";
const PANES_STORAGE_PREFIX = "atlas:panes:";
const SIZES_STORAGE_PREFIX = "atlas:sizes:";
const RIGHT_FOCUS_STORAGE_PREFIX = "atlas:right-focus:";
const ACTIVE_SESSION_STORAGE_PREFIX = "atlas:active-session:";
const ACTIVE_TAB_STORAGE_PREFIX = "atlas:active-tab:";
const ACTIVE_FILE_STORAGE_PREFIX = "atlas:active-file:";
const CITATION_STORAGE_PREFIX = "atlas:citation:";
const INSPECTOR_TAB_STORAGE_PREFIX = "atlas:inspector-tab:";
const DEFAULT_ACTIVE_TAB_IDS = Object.fromEntries(
  Object.entries(INITIAL_TABS).flatMap(([workspaceId, tabs]) =>
    tabs[0] ? [[workspaceId, tabs[0].id]] : [],
  ),
) as Partial<Record<WorkspaceId, string>>;

type InspectorTab = "evidence" | "trace" | "context";

type UseWorkspaceStateOptions = {
  seedTabs?: WorkbenchTab[];
  canvas?: Record<string, unknown>;
  filesTree?: FileTreeNode[];
  getFileTab?: (fileId: string) => WorkbenchTab | null;
  getActionTab?: (target: string) => WorkbenchTab | null;
};

function defaultPanesForWorkspace(workspaceId: WorkspaceId): PaneVisibility {
  return workspaceId === "caspian" ? CASPIAN_DEFAULT_PANES : DEFAULT_PANES;
}

function paneStorageKeys(workspaceId: WorkspaceId, panesStorageKey: string): string[] {
  // Caspian now opens in a calmer chat-first layout. Keep honoring any
  // workspace-specific saved state, but do not resurrect the old global pane
  // preset when this workspace has never been opened before.
  return workspaceId === "caspian"
    ? [panesStorageKey]
    : [panesStorageKey, LEGACY_PANES_STORAGE_KEY];
}

function isPaneStateEqual(a: PaneVisibility, b: PaneVisibility): boolean {
  return (
    a.sessions === b.sessions &&
    a.chat === b.chat &&
    a.workbench === b.workbench &&
    a.files === b.files &&
    a.inspector === b.inspector
  );
}

function loadPaneState(workspaceId: WorkspaceId, panesStorageKey: string): PaneVisibility {
  const fallback = defaultPanesForWorkspace(workspaceId);
  const loaded = loadJson<PaneVisibility>(paneStorageKeys(workspaceId, panesStorageKey), fallback);
  // Migrate Caspian away from the old everything-open factory layout.
  // If the stored state still exactly matches that historical preset, treat it
  // as uncustomized and adopt the calmer chat-first default instead.
  if (workspaceId === "caspian" && isPaneStateEqual(loaded, DEFAULT_PANES)) {
    return CASPIAN_DEFAULT_PANES;
  }
  return loaded;
}

function loadJson<T>(keys: string[], fallback: T): T {
  if (typeof window === "undefined") return fallback;
  try {
    for (const key of keys) {
      const raw = window.localStorage.getItem(key);
      if (!raw) continue;
      return { ...fallback, ...(JSON.parse(raw) as Partial<T>) };
    }
    return fallback;
  } catch {
    return fallback;
  }
}

function loadString(keys: string[], fallback: string | null): string | null {
  if (typeof window === "undefined") return fallback;
  try {
    for (const key of keys) {
      const raw = window.localStorage.getItem(key);
      if (raw) return raw;
    }
  } catch {
    // Ignore storage failures and fall back to the seeded state.
  }
  return fallback;
}

function loadInspectorTab(key: string): InspectorTab {
  const raw = loadString([key], "evidence");
  return raw === "trace" || raw === "context" ? raw : "evidence";
}

function findFileNode(tree: FileTreeNode[], matcher: (file: FileNode) => boolean): FileNode | null {
  for (const node of tree) {
    if (node.type !== "folder") continue;
    const match = node.children.find(matcher);
    if (match) return match;
  }
  return null;
}

function mergeTabs(current: WorkbenchTab[], seeded: WorkbenchTab[]): WorkbenchTab[] {
  const seededById = new Map(seeded.map((tab) => [tab.id, tab] as const));
  const next: WorkbenchTab[] = [];

  for (const tab of current) {
    const updated = seededById.get(tab.id);
    if (updated) {
      next.push(updated);
      seededById.delete(tab.id);
      continue;
    }
    next.push(tab);
  }

  for (const tab of seeded) {
    if (seededById.has(tab.id)) next.push(tab);
  }

  return next;
}

export function useWorkspaceState(
  workspaceId: WorkspaceId,
  options: UseWorkspaceStateOptions = {},
) {
  const panesStorageKey = `${PANES_STORAGE_PREFIX}${workspaceId}`;
  const sizesStorageKey = `${SIZES_STORAGE_PREFIX}${workspaceId}`;
  const rightFocusStorageKey = `${RIGHT_FOCUS_STORAGE_PREFIX}${workspaceId}`;
  const activeSessionStorageKey = `${ACTIVE_SESSION_STORAGE_PREFIX}${workspaceId}`;
  const activeTabStorageKey = `${ACTIVE_TAB_STORAGE_PREFIX}${workspaceId}`;
  const activeFileStorageKey = `${ACTIVE_FILE_STORAGE_PREFIX}${workspaceId}`;
  const citationStorageKey = `${CITATION_STORAGE_PREFIX}${workspaceId}`;
  const inspectorTabStorageKey = `${INSPECTOR_TAB_STORAGE_PREFIX}${workspaceId}`;
  const seededTabs = options.seedTabs ?? INITIAL_TABS[workspaceId] ?? [];
  const fileTree = options.filesTree ?? FILE_TREES[workspaceId] ?? [];
  const [panes, setPanes] = useState<PaneVisibility>(() =>
    loadPaneState(workspaceId, panesStorageKey),
  );
  const [sizes, setSizes] = useState<PaneSizes>(() =>
    loadJson<PaneSizes>([sizesStorageKey, LEGACY_SIZES_STORAGE_KEY], DEFAULT_SIZES),
  );
  const [rightPaneFocus, setRightPaneFocus] = useState<"files" | "inspector">(() => {
    if (typeof window === "undefined") return "files";
    const raw = window.localStorage.getItem(rightFocusStorageKey);
    return raw === "inspector" ? "inspector" : "files";
  });
  const [activeSessionId, setActiveSessionId] = useState<string | null>(() =>
    loadString([activeSessionStorageKey], null),
  );
  const [chats, setChats] = useState<Record<WorkspaceId, ChatMessage[]>>(() => INITIAL_CHAT);
  const [tabsByWs, setTabsByWs] = useState<Record<WorkspaceId, WorkbenchTab[]>>(() => ({
    ...INITIAL_TABS,
    [workspaceId]: seededTabs,
  }));
  const [activeTabByWs, setActiveTabByWs] = useState<Partial<Record<WorkspaceId, string>>>(() => ({
    ...DEFAULT_ACTIVE_TAB_IDS,
    [workspaceId]:
      loadString([activeTabStorageKey], seededTabs[0]?.id ?? DEFAULT_ACTIVE_TAB_IDS[workspaceId] ?? null) ??
      undefined,
  }));
  const [activeFileByWs, setActiveFileByWs] = useState<Partial<Record<WorkspaceId, string>>>(() => ({
    [workspaceId]: loadString([activeFileStorageKey], null) ?? undefined,
  }));
  const [citationByWs, setCitationByWs] = useState<Partial<Record<WorkspaceId, string>>>(() => ({
    [workspaceId]: loadString([citationStorageKey], null) ?? undefined,
  }));
  const [inspectorTabByWs, setInspectorTabByWs] = useState<Partial<Record<WorkspaceId, InspectorTab>>>(() => ({
    [workspaceId]: loadInspectorTab(inspectorTabStorageKey),
  }));

  useEffect(() => {
    window.localStorage.setItem(panesStorageKey, JSON.stringify(panes));
  }, [panes, panesStorageKey]);

  useEffect(() => {
    window.localStorage.setItem(sizesStorageKey, JSON.stringify(sizes));
  }, [sizes, sizesStorageKey]);

  useEffect(() => {
    window.localStorage.setItem(rightFocusStorageKey, rightPaneFocus);
  }, [rightPaneFocus, rightFocusStorageKey]);

  useEffect(() => {
    if (activeSessionId) {
      window.localStorage.setItem(activeSessionStorageKey, activeSessionId);
      return;
    }
    window.localStorage.removeItem(activeSessionStorageKey);
  }, [activeSessionId, activeSessionStorageKey]);

  const activeTabId = activeTabByWs[workspaceId] ?? null;
  useEffect(() => {
    if (activeTabId) {
      window.localStorage.setItem(activeTabStorageKey, activeTabId);
      return;
    }
    window.localStorage.removeItem(activeTabStorageKey);
  }, [activeTabId, activeTabStorageKey]);

  const activeFileId = activeFileByWs[workspaceId] ?? null;
  useEffect(() => {
    if (activeFileId) {
      window.localStorage.setItem(activeFileStorageKey, activeFileId);
      return;
    }
    window.localStorage.removeItem(activeFileStorageKey);
  }, [activeFileId, activeFileStorageKey]);

  const citationId = citationByWs[workspaceId] ?? null;
  useEffect(() => {
    if (citationId) {
      window.localStorage.setItem(citationStorageKey, citationId);
      return;
    }
    window.localStorage.removeItem(citationStorageKey);
  }, [citationId, citationStorageKey]);

  const inspectorTab = inspectorTabByWs[workspaceId] ?? "evidence";
  useEffect(() => {
    window.localStorage.setItem(inspectorTabStorageKey, inspectorTab);
  }, [inspectorTab, inspectorTabStorageKey]);

  useEffect(() => {
    if (seededTabs.length === 0) return;
    setTabsByWs((prev) => {
      const current = prev[workspaceId] ?? [];
      const merged = mergeTabs(current, seededTabs);
      const same =
        current.length === merged.length &&
        current.every((tab, index) => {
          const next = merged[index];
          return (
            next &&
            next.id === tab.id &&
            next.label === tab.label &&
            next.icon === tab.icon &&
            next.kind === tab.kind &&
            next.renderer === tab.renderer &&
            next.dirty === tab.dirty
          );
        });
      if (same) return prev;
      return { ...prev, [workspaceId]: merged };
    });
    setActiveTabByWs((prev) => {
      const active = prev[workspaceId];
      if (active && seededTabs.some((tab) => tab.id === active)) return prev;
      return { ...prev, [workspaceId]: seededTabs[0]?.id };
    });
  }, [seededTabs, workspaceId]);

  const showPane = useCallback((pane: keyof PaneVisibility) => {
    if (pane === "files" || pane === "inspector") {
      setRightPaneFocus(pane);
    }
    setPanes((current) => (current[pane] ? current : { ...current, [pane]: true }));
  }, []);

  const togglePane = useCallback((pane: keyof PaneVisibility) => {
    if (pane === "files" || pane === "inspector") {
      setRightPaneFocus(pane);
      setPanes((current) => ({ ...current, [pane]: !current[pane] }));
      return;
    }
    setPanes((current) => ({ ...current, [pane]: !current[pane] }));
  }, []);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (!e.altKey) return;
      const key = e.key.toLowerCase();
      const map: Record<string, keyof PaneVisibility> = {
        s: "sessions",
        c: "chat",
        p: "workbench",
        f: "files",
        i: "inspector",
      };
      if (map[key]) {
        e.preventDefault();
        togglePane(map[key]);
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [togglePane]);

  const handleCitation = useCallback((id: string) => {
    setCitationByWs((prev) => ({ ...prev, [workspaceId]: id }));
    setRightPaneFocus("inspector");
    setPanes((p) => (p.inspector ? p : { ...p, inspector: true }));
  }, [workspaceId]);

  const openTab = useCallback(
    (tab: WorkbenchTab) => {
      setTabsByWs((prev) => {
        const ws = prev[workspaceId] ?? [];
        if (ws.some((t) => t.id === tab.id)) return prev;
        return { ...prev, [workspaceId]: [...ws, tab] };
      });
      setActiveTabByWs((prev) => ({ ...prev, [workspaceId]: tab.id }));
    },
    [workspaceId],
  );

  const resolveFileTab = useCallback(
    (fileId: string) => options.getFileTab?.(fileId) ?? getFileTab(workspaceId, fileId),
    [options, workspaceId],
  );

  const handleOpenFile = useCallback(
    (node: FileNode | { kind: "citation"; id: string }) => {
      if ("kind" in node && node.kind === "citation") {
        handleCitation(node.id);
        return;
      }
      const file = node as FileNode;
      const tab = resolveFileTab(file.id);
      setActiveFileByWs((prev) => ({ ...prev, [workspaceId]: file.id }));
      if (tab) openTab(tab);
    },
    [handleCitation, openTab, resolveFileTab, workspaceId],
  );

  const handleReference = useCallback(
    (ref: string) => {
      if (ref.startsWith("c_")) {
        handleCitation(ref);
        return;
      }
      const file = findFileNode(fileTree, (node) => node.name === ref || node.id === ref);
      if (file) {
        handleOpenFile(file);
      }
    },
    [fileTree, handleCitation, handleOpenFile],
  );

  const handleAction = useCallback(
    (target: string) => {
      if (target.startsWith("cite-")) {
        handleCitation(target.slice(5));
        return;
      }
      const tab = options.getActionTab?.(target) ?? getActionTab(workspaceId, target);
      if (tab) openTab(tab);
    },
    [handleCitation, openTab, options, workspaceId],
  );

  const handleSelectTab = useCallback(
    (id: string) => {
      setActiveTabByWs((prev) => ({ ...prev, [workspaceId]: id }));
    },
    [workspaceId],
  );

  const handleCloseTab = useCallback(
    (id: string) => {
      setTabsByWs((prev) => {
        const remaining = (prev[workspaceId] ?? []).filter((tab) => tab.id !== id);
        setActiveTabByWs((current) => {
          if (current[workspaceId] !== id) return current;
          return { ...current, [workspaceId]: remaining[0]?.id };
        });
        return { ...prev, [workspaceId]: remaining };
      });
    },
    [workspaceId],
  );

  const handleSend = useCallback(
    (text: string) => {
      const userMsg: ChatMessage = { id: `u${Date.now()}`, role: "user", content: text };
      const family = workspaceId === "caspian" ? "clinical" : "marketplace";
      const reply: ChatMessage = {
        id: `a${Date.now()}`,
        role: "assistant",
        time: new Date().toLocaleTimeString("en-US", { hour: "2-digit", minute: "2-digit" }),
        trace: family === "clinical"
          ? { tool: "fhir.search", target: "Observation?patient=8.4127.881" }
          : { tool: "plugin.run", target: "trial-finder@2.4.1 / re-rank" },
        blocks:
          family === "clinical"
            ? [
                "Acknowledged. I'll fold that into the briefing — citations will keep flowing into [pre-op-packet-v2.md] and the inspector will track every pinned source. Drop a citation chip to open the underlying FHIR resource.",
              ]
            : [
                "Acknowledged. I'll re-rank the shortlist and surface anything that crosses the consent boundary in this thread. The package keeps a clean read-only handle on the Caspian workspace — no PHI leaves the run.",
              ],
      };
      setChats((prev) => ({
        ...prev,
        [workspaceId]: [...(prev[workspaceId] ?? []), userMsg, reply],
      }));
    },
    [workspaceId],
  );

  return {
    panes,
    setPanes,
    showPane,
    togglePane,
    sizes,
    setSizes,
    activeSessionId,
    setActiveSessionId,
    chats,
    tabs: tabsByWs[workspaceId] ?? [],
    activeTabId,
    activeFileId,
    citationId,
    setCitationId: (id: string | null) =>
      setCitationByWs((prev) => ({ ...prev, [workspaceId]: id ?? undefined })),
    rightPaneFocus,
    inspectorTab,
    setInspectorTab: (tab: InspectorTab) =>
      setInspectorTabByWs((prev) => ({ ...prev, [workspaceId]: tab })),
    canvas: options.canvas ?? FIXTURE_CANVAS[workspaceId] ?? {},
    handleCitation,
    handleReference,
    handleOpenFile,
    handleAction,
    handleSelectTab,
    handleCloseTab,
    handleSend,
    openTab,
  };
}

export type WorkspaceStateHook = ReturnType<typeof useWorkspaceState>;

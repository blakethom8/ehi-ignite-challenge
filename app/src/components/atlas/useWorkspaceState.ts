import { useCallback, useEffect, useState } from "react";
import {
  ACTION_TO_TAB,
  FILE_TO_TAB,
  INITIAL_CHAT,
  INITIAL_TABS,
  type ChatMessage,
  type FileNode,
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

const DEFAULT_SIZES: PaneSizes = {
  sessionsW: 248,
  chatW: 480,
  rightW: 300,
  filesH: 50,
};

const PANES_STORAGE_KEY = "atlas:panes";
const SIZES_STORAGE_KEY = "atlas:sizes";

function loadJson<T>(key: string, fallback: T): T {
  if (typeof window === "undefined") return fallback;
  try {
    const raw = window.localStorage.getItem(key);
    if (!raw) return fallback;
    return { ...fallback, ...(JSON.parse(raw) as Partial<T>) };
  } catch {
    return fallback;
  }
}

export function useWorkspaceState(workspaceId: WorkspaceId) {
  const [panes, setPanes] = useState<PaneVisibility>(() =>
    loadJson<PaneVisibility>(PANES_STORAGE_KEY, DEFAULT_PANES),
  );
  const [sizes, setSizes] = useState<PaneSizes>(() =>
    loadJson<PaneSizes>(SIZES_STORAGE_KEY, DEFAULT_SIZES),
  );
  const [activeSessionId, setActiveSessionId] = useState<string | null>(null);
  const [chats, setChats] = useState<Record<WorkspaceId, ChatMessage[]>>(() => INITIAL_CHAT);
  const [tabsByWs, setTabsByWs] = useState<Record<WorkspaceId, WorkbenchTab[]>>(() => INITIAL_TABS);
  const [activeTabByWs, setActiveTabByWs] = useState<Partial<Record<WorkspaceId, string>>>({
    "caspian": "tab_brief",
    "trial-finder": "tab_board",
  });
  const [citationId, setCitationId] = useState<string | null>(null);

  useEffect(() => {
    window.localStorage.setItem(PANES_STORAGE_KEY, JSON.stringify(panes));
  }, [panes]);

  useEffect(() => {
    window.localStorage.setItem(SIZES_STORAGE_KEY, JSON.stringify(sizes));
  }, [sizes]);

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
        setPanes((p) => ({ ...p, [map[key]]: !p[map[key]] }));
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  const togglePane = useCallback((pane: keyof PaneVisibility) => {
    setPanes((p) => ({ ...p, [pane]: !p[pane] }));
  }, []);

  const handleCitation = useCallback((id: string) => {
    setCitationId(id);
    setPanes((p) => (p.inspector ? p : { ...p, inspector: true }));
  }, []);

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

  const handleOpenFile = useCallback(
    (node: FileNode | { kind: "citation"; id: string }) => {
      if ("kind" in node && node.kind === "citation") {
        handleCitation(node.id);
        return;
      }
      const file = node as FileNode;
      const tab = FILE_TO_TAB[file.id];
      if (tab) openTab(tab);
    },
    [handleCitation, openTab],
  );

  const handleAction = useCallback(
    (target: string) => {
      if (target.startsWith("cite-")) {
        handleCitation(target.slice(5));
        return;
      }
      const tab = ACTION_TO_TAB[target];
      if (tab) openTab(tab);
    },
    [handleCitation, openTab],
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
        const ws = (prev[workspaceId] ?? []).filter((x) => x.id !== id);
        return { ...prev, [workspaceId]: ws };
      });
      setActiveTabByWs((prev) => {
        if (prev[workspaceId] !== id) return prev;
        const remaining = (tabsByWs[workspaceId] ?? []).filter((x) => x.id !== id);
        return { ...prev, [workspaceId]: remaining[0]?.id };
      });
    },
    [tabsByWs, workspaceId],
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
    togglePane,
    sizes,
    setSizes,
    activeSessionId,
    setActiveSessionId,
    chats,
    tabs: tabsByWs[workspaceId] ?? [],
    activeTabId: activeTabByWs[workspaceId] ?? null,
    citationId,
    setCitationId,
    handleCitation,
    handleOpenFile,
    handleAction,
    handleSelectTab,
    handleCloseTab,
    handleSend,
  };
}

export type WorkspaceStateHook = ReturnType<typeof useWorkspaceState>;

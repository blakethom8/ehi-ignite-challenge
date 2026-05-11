/**
 * Atlas Agentic Workspaces — shared component barrel.
 *
 * The shell, panes, and durable primitives. Imports from this barrel are
 * the contract for any page that wants to live inside the Atlas chrome.
 *
 * Spec: .claude/handoff/atlas/README.md
 */

// Shell ----------------------------------------------------------------
export { AppShell, deriveActiveModule } from "./AppShell";
export { ModuleBar } from "./ModuleBar";
export { PlatformDrawer } from "./PlatformDrawer";
export { Titlebar, type Crumb } from "./Titlebar";

// Workspace shell ------------------------------------------------------
export { WorkspaceFrame } from "./WorkspaceFrame";
export { ContextStrip } from "./ContextStrip";
export { SessionsPane } from "./SessionsPane";
export { ChatPane } from "./ChatPane";
export { WorkbenchPane } from "./WorkbenchPane";
export { FilesPane } from "./FilesPane";
export { InspectorPane } from "./InspectorPane";
export { PluginHome } from "./PluginHome";

// Reusable primitives ---------------------------------------------------
export { CitationChip, type CitationChipProps } from "./CitationChip";
export { DispositionBanner, type DispositionBannerProps, type DispositionState } from "./DispositionBanner";
export { FactRail, type FactRailProps, type FactRailCell } from "./FactRail";
export { EvidenceTable, type EvidenceTableProps, type EvidenceColumn } from "./EvidenceTable";
export { ApprovalCard, type ApprovalCardProps } from "./ApprovalCard";
export { ToolTrace, type ToolTraceProps } from "./ToolTrace";
export { PatientHeader, type PatientHeaderProps, type PatientIdentity } from "./PatientHeader";

// State + types --------------------------------------------------------
export { useWorkspaceState, type WorkspaceStateHook } from "./useWorkspaceState";
export type {
  ModuleId,
  PaneId,
  PaneVisibility,
  PaneSizes,
  RecentWorkspace,
  User,
  Workspace,
  WorkspaceId,
} from "./types";

// Fixtures (dev / demo only) -------------------------------------------
export {
  WORKSPACES,
  PATIENT,
  SESSIONS,
  WORKFLOWS,
  FILE_TREES,
  CITATIONS,
  INITIAL_CHAT,
  INITIAL_TABS,
  type Citation,
  type ChatMessage,
  type Session,
  type Workflow,
  type WorkbenchTab,
} from "./data";

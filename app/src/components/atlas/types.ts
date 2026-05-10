export type ModuleId =
  | "patient-record"
  | "fhir-charts"
  | "caspian"
  | "workspaces"
  | "learn";

export type WorkspaceId =
  | "caspian"
  | "trial-finder"
  | "med-access"
  | "site-coord";

export type PaneId = "sessions" | "chat" | "workbench" | "files" | "inspector";

export type PaneVisibility = Record<PaneId, boolean>;

export type PaneSizes = {
  sessionsW: number;
  chatW: number;
  rightW: number;
  filesH: number;
};

export type Workspace = {
  id: WorkspaceId;
  family: "clinical" | "plugin";
  title: string;
  subtitle: string;
  icon: string;
  color: string;
  tint: string;
  boundary: string;
  boundaryTone: "ok" | "warn";
  vendor?: string;
  version?: string;
  permissions?: string[];
  runState?: "running" | "complete" | "idle" | "waiting";
  runStep?: string;
  runElapsed?: string;
  lastRefresh?: string;
  anchoredFrom?: string;
};

export type RecentWorkspace = {
  id: WorkspaceId;
  label: string;
  vendor: string;
  icon: string;
};

export type User = {
  initials: string;
  name: string;
  org: string;
};

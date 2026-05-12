import { useEffect, useState } from "react";
import { Braces, ChevronDown, ChevronRight, FileSpreadsheet, FileText, Folder, Hash, MoreHorizontal, Plus, Search } from "lucide-react";
import { FILE_TREES, type FileNode, type FileTreeNode, type FolderTreeNode } from "./data";
import type { WorkspaceId } from "./types";

const ICONS: Record<string, typeof FileText> = {
  FileText,
  FileSpreadsheet,
  Braces,
};

type FilesPaneProps = {
  workspaceId: WorkspaceId;
  onOpen: (node: FileNode | { kind: "citation"; id: string }) => void;
  activeFileId?: string | null;
  tree?: FileTreeNode[];
};

function collectInitiallyExpanded(nodes: FileTreeNode[], prefix = ""): Record<string, boolean> {
  const out: Record<string, boolean> = {};
  for (const node of nodes) {
    if (node.type === "folder") {
      const key = `${prefix}/${node.name}`;
      if (node.expanded) out[key] = true;
      Object.assign(out, collectInitiallyExpanded(node.children, key));
    }
  }
  return out;
}

export function FilesPane({ workspaceId, onOpen, activeFileId, tree: treeOverride }: FilesPaneProps) {
  const tree = treeOverride ?? FILE_TREES[workspaceId] ?? [];
  const [filter, setFilter] = useState("");
  const [expanded, setExpanded] = useState<Record<string, boolean>>(() => collectInitiallyExpanded(tree));

  // When the tree gets reseeded with a new shape (e.g. after a workflow run
  // adds a workflow-runs entry), keep any newly-expanded folders open and
  // honor `expanded: true` on freshly-arrived folders.
  useEffect(() => {
    setExpanded((current) => ({ ...collectInitiallyExpanded(tree), ...current }));
  }, [tree]);

  return (
    <div
      className="grid h-full min-h-0 grid-rows-[auto_auto_1fr] overflow-hidden"
      style={{
        background: "var(--bg-chrome)",
        borderBottom: "1px solid var(--line-1)",
      }}
    >
      <div
        className="flex h-8 items-center gap-2 border-b px-3"
        style={{ borderColor: "var(--line-1)" }}
      >
        <span
          className="text-[11px] font-semibold uppercase tracking-wider"
          style={{ color: "var(--ink-4)" }}
        >
          FILES
        </span>
        <div className="flex-1" />
        <FhBtn icon={<Plus className="h-3 w-3" strokeWidth={1.5} />} />
        <FhBtn icon={<ChevronDown className="h-3 w-3" strokeWidth={1.5} />} />
        <FhBtn icon={<MoreHorizontal className="h-3 w-3" strokeWidth={1.5} />} />
      </div>
      <div
        className="relative border-b px-2 py-1.5"
        style={{ borderColor: "var(--line-1)" }}
      >
        <Search
          className="absolute left-3 top-1/2 h-3 w-3 -translate-y-1/2"
          strokeWidth={1.5}
          style={{ color: "var(--ink-4)" }}
        />
        <input
          placeholder="Filter…"
          value={filter}
          onChange={(e) => setFilter(e.target.value)}
          className="h-6 w-full rounded-md border bg-transparent pl-6 pr-2 text-[11.5px] outline-none"
          style={{
            background: "var(--surface-0)",
            borderColor: "var(--line-1)",
            color: "var(--ink-1)",
          }}
        />
      </div>
      <div className="overflow-y-auto px-1 py-1 text-[12px]">
        {tree.map((n, i) =>
          renderNode(n, `${i}`, "", expanded, setExpanded, onOpen, activeFileId, filter, 10),
        )}
      </div>
    </div>
  );
}

function FhBtn({ icon }: { icon: React.ReactNode }) {
  return (
    <button
      className="grid h-5 w-5 place-items-center rounded text-[var(--ink-4)] hover:bg-[var(--surface-2)] hover:text-[var(--ink-1)]"
    >
      {icon}
    </button>
  );
}

function renderFolderChild(
  child: FileNode | FolderTreeNode,
  parentKey: string,
  expanded: Record<string, boolean>,
  setExpanded: React.Dispatch<React.SetStateAction<Record<string, boolean>>>,
  onOpen: (node: FileNode | { kind: "citation"; id: string }) => void,
  activeFileId: string | null | undefined,
  filter: string,
  depth: number,
): React.ReactNode {
  if (child.type === "folder") {
    return renderNode(child, parentKey, parentKey, expanded, setExpanded, onOpen, activeFileId, filter, depth);
  }
  return renderFile(child, parentKey, onOpen, activeFileId, filter, depth);
}

function renderFile(
  c: FileNode,
  key: string,
  onOpen: (node: FileNode | { kind: "citation"; id: string }) => void,
  activeFileId: string | null | undefined,
  filter: string,
  depth: number,
): React.ReactNode {
  if (filter && !c.name.toLowerCase().includes(filter.toLowerCase())) return null;
  const Icon = ICONS[c.icon] ?? FileText;
  const active = c.id === activeFileId;
  return (
    <div
      key={key}
      onClick={() => onOpen(c)}
      className="flex cursor-pointer items-center gap-1.5 rounded px-1.5 py-1 hover:bg-[var(--surface-2)]"
      style={{
        paddingLeft: depth + 16,
        background: active ? "var(--action-tint)" : "transparent",
      }}
    >
      <span className="w-2.5" />
      <Icon
        className="h-3 w-3"
        strokeWidth={1.5}
        style={{ color: active ? "var(--action)" : "var(--ink-4)" }}
      />
      <span
        className="truncate text-[11.5px]"
        style={{
          fontFamily: "var(--font-mono)",
          color: active ? "var(--action)" : "var(--ink-2)",
        }}
      >
        {c.name}
      </span>
      {c.dirty && (
        <span
          className="ml-1 h-1.5 w-1.5 rounded-full"
          style={{ background: "var(--action)" }}
        />
      )}
      {c.editable === false && (
        <span
          className="ml-auto text-[9.5px] uppercase tracking-wider"
          style={{ color: "var(--ink-4)" }}
        >
          ro
        </span>
      )}
    </div>
  );
}

function renderNode(
  n: FileTreeNode,
  key: string,
  parentKey: string,
  expanded: Record<string, boolean>,
  setExpanded: React.Dispatch<React.SetStateAction<Record<string, boolean>>>,
  onOpen: (node: FileNode | { kind: "citation"; id: string }) => void,
  activeFileId: string | null | undefined,
  filter: string,
  depth: number,
): React.ReactNode {
  if (n.type === "group") {
    return (
      <div
        key={key}
        className="px-2 pb-1 pt-3 text-[10px] font-semibold uppercase tracking-wider"
        style={{ color: "var(--ink-4)" }}
      >
        {n.label}
      </div>
    );
  }
  if (n.type === "folder") {
    const folderKey = `${parentKey}/${n.name}`;
    const open = expanded[folderKey];
    return (
      <div key={key}>
        <div
          onClick={() => setExpanded((e) => ({ ...e, [folderKey]: !e[folderKey] }))}
          className="flex cursor-pointer items-center gap-1.5 rounded px-1.5 py-1 hover:bg-[var(--surface-2)]"
          style={{ paddingLeft: depth }}
        >
          {open ? (
            <ChevronDown className="h-2.5 w-2.5" strokeWidth={1.5} style={{ color: "var(--ink-4)" }} />
          ) : (
            <ChevronRight className="h-2.5 w-2.5" strokeWidth={1.5} style={{ color: "var(--ink-4)" }} />
          )}
          <Folder className="h-3 w-3" strokeWidth={1.5} style={{ color: "var(--ink-4)" }} />
          <span className="text-[12px] font-medium" style={{ color: "var(--ink-1)" }}>
            {n.name}
          </span>
        </div>
        {open &&
          n.children.map((c, i) =>
            renderFolderChild(c, `${folderKey}/${i}`, expanded, setExpanded, onOpen, activeFileId, filter, depth + 16),
          )}
      </div>
    );
  }
  if (n.type === "file") {
    return renderFile(n, key, onOpen, activeFileId, filter, depth);
  }
  if (n.type === "ref") {
    return (
      <div
        key={key}
        onClick={() => n.id.startsWith("c_") && onOpen({ kind: "citation", id: n.id })}
        className="flex cursor-pointer items-center gap-1.5 rounded px-1.5 py-1 hover:bg-[var(--surface-2)]"
        style={{ paddingLeft: 10 }}
      >
        <span className="w-2.5" />
        <Hash className="h-3 w-3" strokeWidth={1.5} style={{ color: "var(--ink-4)" }} />
        <span
          className="truncate text-[11.5px]"
          style={{ fontFamily: "var(--font-mono)", color: "var(--ink-3)" }}
        >
          {n.label}
        </span>
      </div>
    );
  }
  return null;
}

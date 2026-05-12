import { describe, expect, it } from "vitest";
import { FILE_TABS_BY_WORKSPACE, FILE_TREES } from "./data";

describe("atlas fixture file routing", () => {
  it("maps every visible fixture file to a workbench tab in its workspace", () => {
    for (const [workspaceId, nodes] of Object.entries(FILE_TREES)) {
      const tabs = FILE_TABS_BY_WORKSPACE[workspaceId as keyof typeof FILE_TABS_BY_WORKSPACE];
      const fileIds = nodes.flatMap((node) =>
        node.type === "folder"
          ? node.children
              .filter((child): child is { type: "file"; id: string; name: string; ext: string; icon: string } => child.type === "file")
              .map((child) => child.id)
          : [],
      );

      expect(fileIds, `no fixture files found for ${workspaceId}`).not.toHaveLength(0);
      for (const fileId of fileIds) {
        expect(tabs[fileId], `missing tab mapping for ${workspaceId}:${fileId}`).toBeDefined();
      }
    }
  });

  it("keeps each mapped tab structurally complete", () => {
    for (const [workspaceId, tabs] of Object.entries(FILE_TABS_BY_WORKSPACE)) {
      for (const [fileId, tab] of Object.entries(tabs)) {
        expect(tab.id, `missing tab id for ${workspaceId}:${fileId}`).toBeTruthy();
        expect(tab.label, `missing tab label for ${workspaceId}:${fileId}`).toBeTruthy();
        expect(tab.icon, `missing tab icon for ${workspaceId}:${fileId}`).toBeTruthy();
        expect(tab.kind, `missing tab kind for ${workspaceId}:${fileId}`).toBeTruthy();
      }
    }
  });
});

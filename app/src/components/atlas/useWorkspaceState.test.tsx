import { act, renderHook } from "@testing-library/react";
import { beforeEach, describe, expect, it } from "vitest";
import { useWorkspaceState } from "./useWorkspaceState";

describe("useWorkspaceState", () => {
  beforeEach(() => {
    window.localStorage.clear();
  });

  it("opens the inspector when a citation is selected", () => {
    const { result } = renderHook(() => useWorkspaceState("caspian"));

    act(() => {
      result.current.handleCitation("c_1042");
    });

    expect(result.current.citationId).toBe("c_1042");
    expect(result.current.rightPaneFocus).toBe("inspector");
    expect(result.current.panes.inspector).toBe(true);
  });

  it("tracks the selected file and activates its workbench tab", () => {
    const { result } = renderHook(() => useWorkspaceState("second-opinion"));

    act(() => {
      result.current.handleOpenFile({
        type: "file",
        id: "f_referral",
        name: "referral-packet.md",
        ext: "md",
        icon: "FileText",
      });
    });

    expect(result.current.activeFileId).toBe("f_referral");
    expect(result.current.activeTabId).toBe("tab_referral");
    expect(result.current.tabs.some((tab) => tab.id === "tab_referral")).toBe(true);
  });

  it("falls back to the next open tab when the active tab closes", () => {
    const { result } = renderHook(() => useWorkspaceState("caspian"));

    expect(result.current.activeTabId).toBe("tab_brief");

    act(() => {
      result.current.handleCloseTab("tab_brief");
    });

    expect(result.current.activeTabId).toBe("tab_anti");
  });

  it("persists the active session, tab, file, citation, and inspector tab across remounts", () => {
    const first = renderHook(() => useWorkspaceState("trial-finder"));

    act(() => {
      first.result.current.setActiveSessionId("r_live123");
      first.result.current.handleSelectTab("tab_man");
      first.result.current.handleOpenFile({
        type: "file",
        id: "f_geo",
        name: "geography.json",
        ext: "json",
        icon: "Braces",
      });
      first.result.current.handleCitation("c_1042");
      first.result.current.setInspectorTab("context");
    });

    first.unmount();

    const second = renderHook(() => useWorkspaceState("trial-finder"));

    expect(second.result.current.activeSessionId).toBe("r_live123");
    expect(second.result.current.activeTabId).toBe("tab_geo");
    expect(second.result.current.activeFileId).toBe("f_geo");
    expect(second.result.current.citationId).toBe("c_1042");
    expect(second.result.current.inspectorTab).toBe("context");
  });
});

import type { ReactNode } from "react";
import { render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { PluginWorkspace } from "./Workspace";

const workspaceFrameSpy = vi.fn();
const startRunMock = vi.fn();

vi.mock("../../components/atlas/AppShell", () => ({
  AppShell: ({ children }: { children: ReactNode }) => <div data-testid="app-shell">{children}</div>,
}));

vi.mock("../../components/atlas/WorkspaceFrame", () => ({
  WorkspaceFrame: (props: unknown) => {
    workspaceFrameSpy(props);
    return <div data-testid="workspace-frame" />;
  },
}));

vi.mock("../../components/atlas/PluginRunChatPane", () => ({
  PluginRunChatPane: () => <div data-testid="plugin-run-chat" />,
}));

vi.mock("../../api/plugins", () => ({
  pluginsApi: {
    startRun: (...args: unknown[]) => startRunMock(...args),
  },
}));

vi.mock("../../components/atlas/manifests", async (importOriginal) => {
  const actual = await importOriginal<typeof import("../../components/atlas/manifests")>();
  return {
    ...actual,
    useManifest: () => ({
      data: {
        id: "trial-finder",
        displayName: "Trial Finder",
        subtitle: "Plugin",
        version: "2.4.1",
        vendor: { name: "Helix Clinical" },
        color: "#4338ca",
        icon: "Telescope",
        trust: { boundaryLabel: "Consented external · registry lookup" },
        permissions: [{ kind: "read-anchor", scope: ["diagnoses.active"] }],
        connectors: [],
        anchor: { scope: ["diagnoses.active"], redactionPreset: "de-id-v3" },
        ui: {
          homeSections: ["hero"],
          workbenchTabs: [
            { id: "candidate-board", label: "Candidate board", kind: "trial-board", renderer: "trial.board" },
          ],
          files: [{ group: "working", name: "ranked-shortlist.md", icon: "FileText" }],
          agent: { avatarInitials: "Tf", avatarColor: "var(--mod-trials)", modelPreset: "marketplace-act" },
        },
      },
      isLoading: false,
      isError: false,
    }),
    useRunsForPlugin: () => ({
      data: [
        {
          id: "r_live123",
          title: "Live run",
          workflowId: "shortlist",
          startedAt: "2026-05-10T19:45:00Z",
          completedAt: null,
          state: "running",
        },
      ],
    }),
  };
});

vi.mock("../../components/atlas/usePluginRun", () => ({
  usePluginRun: () => ({
    run: {
      id: "r_live123",
      pluginId: "trial-finder",
      pluginVersion: "2.4.1",
      patientId: "8.4127.881",
      state: "running",
      workflowId: "shortlist",
      title: "Live run",
      startedBy: { id: "u_1", name: "Dr. Q", role: "clinician" },
      startedAt: "2026-05-10T19:45:00Z",
      completedAt: null,
      anchor: {
        schemaVersion: "1.0.0",
        pluginId: "trial-finder",
        pluginVersion: "2.4.1",
        patientId: "8.4127.881",
        runId: "r_live123",
        issuedAt: "2026-05-10T19:45:00Z",
        expiresAt: "2026-05-10T20:45:00Z",
        redactionPreset: "de-id-v3",
        scope: ["diagnoses.active"],
        data: { "diagnoses.active": [{ display: "Chronic myeloid leukemia" }] },
        signature: "sig-demo",
      },
      canvas: {},
    },
    events: [],
    approvals: [],
    canvas: {},
    pendingApproval: undefined,
    isLoading: false,
    grantConsent: vi.fn(),
    revokeConsent: vi.fn(),
    callTool: vi.fn(),
    requestApproval: vi.fn(),
    approve: vi.fn(),
    deny: vi.fn(),
  }),
}));

describe("PluginWorkspace", () => {
  beforeEach(() => {
    workspaceFrameSpy.mockReset();
    startRunMock.mockReset();
  });

  it("routes live plugin runs through WorkspaceFrame with a live surface", () => {
    render(
      <MemoryRouter initialEntries={["/workspaces/trial-finder/sessions/r_live123"]}>
        <Routes>
          <Route path="/workspaces/:pluginId/sessions/:sessionId" element={<PluginWorkspace />} />
        </Routes>
      </MemoryRouter>,
    );

    expect(screen.getByTestId("workspace-frame")).toBeInTheDocument();
    const props = workspaceFrameSpy.mock.calls.at(-1)?.[0] as {
      activeSessionId: string;
      surface?: { runId?: string; chatPane?: ReactNode };
    };
    expect(props.activeSessionId).toBe("r_live123");
    expect(props.surface?.runId).toBe("r_live123");
    expect(props.surface?.chatPane).toBeTruthy();
  });

  it("passes the selected patient into plugin run creation", async () => {
    startRunMock.mockResolvedValue({ id: "r_new123" });

    render(
      <MemoryRouter initialEntries={["/workspaces/trial-finder?patient=demo-trial-match"]}>
        <Routes>
          <Route path="/workspaces/:pluginId" element={<PluginWorkspace />} />
        </Routes>
      </MemoryRouter>,
    );

    const props = workspaceFrameSpy.mock.calls.at(-1)?.[0] as {
      onStartRun?: (workflowId?: string) => void;
    };
    props.onStartRun?.("shortlist");

    await waitFor(() =>
      expect(startRunMock).toHaveBeenCalledWith(
        expect.objectContaining({
          pluginId: "trial-finder",
          patientId: "demo-trial-match",
          workflowId: "shortlist",
        }),
      ),
    );
  });
});

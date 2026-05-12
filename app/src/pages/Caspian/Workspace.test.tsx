import type { ReactNode } from "react";
import { useEffect } from "react";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { AccessProvider } from "../../context/AccessContext";
import type { AuthSessionResponse } from "../../types";
import { CaspianWorkspace } from "./Workspace";

function renderWithProviders(ui: ReactNode) {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <QueryClientProvider client={queryClient}>{ui}</QueryClientProvider>,
  );
}

const workspaceFrameSpy = vi.fn();
const togglePaneSpy = vi.fn();
const setInspectorTabSpy = vi.fn();
const focusCitationSpy = vi.fn();
const {
  getAuthSessionMock,
  getCapabilitiesMock,
  listCaspianFilesMock,
  readCaspianFileMock,
  writeCaspianFileMock,
  saveCaspianFileAsNoteMock,
} = vi.hoisted(() => ({
  getAuthSessionMock: vi.fn<() => Promise<AuthSessionResponse>>(),
  getCapabilitiesMock: vi.fn(),
  listCaspianFilesMock: vi.fn(),
  readCaspianFileMock: vi.fn(),
  writeCaspianFileMock: vi.fn(),
  saveCaspianFileAsNoteMock: vi.fn(),
}));

vi.mock("../../api/client", () => ({
  api: {
    getAuthSession: getAuthSessionMock,
    getCapabilities: getCapabilitiesMock,
    login: vi.fn(),
    logout: vi.fn(),
    enterDemo: vi.fn(),
    selectActivePatient: vi.fn(),
    listCaspianFiles: listCaspianFilesMock,
    readCaspianFile: readCaspianFileMock,
    writeCaspianFile: writeCaspianFileMock,
    saveCaspianFileAsNote: saveCaspianFileAsNoteMock,
  },
}));

vi.mock("../../components/atlas/AppShell", () => ({
  AppShell: ({ children }: { children: ReactNode }) => <div data-testid="app-shell">{children}</div>,
}));

vi.mock("../../components/atlas/WorkspaceFrame", () => ({
  WorkspaceFrame: (props: {
    onControlsChange?: (controls: {
      panes: { inspector: boolean };
      togglePane: (pane: string) => void;
      focusCitation: (id: string) => void;
      activeCitationId: string | null;
      setInspectorTab: (tab: string) => void;
    }) => void;
    surface?: { chatPane?: ReactNode; inspector?: { citations?: Record<string, { title: string }> } };
    activeSessionId: string;
  }) => {
    workspaceFrameSpy(props);

    useEffect(() => {
      props.onControlsChange?.({
        panes: { inspector: true },
        togglePane: togglePaneSpy,
        focusCitation: focusCitationSpy,
        activeCitationId: null,
        setInspectorTab: setInspectorTabSpy,
      });
    }, [props.onControlsChange]);

    return (
      <div data-testid="workspace-frame">
        {props.surface?.chatPane}
      </div>
    );
  },
}));

vi.mock("../../components/atlas/useCaspianAssistantSession", () => ({
  useCaspianAssistantSession: () => ({
    messages: [
      {
        id: "a_1",
        role: "assistant",
        content: "Apixaban is active and should be reviewed pre-op.",
        confidence: "high",
        engine: "anthropic-agent-sdk",
        citations: [
          {
            id: "e_1",
            source_type: "MedicationStatement",
            resource_id: "med-1",
            label: "Apixaban 5 mg BID",
            detail: "Active medication documented in the chart.",
            event_date: "2025-04-02",
          },
        ],
        followUps: [],
        trace: {
          trace_id: "trace_live_2",
          duration_ms: 830,
          input_tokens: 210,
          output_tokens: 90,
          total_cost_usd: 0.006,
          tool_calls: [
            {
              tool_name: "query_chart_evidence",
              input_summary: "Query: active meds",
              output_summary: "2 facts, 1 citation",
              duration_ms: 110,
              error: null,
            },
          ],
          system_prompt_preview: "",
          retrieved_facts: [],
          model_used: "claude-sonnet-4-5",
          mode_used: "anthropic",
          max_tokens_used: 2000,
          context_token_estimate: 500,
          history_turns_sent: 0,
        },
        createdAt: "2026-05-10T20:10:00Z",
      },
    ],
    isPending: false,
    isError: false,
    error: null,
    submitQuestion: vi.fn(),
    resetConversation: vi.fn(),
    inspector: {
      citations: {
        e_1: {
          id: "e_1",
          type: "MedicationStatement",
          title: "Apixaban 5 mg BID",
          snippet: "Active medication documented in the chart.",
          source: "med-1",
          encounter: "Observed 2025-04-02",
          author: "MedicationStatement",
          date: "2025-04-02",
          related: [],
        },
      },
      traceByCitationId: {},
      latestTrace: null,
      contextItems: [{ label: "Patient", value: "patient-123" }],
    },
    workflow: {
      tabs: [],
      canvas: {},
      latestTabId: null,
      isPending: false,
      pendingWorkflowId: null,
      error: null,
    },
    runWorkflow: vi.fn(),
    acknowledgeLatestWorkflow: vi.fn(),
  }),
}));

describe("CaspianWorkspace", () => {
  beforeEach(() => {
    workspaceFrameSpy.mockReset();
    togglePaneSpy.mockReset();
    setInspectorTabSpy.mockReset();
    focusCitationSpy.mockReset();
    listCaspianFilesMock.mockReset();
    readCaspianFileMock.mockReset();
    writeCaspianFileMock.mockReset();
    saveCaspianFileAsNoteMock.mockReset();
    listCaspianFilesMock.mockResolvedValue({
      workspace_key: "test-key",
      tree: [],
      capabilities: null,
    });
    readCaspianFileMock.mockResolvedValue({
      path: "",
      content: "",
      mtime: null,
      editable: false,
      kind: "markdown",
      file_kind: "user",
    });
    getAuthSessionMock.mockResolvedValue({
      mode: "authenticated",
      user: {
        id: "user_1",
        email: "clinician@atlas.local",
        display_name: "Atlas Clinician",
        role: "clinician",
      },
      active_patient_id: "patient-123",
      active_patient_name: "Patient 123",
      expires_at: null,
      available_demo_patients: [],
    });
    getCapabilitiesMock.mockResolvedValue({
      mode: "authenticated",
      can_use_caspian: true,
      can_edit_caspian_user_files: true,
      can_write_caspian_notes: true,
      can_run_workflows: true,
      can_use_aggregation_uploads: true,
      can_use_aggregation_profiles: true,
      can_use_harmonize: true,
      can_use_guest_harmonization: true,
      can_use_assistant_tools_write: true,
      show_caspian_seed_files: false,
      persistence_scope: "browser-persistent",
    });
  });

  it("routes the canonical /caspian shell through WorkspaceFrame with a live assistant surface", async () => {
    renderWithProviders(
      <MemoryRouter initialEntries={["/caspian/sessions/s2?patient=patient-123"]}>
        <AccessProvider>
          <Routes>
            <Route path="/caspian/sessions/:sessionId" element={<CaspianWorkspace />} />
          </Routes>
        </AccessProvider>
      </MemoryRouter>,
    );

    await waitFor(() => expect(screen.getByTestId("workspace-frame")).toBeInTheDocument());
    const props = workspaceFrameSpy.mock.calls.at(-1)?.[0] as {
      activeSessionId: string;
      surface?: { chatPane?: ReactNode; inspector?: { citations?: Record<string, { title: string }> } };
    };

    expect(props.activeSessionId).toBe("s2");
    expect(props.surface?.chatPane).toBeTruthy();
    expect(props.surface?.inspector?.citations?.e_1?.title).toBe("Apixaban 5 mg BID");
  });

  it("shows a start state instead of the workspace shell when no patient is selected", async () => {
    getAuthSessionMock.mockResolvedValueOnce({
      mode: "authenticated",
      user: {
        id: "user_1",
        email: "clinician@atlas.local",
        display_name: "Atlas Clinician",
        role: "clinician",
      },
      active_patient_id: null,
      active_patient_name: null,
      expires_at: null,
      available_demo_patients: [],
    });
    renderWithProviders(
      <MemoryRouter initialEntries={["/caspian"]}>
        <AccessProvider>
          <Routes>
            <Route path="/caspian" element={<CaspianWorkspace />} />
          </Routes>
        </AccessProvider>
      </MemoryRouter>,
    );

    await waitFor(() => {
      expect(screen.queryByTestId("workspace-frame")).not.toBeInTheDocument();
      expect(
        screen.getByText("Choose a sample chart before opening Caspian."),
      ).toBeInTheDocument();
    });
  });

  it("opens the trace tab without toggling the inspector closed when it is already visible", async () => {
    renderWithProviders(
      <MemoryRouter initialEntries={["/caspian/sessions/s2?patient=patient-123"]}>
        <AccessProvider>
          <Routes>
            <Route path="/caspian/sessions/:sessionId" element={<CaspianWorkspace />} />
          </Routes>
        </AccessProvider>
      </MemoryRouter>,
    );

    await waitFor(() => expect(screen.getByText("1 tool calls")).toBeInTheDocument());
    fireEvent.click(screen.getByText("1 tool calls"));

    expect(togglePaneSpy).not.toHaveBeenCalled();
    expect(setInspectorTabSpy).toHaveBeenCalledWith("trace");
  });
});

import type { ReactNode } from "react";
import { act, renderHook, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { useCaspianAssistantSession } from "./useCaspianAssistantSession";
import { AccessProvider } from "../../context/AccessContext";

const { chatProviderAssistantStream, getAuthSession, getCapabilities } = vi.hoisted(() => ({
  chatProviderAssistantStream: vi.fn(),
  getAuthSession: vi.fn(),
  getCapabilities: vi.fn(),
}));

vi.mock("../../api/client", () => ({
  api: {
    chatProviderAssistantStream: (...args: unknown[]) =>
      chatProviderAssistantStream(...args),
    getAuthSession: (...args: unknown[]) => getAuthSession(...args),
    getCapabilities: (...args: unknown[]) => getCapabilities(...args),
  },
}));

function wrapper({ children }: { children: ReactNode }) {
  return (
    <QueryClientProvider client={new QueryClient()}>
      <AccessProvider>{children}</AccessProvider>
    </QueryClientProvider>
  );
}

const trace = {
  trace_id: "trace_live_1",
  duration_ms: 1240,
  input_tokens: 320,
  output_tokens: 140,
  total_cost_usd: 0.0123,
  tool_calls: [
    {
      tool_name: "query_chart_evidence",
      input_summary: "Query: active anticoagulants",
      output_summary: "3 facts, 2 citations",
      duration_ms: 210,
      error: null,
    },
  ],
  system_prompt_preview: "clinical system prompt",
  retrieved_facts: ["Apixaban active", "Hgb 12.4"],
  model_used: "claude-sonnet-4-5",
  mode_used: "anthropic",
  max_tokens_used: 2000,
  context_token_estimate: 900,
  history_turns_sent: 0,
};

describe("useCaspianAssistantSession", () => {
  beforeEach(() => {
    window.localStorage.clear();
    chatProviderAssistantStream.mockReset();
    getAuthSession.mockReset();
    getCapabilities.mockReset();
    // Default the AccessContext to an anonymous session so the hook can
    // still derive a storage key for the test patient + session.
    getAuthSession.mockResolvedValue({
      mode: "anonymous",
      user: null,
      active_patient_id: null,
      active_patient_name: null,
      active_demo_patient: null,
      expires_at: null,
      available_demo_patients: [],
    });
    getCapabilities.mockResolvedValue({
      mode: "anonymous",
      can_use_caspian: false,
      can_edit_caspian_user_files: false,
      can_write_caspian_notes: false,
      can_run_workflows: false,
      can_use_aggregation_uploads: false,
      can_use_aggregation_profiles: false,
      can_use_harmonize: false,
      can_use_guest_harmonization: true,
      can_use_assistant_tools_write: false,
      show_caspian_seed_files: false,
      persistence_scope: "none",
    });
  });

  it("submits to the live assistant API and builds inspector-ready citations", async () => {
    const assistantResponse = {
      patient_id: "patient-123",
      answer: "Active apixaban is the main pre-op medication risk.",
      confidence: "high",
      stance: "opinionated",
      engine: "anthropic-agent-sdk",
      citations: [
        {
          source_type: "MedicationStatement",
          resource_id: "med-1",
          label: "Apixaban 5 mg BID",
          detail: "Active medication documented in the chart.",
          event_date: "2025-04-02",
        },
      ],
      follow_ups: ["Should it be held before surgery?"],
      trace,
    };

    // The mock plays back a realistic stream: one tool_start/tool_end pair and
    // then a `done` event carrying the final response, exactly as the SSE
    // endpoint emits.
    chatProviderAssistantStream.mockImplementation(
      async (
        _payload: unknown,
        callbacks: { onEvent: (event: Record<string, unknown>) => void },
      ) => {
        callbacks.onEvent({
          type: "status",
          phase: "starting",
          message: "Initializing Caspian harness and preparing chart evidence.",
        });
        callbacks.onEvent({
          type: "tool_start",
          id: "t1",
          tool: "query_chart_evidence",
          input_summary: "Query: active anticoagulants",
        });
        callbacks.onEvent({
          type: "tool_end",
          id: "t1",
          tool: "query_chart_evidence",
          output_summary: "3 facts, 2 citations",
          duration_ms: 12,
          error: null,
        });
        callbacks.onEvent({ type: "done", response: assistantResponse });
      },
    );

    const { result } = renderHook(
      () => useCaspianAssistantSession("patient-123", "s_live"),
      { wrapper },
    );

    await act(async () => {
      result.current.submitQuestion("Any pre-op medication risks?");
    });

    await waitFor(() => {
      expect(chatProviderAssistantStream).toHaveBeenCalled();
    });
    expect(chatProviderAssistantStream.mock.calls[0][0]).toMatchObject({
      patient_id: "patient-123",
      question: "Any pre-op medication risks?",
      history: [],
      stance: "opinionated",
    });

    await waitFor(() => {
      expect(result.current.messages).toHaveLength(2);
    });

    const assistantMessage = result.current.messages[1];
    expect(assistantMessage.role).toBe("assistant");
    if (assistantMessage.role !== "assistant") return;

    expect(assistantMessage.engine).toBe("anthropic-agent-sdk");
    expect(assistantMessage.citations[0]?.id).toBe("e_1");
    expect(result.current.inspector.citations["e_1"]?.title).toBe("Apixaban 5 mg BID");
    expect(result.current.inspector.citations["e_1"]?.source).toBe("MedicationStatement/med-1");
    expect(result.current.inspector.citations["e_1"]?.sourceType).toBe("MedicationStatement");
    expect(result.current.inspector.citations["e_1"]?.sourceId).toBe("med-1");
    expect(result.current.inspector.traceByCitationId["e_1"]?.trace_id).toBe("trace_live_1");

    const stored = window.localStorage.getItem(
      "atlas:anon:caspian:assistant:patient-123:s_live",
    );
    expect(stored).toContain("Any pre-op medication risks?");
    expect(stored).toContain("Apixaban 5 mg BID");
  });

  it("surfaces an immediate pending status before tool activity arrives", async () => {
    let resolveStream: (() => void) | null = null;
    chatProviderAssistantStream.mockImplementation(
      async (
        _payload: unknown,
        callbacks: { onEvent: (event: Record<string, unknown>) => void },
      ) =>
        new Promise<void>((resolve) => {
          resolveStream = () => {
            callbacks.onEvent({
              type: "done",
              response: {
                patient_id: "patient-123",
                answer: "No immediate blocker found.",
                confidence: "medium",
                stance: "opinionated",
                engine: "anthropic-agent-sdk",
                citations: [],
                follow_ups: [],
                trace: null,
              },
            });
            resolve();
          };
        }),
    );

    const { result } = renderHook(
      () => useCaspianAssistantSession("patient-123", "s_pending"),
      { wrapper },
    );

    act(() => {
      result.current.submitQuestion("Give me the top issue.");
    });

    await waitFor(() => {
      expect(result.current.isPending).toBe(true);
      expect(result.current.pendingStatus).toBe("Starting Caspian harness…");
    });

    await act(async () => {
      resolveStream?.();
    });

    await waitFor(() => {
      expect(result.current.isPending).toBe(false);
      expect(result.current.pendingStatus).toBeNull();
    });
  });
});

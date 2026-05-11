import type { ReactNode } from "react";
import { act, renderHook, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { useCaspianAssistantSession } from "./useCaspianAssistantSession";

const { chatProviderAssistant } = vi.hoisted(() => ({
  chatProviderAssistant: vi.fn(),
}));

vi.mock("../../api/client", () => ({
  api: {
    chatProviderAssistant: (...args: unknown[]) => chatProviderAssistant(...args),
  },
}));

function wrapper({ children }: { children: ReactNode }) {
  return (
    <QueryClientProvider client={new QueryClient()}>
      {children}
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
    chatProviderAssistant.mockReset();
  });

  it("submits to the live assistant API and builds inspector-ready citations", async () => {
    chatProviderAssistant.mockResolvedValue({
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
    });

    const { result } = renderHook(
      () => useCaspianAssistantSession("patient-123", "s_live"),
      { wrapper },
    );

    await act(async () => {
      result.current.submitQuestion("Any pre-op medication risks?");
    });

    await waitFor(() => {
      expect(chatProviderAssistant).toHaveBeenCalledWith({
        patient_id: "patient-123",
        question: "Any pre-op medication risks?",
        history: [],
        stance: "opinionated",
      });
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
    expect(result.current.inspector.traceByCitationId["e_1"]?.trace_id).toBe("trace_live_1");

    const stored = window.localStorage.getItem("atlas:caspian:assistant:patient-123:s_live");
    expect(stored).toContain("Any pre-op medication risks?");
    expect(stored).toContain("Apixaban 5 mg BID");
  });
});

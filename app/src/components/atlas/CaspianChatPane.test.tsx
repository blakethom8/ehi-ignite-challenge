import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { CaspianChatPane } from "./CaspianChatPane";

const trace = {
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
};

describe("CaspianChatPane", () => {
  it("opens citations and trace actions from live assistant messages", () => {
    const onSubmit = vi.fn();
    const onReset = vi.fn();
    const onCitationClick = vi.fn();
    const onOpenTrace = vi.fn();

    render(
      <CaspianChatPane
        patientId="patient-123"
        sessionTitle="Pre-op clearance"
        messages={[
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
            followUps: ["Should it be held before surgery?"],
            trace,
            createdAt: "2026-05-10T20:10:00Z",
          },
        ]}
        isPending={false}
        error={null}
        activeCitationId={null}
        onSubmit={onSubmit}
        onReset={onReset}
        onCitationClick={onCitationClick}
        onOpenTrace={onOpenTrace}
      />,
    );

    fireEvent.click(screen.getByText("e_1"));
    expect(onCitationClick).toHaveBeenCalledWith("e_1");

    fireEvent.click(screen.getByText("1 tool calls"));
    expect(onOpenTrace).toHaveBeenCalledTimes(1);

    fireEvent.click(screen.getByText("Should it be held before surgery?"));
    expect(onSubmit).toHaveBeenCalledWith("Should it be held before surgery?");
  });
});

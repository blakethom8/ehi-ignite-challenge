import { describe, expect, it } from "vitest";
import { buildCanvas } from "./usePluginRun";

describe("buildCanvas", () => {
  it("merges persisted run canvas with streamed tool results", () => {
    const canvas = buildCanvas(
      {
        "packet.draft": {
          artifactId: "outreach-packet-NCT-0421187",
          preview: "# Outreach packet",
        },
      },
      [
        {
          id: "evt_1",
          runId: "r_live",
          ts: "2026-05-10T20:00:00Z",
          kind: "tool.result",
          payload: {
            toolId: "trial.search",
            result: { studies: [{ nctId: "NCT-0421187" }] },
          },
        },
      ],
    );

    expect(canvas["packet.draft"]).toEqual({
      artifactId: "outreach-packet-NCT-0421187",
      preview: "# Outreach packet",
    });
    expect(canvas["trial.search"]).toEqual({ studies: [{ nctId: "NCT-0421187" }] });
  });
});

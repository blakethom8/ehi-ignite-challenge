import type { CitationOut, InvokeSuccess } from "./types.js";

const FENCED = /```(?:json)?\s*(\{[\s\S]*\})\s*```/;

export function parseModelJson(text: string): Record<string, unknown> {
  let cleaned = text.trim();
  const fenced = FENCED.exec(cleaned);
  if (fenced) cleaned = fenced[1]!.trim();
  try {
    const v = JSON.parse(cleaned);
    if (v && typeof v === "object" && !Array.isArray(v)) return v as Record<string, unknown>;
  } catch {
    /* fall through */
  }
  const start = cleaned.indexOf("{");
  const end = cleaned.lastIndexOf("}");
  if (start >= 0 && end > start) {
    const slice = cleaned.slice(start, end + 1);
    const v = JSON.parse(slice);
    if (v && typeof v === "object" && !Array.isArray(v)) return v as Record<string, unknown>;
  }
  throw new Error("Model did not return a JSON object");
}

function normalizeCitations(raw: unknown): CitationOut[] {
  if (!Array.isArray(raw)) return [];
  const out: CitationOut[] = [];
  for (const item of raw) {
    if (!item || typeof item !== "object") continue;
    const o = item as Record<string, unknown>;
    const source_type = String(o.source_type ?? "").trim();
    const resource_id = String(o.resource_id ?? "").trim();
    if (!source_type || !resource_id) continue;
    out.push({
      source_type,
      resource_id,
      label: String(o.label ?? "").trim() || resource_id,
      detail: String(o.detail ?? "").trim() || "No detail provided.",
      event_date: o.event_date === null || o.event_date === undefined ? null : String(o.event_date),
    });
  }
  return out;
}

function normalizeFollowUps(raw: unknown): string[] {
  if (!Array.isArray(raw)) return [];
  const seen = new Set<string>();
  const out: string[] = [];
  for (const x of raw) {
    const t = String(x).trim();
    if (t && !seen.has(t)) {
      seen.add(t);
      out.push(t);
    }
  }
  return out.slice(0, 3);
}

export function buildSuccess(
  rawText: string,
  modelUsed: string,
  runId: string | undefined,
  durationMs: number | undefined
): InvokeSuccess {
  const parsed = parseModelJson(rawText);
  let answer = String(parsed.answer ?? "").trim();
  if (!answer) {
    answer =
      "Short answer: I could not produce a defensible answer from the baseline chart evidence.";
  }
  let confidence = String(parsed.confidence ?? "medium").toLowerCase();
  if (!["high", "medium", "low"].includes(confidence)) confidence = "medium";
  return {
    answer,
    confidence,
    citations: normalizeCitations(parsed.citations),
    follow_ups: normalizeFollowUps(parsed.follow_ups),
    engine: "cursor-sdk-sidecar",
    model_used: modelUsed,
    run_id: runId,
    duration_ms: durationMs,
  };
}

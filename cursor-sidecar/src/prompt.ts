import type { InvokeRequest } from "./types.js";

function historyLines(history: InvokeRequest["history"]): string {
  if (!history?.length) return "(no prior turns)";
  const lines: string[] = [];
  for (const turn of history.slice(-6)) {
    const role = (turn.role || "user").toLowerCase();
    const content = (turn.content || "").trim();
    if (!content) continue;
    lines.push(`${role === "user" ? "Provider" : "Assistant"}: ${content}`);
  }
  return lines.length ? lines.join("\n") : "(no prior turns)";
}

/** Single user message for Agent.prompt — baseline evidence is the chart grounding surface (tools/MCP can extend this later). */
export function buildUserPrompt(req: InvokeRequest): string {
  const baseline =
    req.baseline_evidence !== undefined
      ? JSON.stringify(req.baseline_evidence, null, 0)
      : "(no baseline; caller should supply baseline_evidence)";
  return [
    "You are handling a provider chart question for a single patient.",
    "Task: answer the provider directly using ONLY the baseline evidence JSON below and general clinical reasoning that does not invent chart facts.",
    "",
    `patient_id: ${req.patient_id}`,
    `stance: ${req.stance}`,
    `provider_question: ${req.question}`,
    "",
    "Recent conversation context:",
    historyLines(req.history),
    "",
    "Baseline chart evidence (authoritative for factual claims):",
    baseline,
    "",
    "Rules:",
    "1) Do not invent medications, diagnoses, dates, or resource ids.",
    "2) If baseline evidence is insufficient, say so and lower confidence.",
    "3) Keep the answer concise and actionable.",
    "",
    "Return ONLY JSON with this schema (no markdown fences):",
    '{ "answer": string, "confidence": "high"|"medium"|"low",',
    '  "citations": [ { "source_type": string, "resource_id": string, "label": string, "detail": string, "event_date": string|null } ],',
    '  "follow_ups": string[] }',
  ].join("\n");
}

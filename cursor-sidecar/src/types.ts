export type HistoryTurn = { role: string; content: string };

export type InvokeRequest = {
  patient_id: string;
  question: string;
  stance: string;
  history?: HistoryTurn[] | null;
  baseline_evidence?: unknown;
  /** Resolved model id (already allow-listed by API when applicable). */
  model?: string | null;
};

export type CitationOut = {
  source_type: string;
  resource_id: string;
  label: string;
  detail: string;
  event_date?: string | null;
};

export type InvokeSuccess = {
  answer: string;
  confidence: string;
  citations: CitationOut[];
  follow_ups: string[];
  engine: string;
  model_used: string;
  run_id?: string;
  duration_ms?: number;
};

export type InvokeErrorBody = {
  code: "config" | "execution" | "timeout" | "bad_request";
  message: string;
};

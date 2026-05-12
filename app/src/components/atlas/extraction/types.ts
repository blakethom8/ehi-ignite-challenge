/**
 * Neutral progress shape that both the authenticated extract-job and the
 * Guest harmonization progress block can satisfy.
 *
 * Lets `PdfPageProgressMap` + `PdfExtractionEventTimeline` render either
 * surface without coupling to a specific Pydantic response model.
 */
export interface ExtractionProgressEvent {
  event_id: string;
  event_type: string;
  created_at: string;
  stage: string | null;
  message: string;
  source_id?: string | null;
  source_label: string | null;
  page_start: number | null;
  page_end: number | null;
  page_count: number | null;
  processed_pages: number | null;
  total_pages: number | null;
  processed_files: number | null;
  total_files: number | null;
  progress_basis: string | null;
  is_estimate?: boolean | null;
}

export interface ExtractionProgress {
  status: "pending" | "running" | "complete" | "failed";
  stage: string;
  total_files: number;
  processed_files: number;
  total_pages: number | null;
  processed_pages: number;
  estimated_processed_pages?: number | null;
  current_source_label?: string | null;
  progress_mode: "lifecycle" | "reported" | "estimated" | "metadata";
  events: ExtractionProgressEvent[];
}

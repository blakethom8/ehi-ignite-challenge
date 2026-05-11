/**
 * Renderer contract.
 *
 * Per HARNESS-SURFACES §8: renderers are pure projections. They
 * never fetch, mutate, or derive — they consume structured tool
 * results from the run's canvas state and project them visually.
 */

import type { ReactNode } from "react";
import type { WorkbenchRenderer } from "../trust";

export type RendererProps = {
  runId: string | null;
  /** Live canvas state for the active run, keyed by artifact id / canvas key. */
  canvas: Record<string, unknown>;
  /** The manifest tab spec this renderer was instantiated for. */
  tabId: string;
  /** Click handler for citation chips inside the renderer. */
  onCitationClick?: (id: string) => void;
};

export type RendererComponent = (props: RendererProps) => ReactNode;

export type RendererRegistry = Record<WorkbenchRenderer, RendererComponent>;

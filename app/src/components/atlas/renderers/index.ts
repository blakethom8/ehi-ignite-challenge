/**
 * Renderer registry.
 *
 * Each `WorkbenchRenderer` key in the manifest's `ui.workbenchTabs`
 * maps to a renderer component here. Adding a new renderer is a
 * three-line change: import the component, register the key, write
 * the component. Plugin-specific renderers live under
 * `renderers/{plugin}/` per HARNESS-SURFACES §6.3.
 */

import type { RendererRegistry } from "./types";
import { JsonViewerRenderer } from "./shared/JsonViewerRenderer";
import { MarkdownDocRenderer } from "./shared/MarkdownDocRenderer";
import { NetworkStatusBoardRenderer } from "./shared/NetworkStatusBoardRenderer";
import { UnifiedDiffRenderer } from "./shared/UnifiedDiffRenderer";
import { EligibilityFormRenderer } from "./trial-finder/EligibilityFormRenderer";
import { TrialBoardRenderer } from "./trial-finder/TrialBoardRenderer";
import { TrialDetailRenderer } from "./trial-finder/TrialDetailRenderer";
import { BarriersListRenderer } from "./med-access/BarriersListRenderer";
import { ManufacturerMatcherRenderer } from "./med-access/ManufacturerMatcherRenderer";
import { PaFormRenderer } from "./med-access/PaFormRenderer";
import { ReferralPacketRenderer } from "./second-opinion/ReferralPacketRenderer";
import { SpecialtyPickerRenderer } from "./second-opinion/SpecialtyPickerRenderer";
import { WorkflowArtifactRenderer } from "./caspian/WorkflowArtifactRenderer";
import { WorkspaceFileRenderer } from "./caspian/WorkspaceFileRenderer";

export const RENDERERS: RendererRegistry = {
  "workflow.artifact": WorkflowArtifactRenderer,
  "workspace.file": WorkspaceFileRenderer,
  "trial.board": TrialBoardRenderer,
  "trial.detail": TrialDetailRenderer,
  "form.eligibility": EligibilityFormRenderer,
  "list.barriers": BarriersListRenderer,
  "form.pa": PaFormRenderer,
  "matcher.manufacturer": ManufacturerMatcherRenderer,
  "picker.specialty": SpecialtyPickerRenderer,
  "packet.referral": ReferralPacketRenderer,
  "board.network-status": NetworkStatusBoardRenderer,
  "markdown.doc": MarkdownDocRenderer,
  "json.viewer": JsonViewerRenderer,
  "diff.unified": UnifiedDiffRenderer,
};

export type { RendererProps, RendererComponent, RendererRegistry } from "./types";

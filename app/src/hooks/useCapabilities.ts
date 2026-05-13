// useCapabilities — the single read-surface for server-declared capability
// flags. Components should NEVER re-derive policy from `mode` directly;
// always consult capabilities so the backend remains the source of truth.

import { useAccessContext } from "../context/AccessContext";
import type { Capabilities } from "../types";

/**
 * All-false fallback used while the initial fetch is in flight. Mirrors the
 * shape of an anonymous principal but errs on the safe side (no write
 * surfaces enabled until the server confirms).
 */
export const ANONYMOUS_CAPABILITIES: Capabilities = {
  mode: "anonymous",
  can_use_caspian: false,
  can_edit_caspian_user_files: false,
  can_write_caspian_notes: false,
  can_run_workflows: false,
  can_use_aggregation_uploads: false,
  can_use_aggregation_profiles: false,
  can_use_harmonize: false,
  can_use_guest_harmonization: false,
  can_use_assistant_tools_write: false,
  show_caspian_seed_files: false,
  persistence_scope: "none",
};

export function useCapabilities(): Capabilities {
  const { capabilities } = useAccessContext();
  return capabilities ?? ANONYMOUS_CAPABILITIES;
}

export function canUsePatientWorkspace(capabilities: Capabilities): boolean {
  return capabilities.mode === "authenticated" || capabilities.mode === "demo";
}

export function canManageOwnAccount(capabilities: Capabilities): boolean {
  return capabilities.mode === "authenticated";
}

// Convenience selectors — optional but handy for call sites that only need
// one flag and want a more readable boolean expression.
export function useCanUsePatientWorkspace(): boolean {
  return canUsePatientWorkspace(useCapabilities());
}

export function useCanManageOwnAccount(): boolean {
  return canManageOwnAccount(useCapabilities());
}

export function useCanEditCaspianFiles(): boolean {
  return useCapabilities().can_edit_caspian_user_files;
}

export function useCanWriteCaspianNotes(): boolean {
  return useCapabilities().can_write_caspian_notes;
}

export function useCanRunWorkflows(): boolean {
  return useCapabilities().can_run_workflows;
}

export function useShowCaspianSeedFiles(): boolean {
  return useCapabilities().show_caspian_seed_files;
}

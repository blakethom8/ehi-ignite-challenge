/**
 * Manifest loader + workspace projection.
 *
 * The backend returns *already-verified* manifests over
 * `/api/plugins/installed`. The frontend's job here is shape-narrow
 * the response into typed objects + project each manifest into a
 * `Workspace` for the existing shell components.
 *
 * Per HARNESS-SURFACES §8 (data tools vs render surfaces): this file
 * does no business logic — it shapes data the backend already owns.
 */

import { useQuery } from "@tanstack/react-query";
import { pluginsApi } from "../../api/plugins";
import type { PluginManifest } from "./trust";
import type { Workspace, WorkspaceId } from "./types";

// ============================================================
// Hooks
// ============================================================

export function useInstalledManifests() {
  return useQuery<PluginManifest[]>({
    queryKey: ["plugins", "installed"],
    queryFn: () => pluginsApi.listInstalled(),
    staleTime: 60_000,
  });
}

export function useManifest(pluginId: string | undefined) {
  return useQuery<PluginManifest>({
    queryKey: ["plugins", pluginId, "manifest"],
    queryFn: () => pluginsApi.getManifest(pluginId as string),
    enabled: Boolean(pluginId),
    staleTime: 60_000,
  });
}

export function useRunsForPlugin(pluginId: string | undefined) {
  return useQuery({
    queryKey: ["plugins", pluginId, "runs"],
    queryFn: () => pluginsApi.listRuns(pluginId as string),
    enabled: Boolean(pluginId),
    staleTime: 5_000,
  });
}

export function useProvenanceForPlugin(pluginId: string | undefined) {
  return useQuery({
    queryKey: ["plugins", pluginId, "provenance"],
    queryFn: () => pluginsApi.listPluginProvenance(pluginId as string),
    enabled: Boolean(pluginId),
    staleTime: 5_000,
  });
}

// ============================================================
// Projection
// ============================================================

function tintFromColor(color: string, alpha = 0.1): string {
  // Parse a #rrggbb into rgba(.., .., .., alpha).
  if (!color.startsWith("#") || color.length !== 7) {
    return `rgba(67, 56, 202, ${alpha})`;
  }
  const r = parseInt(color.slice(1, 3), 16);
  const g = parseInt(color.slice(3, 5), 16);
  const b = parseInt(color.slice(5, 7), 16);
  return `rgba(${r}, ${g}, ${b}, ${alpha})`;
}

function permissionLabel(p: PluginManifest["permissions"][number], m: PluginManifest): string | null {
  if (p.kind === "read-anchor") return null;
  if (p.kind === "call-external") {
    const c = m.connectors.find((c) => c.id === p.connector);
    return c ? `external · ${c.label}` : `external · ${p.connector}`;
  }
  if (p.kind === "send-outbound") return `outbound · ${p.channel}`;
  return null;
}

export function workspaceFromManifest(m: PluginManifest): Workspace {
  const permissionLabels = m.permissions
    .map((p) => permissionLabel(p, m))
    .filter((s): s is string => Boolean(s));
  // Always show the read posture once.
  permissionLabels.unshift("read patient anchors");

  return {
    id: m.id as WorkspaceId,
    family: "plugin",
    title: m.displayName,
    subtitle: m.subtitle,
    icon: m.icon,
    color: m.color,
    tint: tintFromColor(m.color),
    boundary: m.trust.boundaryLabel,
    boundaryTone: "warn",
    vendor: m.vendor.name,
    version: m.version,
    permissions: Array.from(new Set(permissionLabels)),
  };
}

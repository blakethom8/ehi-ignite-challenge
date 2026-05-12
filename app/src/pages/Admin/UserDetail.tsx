import { useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Trash2 } from "lucide-react";
import { api } from "../../api/client";
import { useAccessContext } from "../../context/AccessContext";
import { AdminLayout, formatBytes, formatRelative } from "./AdminLayout";
import type { AuthAccountStatus, AuthRole } from "../../types";

type Tab = "workspaces" | "activity" | "account";

const TABS: { id: Tab; label: string }[] = [
  { id: "workspaces", label: "Workspaces" },
  { id: "activity", label: "Activity" },
  { id: "account", label: "Account" },
];

const ROLE_OPTIONS: AuthRole[] = ["consumer", "clinician", "attending", "coordinator", "admin"];

export function AdminUserDetailPage() {
  const { userId = "" } = useParams<{ userId: string }>();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const { user: currentUser } = useAccessContext();
  const [tab, setTab] = useState<Tab>("workspaces");
  const [actionError, setActionError] = useState<string | null>(null);

  const userQuery = useQuery({
    queryKey: ["admin", "users", userId],
    queryFn: () => api.adminGetUser(userId),
    enabled: !!userId,
  });

  const activityQuery = useQuery({
    queryKey: ["admin", "users", userId, "activity"],
    queryFn: () => api.adminGetUserActivity(userId, 100),
    enabled: !!userId && tab === "activity",
  });

  const patchUser = useMutation({
    mutationFn: (payload: { role?: AuthRole; status?: AuthAccountStatus }) =>
      api.adminPatchUser(userId, payload),
    onSuccess: (next) => {
      setActionError(null);
      queryClient.setQueryData(["admin", "users", userId], next);
      queryClient.invalidateQueries({ queryKey: ["admin", "users"] });
    },
    onError: (error: unknown) => setActionError(extractErrorMessage(error)),
  });

  const deleteUser = useMutation({
    mutationFn: () => api.adminDeleteUser(userId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["admin", "users"] });
      navigate("/admin/users", { replace: true });
    },
    onError: (error: unknown) => setActionError(extractErrorMessage(error)),
  });

  if (userQuery.isLoading) {
    return (
      <AdminLayout title="Loading account…">
        <p className="text-sm text-[#62728d]">Loading…</p>
      </AdminLayout>
    );
  }

  if (userQuery.isError || !userQuery.data) {
    return (
      <AdminLayout title="Account not found">
        <p className="text-sm text-[#62728d]">{extractErrorMessage(userQuery.error)}</p>
        <Link to="/admin/users" className="mt-4 inline-block text-sm text-[#3657ff]">
          Back to users
        </Link>
      </AdminLayout>
    );
  }

  const user = userQuery.data;
  const isSelf = user.id === currentUser?.id;

  return (
    <AdminLayout title={user.display_name} subtitle={user.email}>
      {actionError && (
        <div className="mb-4 rounded-2xl border border-[#fecaca] bg-[#fef2f2] px-4 py-3 text-sm text-[#b91c1c]">
          {actionError}
        </div>
      )}

      <div className="mb-4 flex flex-wrap items-center gap-3 rounded-2xl border border-[#d8e0eb] bg-white px-4 py-3 text-sm">
        <div>
          <span className="text-[#62728d]">Role:</span>{" "}
          <select
            value={user.role}
            onChange={(event) => patchUser.mutate({ role: event.target.value as AuthRole })}
            className="ml-1 rounded-lg border border-[#d5deea] bg-white px-2 py-1 text-xs"
          >
            {ROLE_OPTIONS.map((option) => (
              <option key={option} value={option}>{option}</option>
            ))}
          </select>
        </div>
        <div>
          <span className="text-[#62728d]">Status:</span>{" "}
          <button
            type="button"
            disabled={isSelf}
            onClick={() => patchUser.mutate({ status: user.status === "active" ? "disabled" : "active" })}
            className={`ml-1 rounded-full px-2 py-[2px] text-[11px] font-semibold uppercase tracking-[0.08em] ${
              user.status === "active"
                ? "bg-[#ecfdf5] text-[#047857]"
                : "bg-[#fef3c7] text-[#b45309]"
            } ${isSelf ? "opacity-60" : "hover:bg-[#dbeafe]"}`}
          >
            {user.status}
          </button>
        </div>
        <div className="text-[#62728d]">
          Created {formatRelative(user.created_at)} · Last login {formatRelative(user.last_login_at)}
        </div>
        <div className="ml-auto flex items-center gap-2">
          <button
            type="button"
            disabled={isSelf}
            title={isSelf ? "Use Settings → Delete account to remove yourself." : "Delete this account"}
            onClick={() => {
              if (window.confirm(`Permanently delete ${user.email}? Their workspaces (${user.workspace_count}) and sessions will be wiped. Audit history is kept.`)) {
                deleteUser.mutate();
              }
            }}
            className="inline-flex items-center gap-1 rounded-lg border border-[#fecaca] bg-[#fef2f2] px-3 py-1.5 text-xs font-semibold text-[#b91c1c] hover:bg-[#fee2e2] disabled:opacity-50"
          >
            <Trash2 size={12} /> Delete account
          </button>
        </div>
      </div>

      <div className="mb-4 flex gap-1 rounded-2xl bg-[#eef2f7] p-1">
        {TABS.map((entry) => (
          <button
            key={entry.id}
            type="button"
            onClick={() => setTab(entry.id)}
            className={`flex-1 rounded-xl px-4 py-2 text-sm font-semibold transition-colors ${
              tab === entry.id
                ? "bg-white text-[#18202b] shadow-sm"
                : "text-[#62728d] hover:text-[#33415b]"
            }`}
          >
            {entry.label}
          </button>
        ))}
      </div>

      {tab === "workspaces" && (
        <div className="overflow-hidden rounded-2xl border border-[#d8e0eb] bg-white">
          {user.workspaces.length === 0 ? (
            <p className="p-6 text-sm text-[#62728d]">No workspaces yet. New uploads will be stamped to this user.</p>
          ) : (
            <table className="w-full text-sm">
              <thead className="bg-[#f8fafc] text-left text-xs uppercase tracking-[0.1em] text-[#62728d]">
                <tr>
                  <th className="px-4 py-3">Workspace</th>
                  <th className="px-4 py-3">Created</th>
                  <th className="px-4 py-3 text-right">Sources</th>
                  <th className="px-4 py-3 text-right">Storage</th>
                </tr>
              </thead>
              <tbody>
                {user.workspaces.map((workspace) => (
                  <tr key={workspace.id} className="border-t border-[#eef2f6]">
                    <td className="px-4 py-3 text-[#18202b]">
                      <div className="font-semibold">{workspace.display_name}</div>
                      <div className="text-xs text-[#62728d]">{workspace.id}</div>
                    </td>
                    <td className="px-4 py-3 text-[#62728d]">{formatRelative(workspace.created_at)}</td>
                    <td className="px-4 py-3 text-right tabular-nums">{workspace.source_count}</td>
                    <td className="px-4 py-3 text-right tabular-nums">{formatBytes(workspace.storage_bytes)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      )}

      {tab === "activity" && (
        <div className="overflow-hidden rounded-2xl border border-[#d8e0eb] bg-white">
          {activityQuery.isLoading ? (
            <p className="p-6 text-sm text-[#62728d]">Loading activity…</p>
          ) : activityQuery.isError ? (
            <p className="p-6 text-sm text-[#b91c1c]">Could not load activity.</p>
          ) : !activityQuery.data || activityQuery.data.events.length === 0 ? (
            <p className="p-6 text-sm text-[#62728d]">No audit events yet.</p>
          ) : (
            <table className="w-full text-sm">
              <thead className="bg-[#f8fafc] text-left text-xs uppercase tracking-[0.1em] text-[#62728d]">
                <tr>
                  <th className="px-4 py-3">When</th>
                  <th className="px-4 py-3">Event</th>
                  <th className="px-4 py-3">Patient</th>
                  <th className="px-4 py-3">Session</th>
                </tr>
              </thead>
              <tbody>
                {activityQuery.data.events.map((event) => (
                  <tr key={event.id} className="border-t border-[#eef2f6]">
                    <td className="px-4 py-3 text-[#62728d]">{formatRelative(event.created_at)}</td>
                    <td className="px-4 py-3 font-mono text-xs text-[#18202b]">{event.event_type}</td>
                    <td className="px-4 py-3 text-xs text-[#62728d]">{event.patient_id ?? "—"}</td>
                    <td className="px-4 py-3 text-xs text-[#62728d]">
                      {event.session_id ? event.session_id.slice(0, 12) + "…" : "—"}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      )}

      {tab === "account" && (
        <div className="rounded-2xl border border-[#d8e0eb] bg-white p-4 text-sm">
          <dl className="grid grid-cols-[160px_1fr] gap-y-2">
            <dt className="text-[#62728d]">User ID</dt>
            <dd className="font-mono text-xs">{user.id}</dd>
            <dt className="text-[#62728d]">Email</dt>
            <dd>{user.email}</dd>
            <dt className="text-[#62728d]">Display name</dt>
            <dd>{user.display_name}</dd>
            <dt className="text-[#62728d]">Role</dt>
            <dd>{user.role}</dd>
            <dt className="text-[#62728d]">Status</dt>
            <dd>{user.status}</dd>
            <dt className="text-[#62728d]">Created</dt>
            <dd>{new Date(user.created_at).toLocaleString()}</dd>
            <dt className="text-[#62728d]">Last login</dt>
            <dd>{user.last_login_at ? new Date(user.last_login_at).toLocaleString() : "Never"}</dd>
            <dt className="text-[#62728d]">Workspaces</dt>
            <dd>{user.workspace_count}</dd>
            <dt className="text-[#62728d]">Storage</dt>
            <dd>{formatBytes(user.storage_bytes)}</dd>
          </dl>
        </div>
      )}
    </AdminLayout>
  );
}

function extractErrorMessage(error: unknown): string {
  if (!error) return "Something went wrong.";
  if (typeof error === "object" && error !== null) {
    const maybeAxios = error as {
      response?: { data?: { detail?: unknown } };
      message?: string;
    };
    const detail = maybeAxios.response?.data?.detail;
    if (typeof detail === "string" && detail) return detail;
    if (typeof maybeAxios.message === "string" && maybeAxios.message) return maybeAxios.message;
  }
  return "Request failed.";
}

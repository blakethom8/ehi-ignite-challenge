import { useState } from "react";
import { Link } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ChevronRight, Trash2, UserCog } from "lucide-react";
import { api } from "../../api/client";
import { useAccessContext } from "../../context/AccessContext";
import { AdminLayout, formatBytes, formatRelative } from "./AdminLayout";
import type { AdminUserSummary, AuthAccountStatus, AuthRole } from "../../types";

const ROLE_OPTIONS: AuthRole[] = ["consumer", "clinician", "attending", "coordinator", "admin"];

export function AdminUsersPage() {
  const queryClient = useQueryClient();
  const { user: currentUser } = useAccessContext();
  const [actionError, setActionError] = useState<string | null>(null);

  const usersQuery = useQuery({
    queryKey: ["admin", "users"],
    queryFn: () => api.adminListUsers(),
  });

  const patchUser = useMutation({
    mutationFn: ({ userId, role, status }: { userId: string; role?: AuthRole; status?: AuthAccountStatus }) =>
      api.adminPatchUser(userId, { role, status }),
    onSuccess: () => {
      setActionError(null);
      queryClient.invalidateQueries({ queryKey: ["admin", "users"] });
    },
    onError: (error: unknown) => {
      setActionError(extractErrorMessage(error));
    },
  });

  const deleteUser = useMutation({
    mutationFn: (userId: string) => api.adminDeleteUser(userId),
    onSuccess: () => {
      setActionError(null);
      queryClient.invalidateQueries({ queryKey: ["admin", "users"] });
    },
    onError: (error: unknown) => {
      setActionError(extractErrorMessage(error));
    },
  });

  return (
    <AdminLayout title="Users" subtitle="All Atlas accounts, their workspaces, and storage footprint.">
      {actionError && (
        <div className="mb-4 rounded-2xl border border-[#fecaca] bg-[#fef2f2] px-4 py-3 text-sm text-[#b91c1c]">
          {actionError}
        </div>
      )}

      {usersQuery.isLoading ? (
        <p className="text-sm text-[#62728d]">Loading users…</p>
      ) : usersQuery.isError ? (
        <p className="text-sm text-[#b91c1c]">Could not load users: {extractErrorMessage(usersQuery.error)}</p>
      ) : !usersQuery.data || usersQuery.data.length === 0 ? (
        <p className="text-sm text-[#62728d]">No accounts yet.</p>
      ) : (
        <div className="overflow-hidden rounded-2xl border border-[#d8e0eb] bg-white">
          <table className="w-full text-sm">
            <thead className="bg-[#f8fafc] text-left text-xs uppercase tracking-[0.1em] text-[#62728d]">
              <tr>
                <th className="px-4 py-3">User</th>
                <th className="px-4 py-3">Role</th>
                <th className="px-4 py-3">Status</th>
                <th className="px-4 py-3">Last login</th>
                <th className="px-4 py-3 text-right">Workspaces</th>
                <th className="px-4 py-3 text-right">Storage</th>
                <th className="px-4 py-3" />
              </tr>
            </thead>
            <tbody>
              {usersQuery.data.map((row) => (
                <UserRow
                  key={row.id}
                  user={row}
                  isSelf={row.id === currentUser?.id}
                  onRoleChange={(role) => patchUser.mutate({ userId: row.id, role })}
                  onToggleStatus={() =>
                    patchUser.mutate({
                      userId: row.id,
                      status: row.status === "active" ? "disabled" : "active",
                    })
                  }
                  onDelete={() => {
                    if (
                      window.confirm(
                        `Permanently delete ${row.email}? This cascades: their sessions are revoked, their uploaded workspaces are wiped. The audit trail is preserved.`,
                      )
                    ) {
                      deleteUser.mutate(row.id);
                    }
                  }}
                />
              ))}
            </tbody>
          </table>
        </div>
      )}
    </AdminLayout>
  );
}

function UserRow({
  user,
  isSelf,
  onRoleChange,
  onToggleStatus,
  onDelete,
}: {
  user: AdminUserSummary;
  isSelf: boolean;
  onRoleChange: (role: AuthRole) => void;
  onToggleStatus: () => void;
  onDelete: () => void;
}) {
  return (
    <tr className="border-t border-[#eef2f6] hover:bg-[#fafbfd]">
      <td className="px-4 py-3">
        <Link to={`/admin/users/${user.id}`} className="flex items-center gap-3 text-[#18202b] hover:text-[#3657ff]">
          <div className="grid h-9 w-9 place-items-center rounded-full bg-[#dbeafe] text-xs font-semibold text-[#1d4ed8]">
            {user.display_name.slice(0, 2).toUpperCase()}
          </div>
          <div>
            <div className="font-semibold">
              {user.display_name}
              {isSelf && (
                <span className="ml-2 rounded-full bg-[#ecfdf5] px-2 py-[1px] text-[10px] font-semibold uppercase tracking-[0.08em] text-[#047857]">
                  You
                </span>
              )}
            </div>
            <div className="text-xs text-[#62728d]">{user.email}</div>
          </div>
        </Link>
      </td>
      <td className="px-4 py-3">
        <select
          aria-label={`Role for ${user.email}`}
          value={user.role}
          onChange={(event) => onRoleChange(event.target.value as AuthRole)}
          className="rounded-lg border border-[#d5deea] bg-white px-2 py-1 text-xs"
        >
          {ROLE_OPTIONS.map((option) => (
            <option key={option} value={option}>
              {option}
            </option>
          ))}
        </select>
      </td>
      <td className="px-4 py-3">
        <button
          type="button"
          onClick={onToggleStatus}
          disabled={isSelf}
          title={isSelf ? "Cannot disable your own account from this view." : "Toggle status"}
          className={`inline-flex items-center gap-1 rounded-full px-2 py-[2px] text-[11px] font-semibold uppercase tracking-[0.08em] transition-colors ${
            user.status === "active"
              ? "bg-[#ecfdf5] text-[#047857] hover:bg-[#d1fae5]"
              : "bg-[#fef3c7] text-[#b45309] hover:bg-[#fde68a]"
          } ${isSelf ? "opacity-60" : ""}`}
        >
          {user.status}
        </button>
      </td>
      <td className="px-4 py-3 text-[#62728d]">{formatRelative(user.last_login_at)}</td>
      <td className="px-4 py-3 text-right tabular-nums">{user.workspace_count}</td>
      <td className="px-4 py-3 text-right tabular-nums">{formatBytes(user.storage_bytes)}</td>
      <td className="px-4 py-3 text-right">
        <div className="inline-flex items-center gap-2">
          <Link
            to={`/admin/users/${user.id}`}
            className="inline-flex items-center gap-1 rounded-lg border border-[#d5deea] bg-white px-2 py-1 text-xs text-[#33415b] hover:border-[#4d68ff] hover:text-[#3657ff]"
            aria-label={`Open ${user.email}`}
          >
            <UserCog size={12} />
            Open
            <ChevronRight size={12} />
          </Link>
          <button
            type="button"
            onClick={onDelete}
            disabled={isSelf}
            title={isSelf ? "Use Settings → Delete account to remove yourself." : "Delete user"}
            aria-label={`Delete ${user.email}`}
            className="inline-flex items-center gap-1 rounded-lg border border-[#fecaca] bg-[#fef2f2] px-2 py-1 text-xs text-[#b91c1c] hover:bg-[#fee2e2] disabled:opacity-50"
          >
            <Trash2 size={12} />
            Delete
          </button>
        </div>
      </td>
    </tr>
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

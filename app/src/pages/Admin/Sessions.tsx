import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { LogOut } from "lucide-react";
import { api } from "../../api/client";
import { AdminLayout, formatRelative } from "./AdminLayout";
import { useAccessContext } from "../../context/AccessContext";

export function AdminSessionsPage() {
  const queryClient = useQueryClient();
  const { user: currentUser } = useAccessContext();
  const [actionError, setActionError] = useState<string | null>(null);

  const sessionsQuery = useQuery({
    queryKey: ["admin", "sessions"],
    queryFn: () => api.adminListSessions(),
  });

  const revoke = useMutation({
    mutationFn: (sessionId: string) => api.adminRevokeSession(sessionId),
    onSuccess: () => {
      setActionError(null);
      queryClient.invalidateQueries({ queryKey: ["admin", "sessions"] });
    },
    onError: (error: unknown) => setActionError(extractErrorMessage(error)),
  });

  return (
    <AdminLayout title="Active sessions" subtitle="Every live session across users. Revoke to force a sign-out.">
      {actionError && (
        <div className="mb-4 rounded-2xl border border-[#fecaca] bg-[#fef2f2] px-4 py-3 text-sm text-[#b91c1c]">
          {actionError}
        </div>
      )}

      {sessionsQuery.isLoading ? (
        <p className="text-sm text-[#62728d]">Loading sessions…</p>
      ) : sessionsQuery.isError ? (
        <p className="text-sm text-[#b91c1c]">Could not load sessions: {extractErrorMessage(sessionsQuery.error)}</p>
      ) : !sessionsQuery.data || sessionsQuery.data.length === 0 ? (
        <p className="text-sm text-[#62728d]">No live sessions right now.</p>
      ) : (
        <div className="overflow-hidden rounded-2xl border border-[#d8e0eb] bg-white">
          <table className="w-full text-sm">
            <thead className="bg-[#f8fafc] text-left text-xs uppercase tracking-[0.1em] text-[#62728d]">
              <tr>
                <th className="px-4 py-3">Session</th>
                <th className="px-4 py-3">Mode</th>
                <th className="px-4 py-3">User</th>
                <th className="px-4 py-3">Active patient</th>
                <th className="px-4 py-3">Last seen</th>
                <th className="px-4 py-3">Expires</th>
                <th className="px-4 py-3" />
              </tr>
            </thead>
            <tbody>
              {sessionsQuery.data.map((session) => {
                const userAgent = session.user_agent ? truncate(session.user_agent, 40) : "—";
                return (
                  <tr key={session.id} className="border-t border-[#eef2f6]">
                    <td className="px-4 py-3 font-mono text-xs text-[#18202b]">
                      {session.id.slice(0, 14)}…
                      <div className="mt-1 text-[10px] text-[#62728d]">UA: {userAgent}</div>
                    </td>
                    <td className="px-4 py-3">
                      <span className={`rounded-full px-2 py-[2px] text-[11px] font-semibold uppercase tracking-[0.08em] ${
                        session.mode === "demo"
                          ? "bg-[#fef3c7] text-[#b45309]"
                          : "bg-[#dbeafe] text-[#1d4ed8]"
                      }`}>
                        {session.mode}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-[#18202b]">
                      {session.user_display_name ? (
                        <>
                          <div className="font-semibold">{session.user_display_name}</div>
                          <div className="text-xs text-[#62728d]">{session.user_email}</div>
                        </>
                      ) : (
                        <span className="text-[#62728d]">Demo (no user)</span>
                      )}
                    </td>
                    <td className="px-4 py-3 text-xs text-[#62728d]">{session.active_patient_name ?? session.active_patient_id ?? "—"}</td>
                    <td className="px-4 py-3 text-[#62728d]">{formatRelative(session.last_seen_at)}</td>
                    <td className="px-4 py-3 text-[#62728d]">{formatRelative(session.expires_at)}</td>
                    <td className="px-4 py-3 text-right">
                      <button
                        type="button"
                        onClick={() => {
                          if (window.confirm("Revoke this session? The user will be signed out on their next request.")) {
                            revoke.mutate(session.id);
                          }
                        }}
                        disabled={session.user_id === currentUser?.id}
                        title={session.user_id === currentUser?.id ? "This is your current session." : "Revoke session"}
                        className="inline-flex items-center gap-1 rounded-lg border border-[#fecaca] bg-[#fef2f2] px-2 py-1 text-xs text-[#b91c1c] hover:bg-[#fee2e2] disabled:opacity-50"
                      >
                        <LogOut size={12} />
                        Revoke
                      </button>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </AdminLayout>
  );
}

function truncate(value: string, length: number): string {
  return value.length <= length ? value : `${value.slice(0, length)}…`;
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

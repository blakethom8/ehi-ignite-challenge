import { useCallback, useEffect, useState, type FormEvent, type ReactNode } from "react";
import { Link, Navigate, useNavigate } from "react-router-dom";
import { ArrowLeft, Laptop, LogOut, Shield, Trash2, UserRound } from "lucide-react";
import { api } from "../api/client";
import { useAccessContext } from "../context/AccessContext";
import { useCanManageOwnAccount } from "../hooks/useCapabilities";
import { useSessionActions } from "../hooks/useSessionActions";
import { resolveSessionHomePath } from "../sessionRouting";
import type { AccountSessionSummary, PatientListItem } from "../types";

type AccountTab = "overview" | "security" | "sessions";
type MessageTone = "info" | "error";

export function AccountSettingsPage() {
  const navigate = useNavigate();
  const canManageOwnAccount = useCanManageOwnAccount();
  const {
    activePatientId,
    isLoading,
    mode,
    user,
    updateDisplayName,
    changePassword,
    deleteAccount,
  } = useAccessContext();
  const {
    isSessionActionPending,
    leaveSessionToHome,
    sessionActionError,
    sessionActionPendingLabel,
  } = useSessionActions();
  const [activeTab, setActiveTab] = useState<AccountTab>("overview");
  const [displayName, setDisplayName] = useState("");
  const [currentPassword, setCurrentPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [profileMsg, setProfileMsg] = useState<{ tone: MessageTone; text: string } | null>(null);
  const [passwordMsg, setPasswordMsg] = useState<{ tone: MessageTone; text: string } | null>(null);
  const [sessionMsg, setSessionMsg] = useState<{ tone: MessageTone; text: string } | null>(null);
  const [deleteError, setDeleteError] = useState<string | null>(null);
  const [workspaces, setWorkspaces] = useState<PatientListItem[]>([]);
  const [isLoadingWorkspaces, setIsLoadingWorkspaces] = useState(false);
  const [workspaceError, setWorkspaceError] = useState<string | null>(null);
  const [sessions, setSessions] = useState<AccountSessionSummary[]>([]);
  const [isLoadingSessions, setIsLoadingSessions] = useState(false);
  const [sessionError, setSessionError] = useState<string | null>(null);
  const [pendingSessionId, setPendingSessionId] = useState<string | null>(null);
  const [isRevokingOthers, setIsRevokingOthers] = useState(false);
  const backToAtlasHref = resolveSessionHomePath(mode, activePatientId);

  useEffect(() => {
    if (user) {
      setDisplayName(user.display_name);
    }
  }, [user]);

  const refreshSessions = useCallback(async () => {
    setIsLoadingSessions(true);
    setSessionError(null);
    try {
      setSessions(await api.listOwnSessions());
    } catch (error) {
      setSessionError(extractErrorMessage(error));
    } finally {
      setIsLoadingSessions(false);
    }
  }, []);

  useEffect(() => {
    if (!user) return;
    let cancelled = false;
    setIsLoadingWorkspaces(true);
    setWorkspaceError(null);
    api.listPatients()
      .then((items) => {
        if (!cancelled) {
          setWorkspaces(items);
        }
      })
      .catch((error) => {
        if (!cancelled) {
          setWorkspaceError(extractErrorMessage(error));
        }
      })
      .finally(() => {
        if (!cancelled) {
          setIsLoadingWorkspaces(false);
        }
      });
    return () => {
      cancelled = true;
    };
  }, [user]);

  useEffect(() => {
    if (!user) return;
    void refreshSessions();
  }, [refreshSessions, user]);

  if (isLoading) {
    return (
      <div className="grid min-h-screen place-items-center bg-[#eef2f6]">
        <div className="h-10 w-10 animate-spin rounded-full border-4 border-[#cad6ff] border-t-[#4d68ff]" />
      </div>
    );
  }

  if (!canManageOwnAccount || !user) {
    return <Navigate to="/account" replace />;
  }

  const currentSession = sessions.find((session) => session.is_current) ?? null;
  const otherSessions = sessions.filter((session) => !session.is_current);

  const handleProfile = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setProfileMsg(null);
    try {
      await updateDisplayName(displayName);
      setProfileMsg({ tone: "info", text: "Display name updated." });
    } catch (error) {
      setProfileMsg({ tone: "error", text: extractErrorMessage(error) });
    }
  };

  const handlePassword = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setPasswordMsg(null);
    if (newPassword !== confirmPassword) {
      setPasswordMsg({ tone: "error", text: "New password and confirmation do not match." });
      return;
    }
    if (newPassword.length < 8) {
      setPasswordMsg({ tone: "error", text: "New password must be at least 8 characters." });
      return;
    }
    try {
      await changePassword(currentPassword, newPassword);
      setCurrentPassword("");
      setNewPassword("");
      setConfirmPassword("");
      setPasswordMsg({ tone: "info", text: "Password changed. Other sessions have been signed out." });
      await refreshSessions();
    } catch (error) {
      setPasswordMsg({ tone: "error", text: extractErrorMessage(error) });
    }
  };

  const handleRevokeOtherSessions = async () => {
    setSessionMsg(null);
    setIsRevokingOthers(true);
    try {
      await api.revokeOtherSessions();
      setSessionMsg({ tone: "info", text: "Other sessions were signed out." });
      await refreshSessions();
    } catch (error) {
      setSessionMsg({ tone: "error", text: extractErrorMessage(error) });
    } finally {
      setIsRevokingOthers(false);
    }
  };

  const handleRevokeSession = async (sessionId: string) => {
    setSessionMsg(null);
    setPendingSessionId(sessionId);
    try {
      await api.revokeOwnSession(sessionId);
      setSessionMsg({ tone: "info", text: "Session signed out." });
      await refreshSessions();
    } catch (error) {
      setSessionMsg({ tone: "error", text: extractErrorMessage(error) });
    } finally {
      setPendingSessionId(null);
    }
  };

  const handleDelete = async () => {
    if (
      !window.confirm(
        "Delete your Atlas account permanently? Your uploaded workspaces will be wiped and you will be signed out. This cannot be undone.",
      )
    ) {
      return;
    }
    setDeleteError(null);
    try {
      await deleteAccount();
      navigate("/", { replace: true });
    } catch (error) {
      setDeleteError(extractErrorMessage(error));
    }
  };

  return (
    <div className="min-h-screen bg-[#eef2f6] px-6 py-8 text-[#18202b]">
      <div className="mx-auto max-w-4xl">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <Link
            to={backToAtlasHref}
            className="inline-flex items-center gap-2 text-sm font-semibold text-[#52627f] transition-colors hover:text-[#3657ff]"
          >
            <ArrowLeft size={16} />
            Back to Atlas
          </Link>
          <button
            type="button"
            onClick={() => {
              void leaveSessionToHome();
            }}
            disabled={isSessionActionPending}
            className="inline-flex items-center gap-2 rounded-2xl border border-[#d5deea] bg-white px-4 py-2 text-sm font-semibold text-[#33415b] transition-colors hover:border-[#4d68ff] hover:text-[#3657ff] disabled:cursor-not-allowed disabled:opacity-70"
          >
            <LogOut size={15} />
            {isSessionActionPending ? sessionActionPendingLabel : "Sign out"}
          </button>
        </div>
        {sessionActionError && <Message tone="error" text={sessionActionError} />}

        <header className="mt-6 rounded-[28px] border border-[#d8e0eb] bg-white px-6 py-5 shadow-sm">
          <div className="flex flex-wrap items-start justify-between gap-4">
            <div>
              <h1 className="text-3xl font-semibold tracking-[-0.03em] text-[#171b24]">Account settings</h1>
              <p className="mt-1 text-sm text-[#62728d]">
                Review your profile, control active sessions, and manage your account security without leaving the workspace.
              </p>
            </div>
            <div className="rounded-2xl border border-[#dbe4f0] bg-[#f8fbff] px-4 py-3 text-right">
              <p className="text-xs font-semibold uppercase tracking-[0.12em] text-[#7a88a3]">Signed in as</p>
              <p className="mt-1 text-sm font-semibold text-[#18202b]">{user.email}</p>
              <p className="mt-1 text-xs text-[#62728d]">Role: {user.role}</p>
            </div>
          </div>

          <div className="mt-5 grid grid-cols-3 gap-2 rounded-2xl bg-[#eef2f7] p-1">
            {([
              ["overview", "Overview"],
              ["security", "Security"],
              ["sessions", "Sessions"],
            ] as const).map(([tab, label]) => (
              <button
                key={tab}
                type="button"
                onClick={() => setActiveTab(tab)}
                className={`rounded-xl px-4 py-2.5 text-sm font-semibold transition-colors ${
                  activeTab === tab
                    ? "bg-white text-[#18202b] shadow-sm"
                    : "text-[#62728d] hover:text-[#33415b]"
                }`}
              >
                {label}
              </button>
            ))}
          </div>
        </header>

        {activeTab === "overview" ? (
          <div className="mt-6 grid gap-4 lg:grid-cols-[1.05fr_0.95fr]">
            <section className="rounded-2xl border border-[#d8e0eb] bg-white p-5 shadow-sm">
              <SectionTitle
                icon={<UserRound className="h-4 w-4 text-[#3657ff]" />}
                title="Profile"
                body="Keep the clinician-facing name current. Email and role remain read-only."
              />
              <form onSubmit={handleProfile} className="mt-4 max-w-md">
                <label className="block text-xs font-semibold uppercase tracking-[0.12em] text-[#7a88a3]">
                  Display name
                </label>
                <input
                  aria-label="Display name"
                  value={displayName}
                  onChange={(event) => setDisplayName(event.target.value)}
                  className="mt-2 w-full rounded-2xl border border-[#d5deea] bg-white px-4 py-3 text-sm text-[#18202b] outline-none transition-colors focus:border-[#4d68ff]"
                />
                <div className="mt-4 grid gap-3 sm:grid-cols-2">
                  <ReadOnlyField label="Email" value={user.email} />
                  <ReadOnlyField label="Role" value={user.role} />
                </div>
                {profileMsg && <Message tone={profileMsg.tone} text={profileMsg.text} />}
                <button
                  type="submit"
                  disabled={!displayName.trim() || displayName.trim() === user.display_name}
                  className="mt-4 rounded-2xl bg-[#4d68ff] px-5 py-2 text-sm font-semibold text-white transition-colors hover:bg-[#3c57ef] disabled:cursor-not-allowed disabled:opacity-70"
                >
                  Save name
                </button>
              </form>
            </section>

            <section className="rounded-2xl border border-[#d8e0eb] bg-white p-5 shadow-sm">
              <SectionTitle
                icon={<Laptop className="h-4 w-4 text-[#3657ff]" />}
                title="Workspace posture"
                body="See what this account already owns before jumping back into the app."
              />
              <div className="mt-4 grid gap-3 sm:grid-cols-2">
                <MetricCard
                  label="Private workspaces"
                  value={isLoadingWorkspaces ? "…" : String(workspaces.length)}
                  detail={workspaces.length ? "Saved Atlas workspaces linked to this account." : "No private workspaces yet."}
                />
                <MetricCard
                  label="Active sessions"
                  value={isLoadingSessions ? "…" : String(sessions.length)}
                  detail={sessions.length > 1 ? "This account is open in multiple browsers/devices." : "Only this browser session is active."}
                />
              </div>
              {workspaceError && <Message tone="error" text={workspaceError} />}
              <div className="mt-4 rounded-2xl border border-[#e3eaf4] bg-[#f8fbff] p-4">
                <p className="text-xs font-semibold uppercase tracking-[0.12em] text-[#7a88a3]">Recent workspaces</p>
                {isLoadingWorkspaces ? (
                  <p className="mt-3 text-sm text-[#62728d]">Loading workspaces…</p>
                ) : workspaces.length ? (
                  <div className="mt-3 space-y-3">
                    {workspaces.slice(0, 3).map((workspace) => (
                      <div key={workspace.id} className="rounded-2xl border border-white bg-white px-4 py-3">
                        <p className="text-sm font-semibold text-[#18202b]">{workspace.name}</p>
                        <p className="mt-1 text-xs text-[#62728d]">
                          {workspace.source_count ?? 0} sources · {workspace.prepared_source_count ?? 0} prepared
                        </p>
                      </div>
                    ))}
                  </div>
                ) : (
                  <p className="mt-3 text-sm leading-6 text-[#62728d]">
                    Create your first private workspace from Source Intake after you upload a chart.
                  </p>
                )}
                <Link
                  to="/patient-record/sources"
                  className="mt-4 inline-flex items-center gap-2 text-sm font-semibold text-[#3657ff] transition-colors hover:text-[#2444df]"
                >
                  Open Source Intake
                </Link>
              </div>
            </section>
          </div>
        ) : null}

        {activeTab === "security" ? (
          <div className="mt-6 grid gap-4 lg:grid-cols-[1.05fr_0.95fr]">
            <section className="rounded-2xl border border-[#d8e0eb] bg-white p-5 shadow-sm">
              <SectionTitle
                icon={<Shield className="h-4 w-4 text-[#3657ff]" />}
                title="Password"
                body="Change your password when you need to rotate credentials. Atlas will keep this browser signed in and revoke the rest."
              />
              <form onSubmit={handlePassword} className="mt-4 max-w-md space-y-3">
                <Field
                  label="Current password"
                  type="password"
                  value={currentPassword}
                  onChange={setCurrentPassword}
                  autoComplete="current-password"
                />
                <Field
                  label="New password"
                  type="password"
                  value={newPassword}
                  onChange={setNewPassword}
                  autoComplete="new-password"
                  placeholder="At least 8 characters"
                />
                <Field
                  label="Confirm new password"
                  type="password"
                  value={confirmPassword}
                  onChange={setConfirmPassword}
                  autoComplete="new-password"
                />
                {passwordMsg && <Message tone={passwordMsg.tone} text={passwordMsg.text} />}
                <button
                  type="submit"
                  disabled={!currentPassword || newPassword.length < 8 || newPassword !== confirmPassword}
                  className="rounded-2xl bg-[#4d68ff] px-5 py-2 text-sm font-semibold text-white transition-colors hover:bg-[#3c57ef] disabled:cursor-not-allowed disabled:opacity-70"
                >
                  Save new password
                </button>
              </form>
            </section>

            <section className="rounded-2xl border border-[#d8e0eb] bg-white p-5 shadow-sm">
              <SectionTitle
                icon={<Laptop className="h-4 w-4 text-[#3657ff]" />}
                title="Session controls"
                body="Use explicit session revocation when you do not want to rotate your password."
              />
              {sessionMsg && <Message tone={sessionMsg.tone} text={sessionMsg.text} />}
              {sessionError && <Message tone="error" text={sessionError} />}
              <div className="mt-4 rounded-2xl border border-[#e3eaf4] bg-[#f8fbff] p-4">
                <p className="text-sm font-semibold text-[#18202b]">
                  {otherSessions.length
                    ? `${otherSessions.length} other session${otherSessions.length === 1 ? "" : "s"} currently active`
                    : "No other active sessions"}
                </p>
                <p className="mt-2 text-sm leading-6 text-[#62728d]">
                  Sign out other browsers and devices without interrupting this workspace.
                </p>
                <button
                  type="button"
                  onClick={() => {
                    void handleRevokeOtherSessions();
                  }}
                  disabled={isRevokingOthers || otherSessions.length === 0}
                  className="mt-4 rounded-2xl border border-[#d5deea] bg-white px-4 py-2 text-sm font-semibold text-[#33415b] transition-colors hover:border-[#4d68ff] hover:text-[#3657ff] disabled:cursor-not-allowed disabled:opacity-70"
                >
                  {isRevokingOthers ? "Signing out other sessions..." : "Sign out other sessions"}
                </button>
              </div>
            </section>
          </div>
        ) : null}

        {activeTab === "sessions" ? (
          <div className="mt-6 grid gap-4">
            <section className="rounded-2xl border border-[#d8e0eb] bg-white p-5 shadow-sm">
              <div className="flex flex-wrap items-start justify-between gap-3">
                <SectionTitle
                  icon={<Laptop className="h-4 w-4 text-[#3657ff]" />}
                  title="Active sessions"
                  body="Review where this account is still signed in and revoke anything you do not recognize."
                />
                <button
                  type="button"
                  onClick={() => {
                    void handleRevokeOtherSessions();
                  }}
                  disabled={isRevokingOthers || otherSessions.length === 0}
                  className="rounded-2xl border border-[#d5deea] bg-white px-4 py-2 text-sm font-semibold text-[#33415b] transition-colors hover:border-[#4d68ff] hover:text-[#3657ff] disabled:cursor-not-allowed disabled:opacity-70"
                >
                  {isRevokingOthers ? "Signing out other sessions..." : "Sign out all others"}
                </button>
              </div>
              {sessionMsg && <Message tone={sessionMsg.tone} text={sessionMsg.text} />}
              {sessionError && <Message tone="error" text={sessionError} />}
              {isLoadingSessions ? (
                <p className="mt-4 text-sm text-[#62728d]">Loading sessions…</p>
              ) : (
                <div className="mt-4 space-y-3">
                  {currentSession ? (
                    <SessionCard
                      session={currentSession}
                      tone="current"
                      actionLabel="Current session"
                    />
                  ) : null}
                  {otherSessions.map((session) => (
                    <SessionCard
                      key={session.id}
                      session={session}
                      tone="default"
                      actionLabel={pendingSessionId === session.id ? "Signing out..." : "Sign out session"}
                      onAction={() => {
                        void handleRevokeSession(session.id);
                      }}
                      actionDisabled={pendingSessionId === session.id}
                    />
                  ))}
                  {!sessions.length ? (
                    <p className="rounded-2xl border border-[#e3eaf4] bg-[#f8fbff] px-4 py-4 text-sm text-[#62728d]">
                      No active sessions were returned for this account.
                    </p>
                  ) : null}
                </div>
              )}
            </section>
          </div>
        ) : null}

        <section className="mt-4 rounded-2xl border border-[#fecaca] bg-[#fef9f9] p-5 shadow-sm">
          <h2 className="text-lg font-semibold text-[#b91c1c]">Delete account</h2>
          <p className="mt-1 text-sm text-[#7c2d12]">
            Permanently removes your account, every workspace you own, and every uploaded file. Audit history is retained for compliance.
          </p>
          {deleteError && <Message tone="error" text={deleteError} />}
          <button
            type="button"
            onClick={handleDelete}
            className="mt-4 inline-flex items-center gap-2 rounded-2xl border border-[#fecaca] bg-white px-4 py-2 text-sm font-semibold text-[#b91c1c] transition-colors hover:bg-[#fee2e2]"
          >
            <Trash2 size={14} />
            Delete my account
          </button>
        </section>
      </div>
    </div>
  );
}

function SectionTitle({
  icon,
  title,
  body,
}: {
  icon: ReactNode;
  title: string;
  body: string;
}) {
  return (
    <div>
      <div className="flex items-center gap-2">
        {icon}
        <h2 className="text-lg font-semibold text-[#18202b]">{title}</h2>
      </div>
      <p className="mt-1 text-sm leading-6 text-[#62728d]">{body}</p>
    </div>
  );
}

function ReadOnlyField({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <p className="text-xs font-semibold uppercase tracking-[0.12em] text-[#7a88a3]">{label}</p>
      <p className="mt-2 rounded-2xl border border-[#d5deea] bg-[#f8fbff] px-4 py-3 text-sm text-[#33415b]">
        {value}
      </p>
    </div>
  );
}

function MetricCard({
  label,
  value,
  detail,
}: {
  label: string;
  value: string;
  detail: string;
}) {
  return (
    <div className="rounded-2xl border border-[#e3eaf4] bg-[#f8fbff] p-4">
      <p className="text-xs font-semibold uppercase tracking-[0.12em] text-[#7a88a3]">{label}</p>
      <p className="mt-2 text-3xl font-semibold tracking-[-0.03em] text-[#18202b]">{value}</p>
      <p className="mt-2 text-sm leading-6 text-[#62728d]">{detail}</p>
    </div>
  );
}

function SessionCard({
  session,
  tone,
  actionLabel,
  onAction,
  actionDisabled = true,
}: {
  session: AccountSessionSummary;
  tone: "current" | "default";
  actionLabel: string;
  onAction?: () => void;
  actionDisabled?: boolean;
}) {
  return (
    <div
      className={`rounded-2xl border px-4 py-4 ${
        tone === "current"
          ? "border-[#cdd8ff] bg-[#eef2ff]"
          : "border-[#e3eaf4] bg-[#f8fbff]"
      }`}
    >
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <p className="text-sm font-semibold text-[#18202b]">
            {session.is_current ? "Current browser" : session.user_agent || "Browser session"}
          </p>
          <p className="mt-1 text-xs text-[#62728d]">
            Last active {formatDateTime(session.last_seen_at)} · Expires {formatDateTime(session.expires_at)}
          </p>
          <p className="mt-1 text-xs text-[#62728d]">
            Started {formatDateTime(session.created_at)}
            {session.active_patient_name ? ` · Active workspace: ${session.active_patient_name}` : ""}
          </p>
        </div>
        {session.is_current ? (
          <span className="rounded-full border border-[#c7d4ff] bg-white px-3 py-1 text-xs font-semibold text-[#3657ff]">
            Current
          </span>
        ) : (
          <button
            type="button"
            onClick={onAction}
            disabled={actionDisabled}
            className="rounded-2xl border border-[#d5deea] bg-white px-4 py-2 text-sm font-semibold text-[#33415b] transition-colors hover:border-[#4d68ff] hover:text-[#3657ff] disabled:cursor-not-allowed disabled:opacity-70"
          >
            {actionLabel}
          </button>
        )}
      </div>
    </div>
  );
}

function Field({
  label,
  type = "text",
  value,
  onChange,
  autoComplete,
  placeholder,
}: {
  label: string;
  type?: string;
  value: string;
  onChange: (next: string) => void;
  autoComplete?: string;
  placeholder?: string;
}) {
  return (
    <div>
      <label className="block text-xs font-semibold uppercase tracking-[0.12em] text-[#7a88a3]">{label}</label>
      <input
        aria-label={label}
        type={type}
        value={value}
        onChange={(event) => onChange(event.target.value)}
        autoComplete={autoComplete}
        placeholder={placeholder}
        className="mt-2 w-full rounded-2xl border border-[#d5deea] bg-white px-4 py-3 text-sm text-[#18202b] outline-none transition-colors focus:border-[#4d68ff]"
      />
    </div>
  );
}

function Message({ tone, text }: { tone: MessageTone; text: string }) {
  return (
    <p
      role={tone === "error" ? "alert" : "status"}
      className={`mt-3 text-sm ${tone === "error" ? "text-[#b91c1c]" : "text-[#047857]"}`}
    >
      {text}
    </p>
  );
}

function formatDateTime(value: string): string {
  try {
    return new Intl.DateTimeFormat(undefined, {
      month: "short",
      day: "numeric",
      hour: "numeric",
      minute: "2-digit",
    }).format(new Date(value));
  } catch {
    return value;
  }
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

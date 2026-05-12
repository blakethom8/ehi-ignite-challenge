import { useEffect, useState, type FormEvent } from "react";
import { Link, Navigate, useNavigate } from "react-router-dom";
import { ArrowLeft, Trash2 } from "lucide-react";
import { useAccessContext } from "../context/AccessContext";

export function AccountSettingsPage() {
  const navigate = useNavigate();
  const { isLoading, isUnlocked, user, updateDisplayName, changePassword, deleteAccount } = useAccessContext();
  const [displayName, setDisplayName] = useState("");
  const [currentPassword, setCurrentPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [profileMsg, setProfileMsg] = useState<{ tone: "info" | "error"; text: string } | null>(null);
  const [passwordMsg, setPasswordMsg] = useState<{ tone: "info" | "error"; text: string } | null>(null);
  const [deleteError, setDeleteError] = useState<string | null>(null);

  useEffect(() => {
    if (user) {
      setDisplayName(user.display_name);
    }
  }, [user?.id, user?.display_name]);

  if (isLoading) {
    return (
      <div className="grid min-h-screen place-items-center bg-[#eef2f6]">
        <div className="h-10 w-10 animate-spin rounded-full border-4 border-[#cad6ff] border-t-[#4d68ff]" />
      </div>
    );
  }

  if (!isUnlocked || !user) {
    return <Navigate to="/account" replace />;
  }

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
    } catch (error) {
      setPasswordMsg({ tone: "error", text: extractErrorMessage(error) });
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
      <div className="mx-auto max-w-3xl">
        <Link
          to="/"
          className="inline-flex items-center gap-2 text-sm font-semibold text-[#52627f] transition-colors hover:text-[#3657ff]"
        >
          <ArrowLeft size={16} />
          Back to Atlas
        </Link>

        <header className="mt-6">
          <h1 className="text-3xl font-semibold tracking-[-0.03em] text-[#171b24]">Account settings</h1>
          <p className="mt-1 text-sm text-[#62728d]">
            Update your name, change your password, or close your account. Account email and role can only be changed by an admin.
          </p>
        </header>

        <section className="mt-6 rounded-2xl border border-[#d8e0eb] bg-white p-5 shadow-sm">
          <h2 className="text-lg font-semibold text-[#18202b]">Profile</h2>
          <p className="mt-1 text-xs text-[#62728d]">Signed in as <strong>{user.email}</strong> · role: {user.role}</p>
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

        <section className="mt-4 rounded-2xl border border-[#d8e0eb] bg-white p-5 shadow-sm">
          <h2 className="text-lg font-semibold text-[#18202b]">Change password</h2>
          <p className="mt-1 text-xs text-[#62728d]">Other devices will be signed out when you save a new password.</p>
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

        <section className="mt-4 rounded-2xl border border-[#fecaca] bg-[#fef9f9] p-5 shadow-sm">
          <h2 className="text-lg font-semibold text-[#b91c1c]">Delete account</h2>
          <p className="mt-1 text-sm text-[#7c2d12]">
            Permanently removes your account, every workspace you own, and every uploaded file. Audit history (login times, patient access timestamps) is retained for compliance.
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

function Message({ tone, text }: { tone: "info" | "error"; text: string }) {
  return (
    <p
      role={tone === "error" ? "alert" : "status"}
      className={`mt-3 text-sm ${tone === "error" ? "text-[#b91c1c]" : "text-[#047857]"}`}
    >
      {text}
    </p>
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

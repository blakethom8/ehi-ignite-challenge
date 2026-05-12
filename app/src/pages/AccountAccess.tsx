import axios from "axios";
import { useState, type FormEvent } from "react";
import { Link, useNavigate } from "react-router-dom";
import { ArrowLeft, ArrowRight, CheckCircle2, LockKeyhole, UserPlus } from "lucide-react";
import { useAccessContext } from "../context/AccessContext";

type AccountTab = "login" | "signup";

function signInErrorMessage(error: unknown): string {
  if (axios.isAxiosError(error)) {
    if (error.response?.status === 401) {
      return "The email or password did not match an account.";
    }
    if (error.response?.status === 403) {
      return "This account cannot access the requested workspace.";
    }
    if (!error.response) {
      return "Atlas could not reach the account service. Try again when the API is available.";
    }
  }
  if (error instanceof Error && error.message.trim()) {
    return error.message;
  }
  return "Log in failed. Check the account credentials and try again.";
}

function signUpErrorMessage(error: unknown): string {
  if (axios.isAxiosError(error)) {
    if (error.response?.status === 409) {
      return "An account with this email already exists. Try logging in instead.";
    }
    if (error.response?.status === 422) {
      const detail = (error.response.data as { detail?: unknown } | undefined)?.detail;
      if (typeof detail === "string" && detail.trim()) return detail;
      return "Check that the email is valid, the password is at least 8 characters, and a display name is set.";
    }
    if (!error.response) {
      return "Atlas could not reach the account service. Try again when the API is available.";
    }
  }
  if (error instanceof Error && error.message.trim()) {
    return error.message;
  }
  return "Account creation failed. Try again.";
}

export function AccountAccessPage() {
  const navigate = useNavigate();
  const { activePatientId, isLoading, isUnlocked, signIn, signUp, user } = useAccessContext();
  const [activeTab, setActiveTab] = useState<AccountTab>("login");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [signInError, setSignInError] = useState<string | null>(null);
  const [signUpEmail, setSignUpEmail] = useState("");
  const [signUpPassword, setSignUpPassword] = useState("");
  const [signUpDisplayName, setSignUpDisplayName] = useState("");
  const [signUpError, setSignUpError] = useState<string | null>(null);

  const handleSignIn = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setSignInError(null);
    try {
      await signIn(email, password);
      navigate(activePatientId ? `/patient-record?patient=${encodeURIComponent(activePatientId)}` : "/records-pool");
    } catch (error) {
      setSignInError(signInErrorMessage(error));
    }
  };

  const handleSignUp = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setSignUpError(null);
    try {
      await signUp(signUpEmail, signUpPassword, signUpDisplayName);
      navigate("/records-pool");
    } catch (error) {
      setSignUpError(signUpErrorMessage(error));
    }
  };

  return (
    <div className="min-h-screen bg-[radial-gradient(circle_at_top,#f6f9ff_0%,#eef3f8_42%,#e9eef4_100%)] px-6 py-8 text-[#18202b]">
      <div className="mx-auto max-w-5xl">
        <header className="flex items-center justify-between gap-4">
          <Link
            to="/"
            className="inline-flex items-center gap-2 text-sm font-semibold text-[#52627f] transition-colors hover:text-[#3657ff]"
          >
            <ArrowLeft size={16} />
            Back to demo
          </Link>
          <Link
            to="/using-atlas"
            className="hidden text-sm font-semibold text-[#52627f] transition-colors hover:text-[#3657ff] sm:inline-flex"
          >
            About Atlas
          </Link>
        </header>

        <main className="mt-10 grid gap-6 lg:grid-cols-[0.95fr_1.05fr] lg:items-start">
          <section className="rounded-[30px] border border-[#cad6ff] bg-[rgba(255,255,255,0.78)] p-7 shadow-[0_22px_70px_rgba(77,104,255,0.08)]">
            <p className="text-[11px] font-semibold uppercase tracking-[0.22em] text-[#4d68ff]">
              Atlas account
            </p>
            <h1 className="mt-4 text-4xl font-semibold tracking-[-0.05em] text-[#171b24] sm:text-5xl">
              Log in to a saved health-record workspace.
            </h1>
            <p className="mt-4 text-sm leading-7 text-[#5f6f89]">
              Use your account to save private record workspaces, upload health-record files, and return later.
            </p>

            <div className="mt-6 grid gap-3">
              {[
                "Upload PDFs, portal exports, and other health-record files.",
                "Keep sample charts separate from private account workspaces.",
                "Start with the public demo when you do not have an account yet.",
              ].map((item) => (
                <div key={item} className="flex items-start gap-3 text-sm leading-6 text-[#3e4d68]">
                  <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0 text-[#00a36c]" />
                  <span>{item}</span>
                </div>
              ))}
            </div>
          </section>

          <section className="rounded-[30px] border border-[#d8e0eb] bg-white/82 p-5 shadow-[0_22px_70px_rgba(32,52,89,0.08)]">
            <div className="grid grid-cols-2 gap-2 rounded-2xl bg-[#eef2f7] p-1">
              <button
                type="button"
                onClick={() => setActiveTab("login")}
                className={`inline-flex items-center justify-center gap-2 rounded-xl px-4 py-2.5 text-sm font-semibold transition-colors ${
                  activeTab === "login"
                    ? "bg-white text-[#18202b] shadow-sm"
                    : "text-[#62728d] hover:text-[#33415b]"
                }`}
              >
                <LockKeyhole size={15} />
                Log in
              </button>
              <button
                type="button"
                onClick={() => setActiveTab("signup")}
                className={`inline-flex items-center justify-center gap-2 rounded-xl px-4 py-2.5 text-sm font-semibold transition-colors ${
                  activeTab === "signup"
                    ? "bg-white text-[#18202b] shadow-sm"
                    : "text-[#62728d] hover:text-[#33415b]"
                }`}
              >
                <UserPlus size={15} />
                Create account
              </button>
            </div>

            {activeTab === "login" ? (
              <form onSubmit={handleSignIn} className="mt-6">
                <h2 className="text-xl font-semibold text-[#18202b]">Account login</h2>
                <p className="mt-2 text-sm leading-6 text-[#62728d]">
                  Log in with an existing Atlas account, or switch to the Create account tab to make one.
                </p>
                <label className="mt-5 block text-xs font-semibold uppercase tracking-[0.12em] text-[#7a88a3]">
                  Email
                </label>
                <input
                  aria-label="Email"
                  value={email}
                  onChange={(event) => setEmail(event.target.value)}
                  className="mt-2 w-full rounded-2xl border border-[#d5deea] bg-white px-4 py-3 text-sm text-[#18202b] outline-none transition-colors focus:border-[#4d68ff]"
                  autoComplete="username"
                  type="email"
                />
                <label className="mt-4 block text-xs font-semibold uppercase tracking-[0.12em] text-[#7a88a3]">
                  Password
                </label>
                <input
                  aria-label="Password"
                  type="password"
                  value={password}
                  onChange={(event) => setPassword(event.target.value)}
                  className="mt-2 w-full rounded-2xl border border-[#d5deea] bg-white px-4 py-3 text-sm text-[#18202b] outline-none transition-colors focus:border-[#4d68ff]"
                  autoComplete="current-password"
                />
                {signInError && (
                  <p className="mt-3 text-sm text-[#b42318]">{signInError}</p>
                )}
                {isUnlocked && user && (
                  <p className="mt-3 rounded-2xl bg-[#ecfdf5] px-4 py-3 text-sm text-[#047857]">
                    Signed in as {user.display_name}.
                  </p>
                )}
                <button
                  type="submit"
                  disabled={isLoading || !email.trim() || !password}
                  className="mt-5 inline-flex items-center gap-2 rounded-2xl bg-[#4d68ff] px-5 py-3 text-sm font-semibold text-white transition-colors hover:bg-[#3c57ef] disabled:cursor-not-allowed disabled:opacity-70"
                >
                  {isLoading ? "Checking account..." : "Log in"}
                  <ArrowRight size={16} />
                </button>
              </form>
            ) : (
              <form onSubmit={handleSignUp} className="mt-6">
                <h2 className="text-xl font-semibold text-[#18202b]">Create your Atlas account</h2>
                <p className="mt-2 text-sm leading-6 text-[#62728d]">
                  Accounts keep your uploaded charts private to you. Your workspaces and source files are only visible to your account.
                </p>
                <label className="mt-5 block text-xs font-semibold uppercase tracking-[0.12em] text-[#7a88a3]">
                  Display name
                </label>
                <input
                  aria-label="Display name"
                  value={signUpDisplayName}
                  onChange={(event) => setSignUpDisplayName(event.target.value)}
                  className="mt-2 w-full rounded-2xl border border-[#d5deea] bg-white px-4 py-3 text-sm text-[#18202b] outline-none transition-colors focus:border-[#4d68ff]"
                  autoComplete="name"
                  type="text"
                  placeholder="Dr. Max Gibber"
                />
                <label className="mt-4 block text-xs font-semibold uppercase tracking-[0.12em] text-[#7a88a3]">
                  Email
                </label>
                <input
                  aria-label="Signup email"
                  value={signUpEmail}
                  onChange={(event) => setSignUpEmail(event.target.value)}
                  className="mt-2 w-full rounded-2xl border border-[#d5deea] bg-white px-4 py-3 text-sm text-[#18202b] outline-none transition-colors focus:border-[#4d68ff]"
                  autoComplete="email"
                  type="email"
                />
                <label className="mt-4 block text-xs font-semibold uppercase tracking-[0.12em] text-[#7a88a3]">
                  Password
                </label>
                <input
                  aria-label="Signup password"
                  type="password"
                  value={signUpPassword}
                  onChange={(event) => setSignUpPassword(event.target.value)}
                  className="mt-2 w-full rounded-2xl border border-[#d5deea] bg-white px-4 py-3 text-sm text-[#18202b] outline-none transition-colors focus:border-[#4d68ff]"
                  autoComplete="new-password"
                  placeholder="At least 8 characters"
                />
                {signUpError && (
                  <p className="mt-3 text-sm text-[#b42318]">{signUpError}</p>
                )}
                <button
                  type="submit"
                  disabled={
                    isLoading ||
                    !signUpEmail.trim() ||
                    !signUpDisplayName.trim() ||
                    signUpPassword.length < 8
                  }
                  className="mt-5 inline-flex items-center gap-2 rounded-2xl bg-[#4d68ff] px-5 py-3 text-sm font-semibold text-white transition-colors hover:bg-[#3c57ef] disabled:cursor-not-allowed disabled:opacity-70"
                >
                  {isLoading ? "Creating account..." : "Create account"}
                  <ArrowRight size={16} />
                </button>
                <p className="mt-4 text-xs leading-5 text-[#7a88a3]">
                  Atlas is in active development. Your uploads are stored on the application server and only visible to your account.
                </p>
              </form>
            )}
          </section>
        </main>
      </div>
    </div>
  );
}

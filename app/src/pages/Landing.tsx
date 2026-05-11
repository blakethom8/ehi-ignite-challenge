import { useState, type FormEvent } from "react";
import { Link } from "react-router-dom";
import { ArrowRight, Boxes, Database, FileSearch, ShieldCheck, Upload, type LucideIcon } from "lucide-react";
import { DemoPatientPicker } from "../components/atlas/DemoPatientPicker";
import { useAccessContext } from "../context/AccessContext";

const moduleCards = [
  {
    title: "Patient Record",
    body: "Intake, harmonization, publishing, and patient context in one operational pipeline.",
    caption: "Prepared chart layer",
    to: "/patient-record",
    icon: FileSearch,
    accent: "from-[#eff3ff] via-[#f8faff] to-[#ffffff]",
    edge: "border-[#cad6ff]",
    glow: "shadow-[0_22px_70px_rgba(77,104,255,0.10)]",
    detail: "Source intake • review queue • canonical publish",
  },
  {
    title: "FHIR Charts",
    body: "Prepared chart surfaces for summary, history, safety, patient data, and chart-grounded review.",
    caption: "Clinical chart views",
    to: "/fhir-charts",
    icon: Database,
    accent: "from-[#edf8ff] via-[#f7fcff] to-[#ffffff]",
    edge: "border-[#c8e2f1]",
    glow: "shadow-[0_22px_70px_rgba(30,120,185,0.10)]",
    detail: "Summary • timeline • labs • grounded assistant",
  },
  {
    title: "Caspian",
    body: "Private, first-party clinical workspace for workflow execution, review, and citation-backed reasoning.",
    caption: "Private workflow agent",
    to: "/caspian",
    icon: ShieldCheck,
    accent: "from-[#eefaf4] via-[#f8fcfa] to-[#ffffff]",
    edge: "border-[#cbe5d8]",
    glow: "shadow-[0_22px_70px_rgba(54,128,94,0.10)]",
    detail: "Private boundary • approvals • evidence trace",
  },
  {
    title: "Plugins",
    body: "Consented external tools that operate from the chart while keeping their trust posture visible.",
    caption: "External runtime surfaces",
    to: "/workspaces",
    icon: Boxes,
    accent: "from-[#f4efff] via-[#fbf8ff] to-[#ffffff]",
    edge: "border-[#ddd0ff]",
    glow: "shadow-[0_22px_70px_rgba(113,79,196,0.10)]",
    detail: "Trial finder • med access • second opinion",
  },
];

export function Landing() {
  const { activePatientId, activePatientName, isDemo, isLoading, isUnlocked, signIn, user } = useAccessContext();
  const [email, setEmail] = useState("clinician@atlas.local");
  const [password, setPassword] = useState("atlas-demo-password");
  const [signInError, setSignInError] = useState<string | null>(null);
  const moduleCardsForState = moduleCards.map((card) => ({
    ...card,
    to: activePatientId ? `${card.to}?patient=${encodeURIComponent(activePatientId)}` : card.to,
  }));

  const handleSignIn = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setSignInError(null);
    try {
      await signIn(email, password);
    } catch (error) {
      if (error instanceof Error && error.message.trim()) {
        setSignInError(error.message);
        return;
      }
      setSignInError("Sign-in failed. Check the account credentials and try again.");
    }
  };

  return (
    <div className="min-h-screen bg-[radial-gradient(circle_at_top,#f6f9ff_0%,#eef3f8_42%,#e9eef4_100%)] text-[#18202b]">
      <header className="border-b border-[#dde5ef] bg-[rgba(255,255,255,0.88)] backdrop-blur">
        <div className="mx-auto flex max-w-7xl items-center justify-between gap-6 px-6 py-5">
          <div className="min-w-0">
            <p className="text-[11px] font-semibold uppercase tracking-[0.22em] text-[#7f8aa0]">
              EHI Exchange Platform
            </p>
            <p className="mt-1 text-lg font-semibold text-[#18202b]">
              Clinical workflow workspace
            </p>
          </div>
          <div className="flex items-center gap-3">
            <Link
              to="/using-atlas"
              className="hidden text-sm font-semibold text-[#52627f] transition-colors hover:text-[#3657ff] sm:inline-flex"
            >
              About Atlas
            </Link>
            {isUnlocked && activePatientId ? (
              <Link
                to={`/patient-record?patient=${encodeURIComponent(activePatientId)}`}
                className="inline-flex items-center gap-2 rounded-2xl bg-[#4d68ff] px-5 py-3 text-sm font-semibold text-white shadow-[0_10px_24px_rgba(77,104,255,0.22)] transition-colors hover:bg-[#3c57ef]"
              >
                Continue with {isDemo ? "demo" : "active"} patient
                <ArrowRight size={16} />
              </Link>
              ) : (
              <Link
                to="/guest-harmonization"
                className="inline-flex items-center gap-2 rounded-2xl bg-[#4d68ff] px-5 py-3 text-sm font-semibold text-white shadow-[0_10px_24px_rgba(77,104,255,0.22)] transition-colors hover:bg-[#3c57ef]"
              >
                Try with my files
                <ArrowRight size={16} />
              </Link>
            )}
          </div>
        </div>
      </header>

      <main className="px-6 py-10">
        <section className="mx-auto max-w-7xl">
          <section className="relative overflow-hidden rounded-[36px] px-2 py-4 lg:px-0">
            <div className="absolute inset-x-0 top-0 -z-10 h-[420px] rounded-[40px] bg-[radial-gradient(circle_at_15%_18%,rgba(77,104,255,0.18),transparent_30%),radial-gradient(circle_at_82%_22%,rgba(101,198,255,0.16),transparent_26%),linear-gradient(180deg,rgba(255,255,255,0.72),rgba(255,255,255,0))]" />
            <div className="grid gap-10 lg:grid-cols-[1.1fr_0.9fr] lg:items-end">
              <div className="max-w-4xl">
                <p className="text-[11px] font-semibold uppercase tracking-[0.22em] text-[#4d68ff]">
                  Health-record workspace
                </p>
                <h1 className="mt-5 text-5xl font-semibold leading-[0.94] tracking-[-0.05em] text-[#171b24] sm:text-6xl lg:text-[88px]">
                  Bring scattered health records into one reviewable workspace.
                </h1>
                <p className="mt-6 max-w-3xl text-lg leading-8 text-[#5f6f89]">
                  Explore synthetic sample records, run a temporary harmonization with your own files, or sign in to save private record workspaces.
                </p>
                <div className="mt-8 flex flex-wrap gap-3">
                  {isUnlocked && activePatientId ? (
                    <>
                      <Link
                        to={`/patient-record?patient=${encodeURIComponent(activePatientId)}`}
                        className="inline-flex items-center gap-2 rounded-2xl bg-[#4d68ff] px-5 py-3 text-sm font-semibold text-white transition-colors hover:bg-[#3c57ef]"
                      >
                        Open patient record
                        <ArrowRight size={16} />
                      </Link>
                      <Link
                        to={`/records-pool?patient=${encodeURIComponent(activePatientId)}`}
                        className="inline-flex items-center gap-2 rounded-2xl border border-[#d5deea] bg-[rgba(255,255,255,0.76)] px-5 py-3 text-sm font-semibold text-[#33415b] transition-colors hover:border-[#4d68ff] hover:text-[#3657ff]"
                      >
                        Switch demo patient
                      </Link>
                    </>
                  ) : (
                    <>
                      <a
                        href="#demo-access"
                        className="inline-flex items-center gap-2 rounded-2xl bg-[#4d68ff] px-5 py-3 text-sm font-semibold text-white transition-colors hover:bg-[#3c57ef]"
                      >
                        Explore sample demo
                        <ArrowRight size={16} />
                      </a>
                      <Link
                        to="/guest-harmonization"
                        className="inline-flex items-center gap-2 rounded-2xl border border-[#d5deea] bg-[rgba(255,255,255,0.76)] px-5 py-3 text-sm font-semibold text-[#33415b] transition-colors hover:border-[#4d68ff] hover:text-[#3657ff]"
                      >
                        Try with my files
                        <Upload size={16} />
                      </Link>
                    </>
                  )}
                </div>
              </div>

              <div className="grid gap-3 sm:grid-cols-3 lg:grid-cols-1">
                {isUnlocked && activePatientId ? (
                  <div className="rounded-[24px] border border-[rgba(77,104,255,0.14)] bg-[rgba(255,255,255,0.82)] p-5 backdrop-blur sm:col-span-3 lg:col-span-1">
                    <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-[#4d68ff]">
                      Active environment
                    </p>
                    <p className="mt-3 text-xl font-semibold text-[#18202b]">
                      {activePatientName ?? activePatientId}
                    </p>
                    <p className="mt-2 text-sm leading-6 text-[#3e4d68]">
                      {isDemo
                        ? "Sample chart is active. The shared shell now runs through a server-backed sample session."
                        : user
                          ? `Signed in as ${user.display_name}. Select or switch patients without leaving the shell.`
                          : "Authenticated access is active."}
                    </p>
                    <div className="mt-3 inline-flex rounded-full bg-[#eef2ff] px-3 py-1 text-[11px] font-semibold uppercase tracking-[0.14em] text-[#4d68ff]">
                      {isDemo ? "Demo patient unlocked" : "Active patient context"}
                    </div>
                    {user && !isDemo && (
                      <div className="mt-3 text-xs font-medium text-[#62728d]">
                        Logged in as {user.email}
                      </div>
                    )}
                  </div>
                ) : (
                  <>
                    <div className="rounded-[24px] border border-[rgba(77,104,255,0.14)] bg-[rgba(255,255,255,0.72)] p-5 backdrop-blur">
                      <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-[#7a88a3]">
                        Access gate
                      </p>
                      <p className="mt-3 text-sm leading-6 text-[#3e4d68]">
                        Patient-specific data stays locked until you sign in, start a sample workspace, or create a temporary guest run.
                      </p>
                    </div>
                    <div className="rounded-[24px] border border-[rgba(77,104,255,0.14)] bg-[rgba(255,255,255,0.72)] p-5 backdrop-blur">
                      <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-[#7a88a3]">
                        Shared shell
                      </p>
                      <p className="mt-3 text-sm leading-6 text-[#3e4d68]">
                        Modules feel like one application instead of disconnected demos, but each surface keeps its own workflow posture.
                      </p>
                    </div>
                    <div className="rounded-[24px] border border-[rgba(77,104,255,0.14)] bg-[rgba(255,255,255,0.72)] p-5 backdrop-blur">
                      <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-[#7a88a3]">
                        Trust visible
                      </p>
                      <p className="mt-3 text-sm leading-6 text-[#3e4d68]">
                        Private clinical workflows and consented external plugins can coexist without hiding the trust boundary.
                      </p>
                    </div>
                  </>
                )}
              </div>
            </div>
          </section>

          <section className="mt-8" id="demo-access">
            {!isUnlocked && (
              <>
              <div className="mb-6 grid gap-4 lg:grid-cols-3">
                <EntryCard
                  title="Explore sample demo"
                  body="Review prepared synthetic records through the patient chart and workflow surfaces."
                  to="#sample-demo"
                  icon={FileSearch}
                  primary
                />
                <EntryCard
                  title="Try with my files"
                  body="Upload files into a temporary guest workspace and download a portable output."
                  to="/guest-harmonization"
                  icon={Upload}
                />
                <EntryCard
                  title="Log in / Sign up"
                  body="Use an account to save private record workspaces and return later."
                  to="#account-access"
                  icon={ShieldCheck}
                />
              </div>
              <div className="mb-6 grid gap-6 rounded-[30px] border border-[#cad6ff] bg-[rgba(255,255,255,0.78)] p-6 shadow-[0_22px_70px_rgba(77,104,255,0.08)] lg:grid-cols-[0.95fr_1.05fr]">
                <form id="account-access" onSubmit={handleSignIn} className="rounded-[24px] border border-[#d8e0eb] bg-white/75 p-5">
                  <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-[#4d68ff]">
                    Sign in
                  </p>
                  <h3 className="mt-2 text-xl font-semibold text-[#18202b]">
                    Use your account
                  </h3>
                  <p className="mt-2 text-sm leading-6 text-[#62728d]">
                    Account workspaces are for saved health records. Public account creation is still being wired, so local development uses the seeded account.
                  </p>
                  <label className="mt-4 block text-xs font-semibold uppercase tracking-[0.12em] text-[#7a88a3]">
                    Email
                  </label>
                  <input
                    value={email}
                    onChange={(event) => setEmail(event.target.value)}
                    className="mt-2 w-full rounded-2xl border border-[#d5deea] bg-white px-4 py-3 text-sm text-[#18202b] outline-none transition-colors focus:border-[#4d68ff]"
                    autoComplete="username"
                  />
                  <label className="mt-4 block text-xs font-semibold uppercase tracking-[0.12em] text-[#7a88a3]">
                    Password
                  </label>
                  <input
                    type="password"
                    value={password}
                    onChange={(event) => setPassword(event.target.value)}
                    className="mt-2 w-full rounded-2xl border border-[#d5deea] bg-white px-4 py-3 text-sm text-[#18202b] outline-none transition-colors focus:border-[#4d68ff]"
                    autoComplete="current-password"
                  />
                  {signInError && (
                    <p className="mt-3 text-sm text-[#b42318]">{signInError}</p>
                  )}
                  <button
                    type="submit"
                    disabled={isLoading}
                    className="mt-5 inline-flex items-center gap-2 rounded-2xl bg-[#4d68ff] px-5 py-3 text-sm font-semibold text-white transition-colors hover:bg-[#3c57ef] disabled:cursor-not-allowed disabled:opacity-70"
                  >
                    {isLoading ? "Checking session..." : "Sign in"}
                    <ArrowRight size={16} />
                  </button>
                </form>
                <div id="sample-demo">
                  <DemoPatientPicker destination={(patientId) => `/patient-record?patient=${encodeURIComponent(patientId)}`} />
                </div>
              </div>
              </>
            )}
            <div className="flex flex-col gap-3 lg:flex-row lg:items-end lg:justify-between">
              <div className="max-w-2xl">
                <p className="text-[11px] font-semibold uppercase tracking-[0.2em] text-[#4d68ff]">
                  {isUnlocked ? "Core surfaces" : "Available after access"}
                </p>
                <h2 className="mt-2 text-3xl font-semibold tracking-[-0.03em] text-[#18202b] sm:text-4xl">
                  Four working environments, one prepared patient chart.
                </h2>
              </div>
              <p className="max-w-2xl text-sm leading-7 text-[#62728d]">
                {isUnlocked
                  ? "These are the main components of the platform for the active patient context."
                  : "These are the main product surfaces. Access comes first; module navigation comes after the patient context is established."}
              </p>
            </div>

            <div className="mt-6 grid gap-5 xl:grid-cols-2">
              {moduleCardsForState.map((card) => {
                const Icon = card.icon;
                return (
                  <Link
                    key={card.title}
                    to={card.to}
                    className={`group relative overflow-hidden rounded-[30px] border ${card.edge} bg-gradient-to-br ${card.accent} p-6 ${card.glow} transition-transform duration-200 ${
                      isUnlocked ? "hover:-translate-y-1" : "pointer-events-none opacity-70"
                    }`}
                  >
                    <div className="absolute inset-y-0 right-0 w-[44%] bg-[linear-gradient(135deg,rgba(255,255,255,0.04),rgba(255,255,255,0.44))]" />
                    <div className="absolute right-6 top-6 h-24 w-24 rounded-full border border-[rgba(77,104,255,0.10)] bg-[radial-gradient(circle,rgba(255,255,255,0.9),rgba(255,255,255,0))]" />

                    <div className="relative">
                      <div className="flex items-start justify-between gap-6">
                        <div className="flex h-14 w-14 items-center justify-center rounded-[18px] border border-[rgba(77,104,255,0.12)] bg-[rgba(255,255,255,0.72)] text-[#3558ff]">
                          <Icon size={24} />
                        </div>
                        <div className="rounded-full border border-[rgba(24,32,43,0.08)] bg-[rgba(255,255,255,0.65)] px-3 py-1 text-[11px] font-semibold uppercase tracking-[0.14em] text-[#6f7e98]">
                          {card.caption}
                        </div>
                      </div>

                      <h3 className="mt-10 text-[30px] font-semibold tracking-[-0.04em] text-[#18202b]">
                        {card.title}
                      </h3>
                      <p className="mt-3 max-w-xl text-base leading-7 text-[#556784]">
                        {card.body}
                      </p>

                      <div className="mt-8 flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
                        <p className="text-[12px] font-medium uppercase tracking-[0.16em] text-[#7887a1]">
                          {card.detail}
                        </p>
                        {isUnlocked ? (
                          <span className="inline-flex items-center gap-2 text-sm font-semibold text-[#3558ff] transition-all group-hover:gap-3">
                            Open surface
                            <ArrowRight size={15} />
                          </span>
                        ) : (
                          <span className="text-sm font-semibold text-[#71829d]">
                            Available after access
                          </span>
                        )}
                      </div>
                    </div>
                  </Link>
                );
              })}
            </div>
          </section>
        </section>
      </main>
    </div>
  );
}

function EntryCard({
  title,
  body,
  to,
  icon: Icon,
  primary = false,
}: {
  title: string;
  body: string;
  to: string;
  icon: LucideIcon;
  primary?: boolean;
}) {
  const className = `block rounded-[24px] border p-5 transition-colors ${
    primary
      ? "border-[#cad6ff] bg-white shadow-[0_16px_40px_rgba(77,104,255,0.08)] hover:border-[#4d68ff]"
      : "border-[#d8e0eb] bg-white/75 hover:border-[#4d68ff]"
  }`;
  const content = (
    <>
      <div className="flex h-11 w-11 items-center justify-center rounded-[14px] bg-[#eef2ff] text-[#4d68ff]">
        <Icon size={20} />
      </div>
      <h3 className="mt-4 text-lg font-semibold text-[#18202b]">{title}</h3>
      <p className="mt-2 text-sm leading-6 text-[#62728d]">{body}</p>
      <span className="mt-4 inline-flex items-center gap-2 text-sm font-semibold text-[#3657ff]">
        Continue
        <ArrowRight size={15} />
      </span>
    </>
  );
  if (to.startsWith("#")) {
    return <a href={to} className={className}>{content}</a>;
  }
  return <Link to={to} className={className}>{content}</Link>;
}

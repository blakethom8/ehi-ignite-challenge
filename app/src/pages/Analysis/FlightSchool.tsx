import { useMemo, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { CheckCircle2, Circle, Compass, ExternalLink, GraduationCap, Sparkles, Target } from "lucide-react";

interface Lesson {
  id: string;
  title: string;
  goal: string;
  why: string;
  exercise: string;
  completeWhen: string;
  links: Array<{ label: string; to: string }>;
  chatPrompts: string[];
}

const LESSONS: Lesson[] = [
  {
    id: "orientation",
    title: "Orientation: Know Your FHIR Ground Truth",
    goal: "Understand what one patient bundle contains and where uncertainty starts.",
    why: "If the team can’t distinguish source truth from derived logic, every downstream model becomes brittle.",
    exercise:
      "Open one patient in Overview and identify three direct source facts: demographics, active meds, and encounter span.",
    completeWhen:
      "You can point to one field for identity, one for timeline scope, and one for current treatment context.",
    links: [
      { label: "Explorer Overview", to: "/explorer" },
      { label: "Data Definitions", to: "/analysis/definitions" },
    ],
    chatPrompts: [
      "What are the top 5 facts I should know about this patient before pre-op planning?",
      "Which facts in this summary are direct source fields versus derived interpretations?",
    ],
  },
  {
    id: "timeline",
    title: "Temporal Reasoning: What Is Active vs Historical",
    goal: "Read patient history as a sequence of state changes, not isolated records.",
    why: "Clinical decisions depend on recency and persistence, not just presence of a diagnosis or medication.",
    exercise:
      "In Timeline, compare the most recent encounter against a prior year and note what changed in meds and conditions.",
    completeWhen:
      "You can state one active risk and one historical risk with dates.",
    links: [
      { label: "Explorer Timeline", to: "/explorer/timeline" },
      { label: "Methodology", to: "/analysis/methodology" },
    ],
    chatPrompts: [
      "What changed in the last 6 months that affects surgical risk?",
      "Is this risk active now, historical, or unresolved?",
    ],
  },
  {
    id: "safety",
    title: "Safety Logic: Drug Classes and Interactions",
    goal: "Use class-level safety flags to generate immediate pre-op actions.",
    why: "Medication burden is the fastest path to actionable insight in pre-case review.",
    exercise:
      "Review Safety and Interactions for one patient, then draft a one-paragraph pre-op hold/monitor plan.",
    completeWhen:
      "You can list one hold-now item, one monitor item, and one coordination item.",
    links: [
      { label: "Explorer Safety", to: "/explorer/safety" },
      { label: "Explorer Interactions", to: "/explorer/interactions" },
    ],
    chatPrompts: [
      "Give me an opinionated pre-op medication plan with highest-risk items first.",
      "Push back if the chart evidence is weak or missing for a recommendation.",
    ],
  },
  {
    id: "coverage",
    title: "Reliability: Don’t Over-Trust Sparse Fields",
    goal: "Attach confidence expectations to every interpretation.",
    why: "Low-coverage fields can produce false certainty if they are treated as complete.",
    exercise:
      "Open Coverage and select two fields below 70% coverage. Describe how each should alter recommendation confidence.",
    completeWhen:
      "You can explain one place where the app should push back due to sparse evidence.",
    links: [
      { label: "Coverage Dashboard", to: "/analysis/coverage" },
      { label: "Data Definitions", to: "/analysis/definitions" },
    ],
    chatPrompts: [
      "What can’t we confidently conclude from this chart?",
      "Which claims should be marked as low-confidence based on field coverage?",
    ],
  },
  {
    id: "provider-assistant",
    title: "Provider Chat: Ask, Verify, Decide",
    goal: "Use conversational retrieval while keeping evidence and judgment explicit.",
    why: "The assistant should answer fast, be direct, and push back when data quality does not support strong conclusions.",
    exercise:
      "Ask 3 pre-op questions in Provider Assistant, then validate each answer against cited records.",
    completeWhen:
      "You can trust the assistant’s speed without losing source-level accountability.",
    links: [
      { label: "Provider Assistant", to: "/explorer/assistant" },
      { label: "Explorer Timeline", to: "/explorer/timeline" },
    ],
    chatPrompts: [
      "Is this patient safe to proceed this week, and what would you block on first?",
      "Give me the hard pushback if my plan ignores chart evidence.",
    ],
  },
];

function localStorageKey(patientId: string | null): string {
  return patientId ? `ehi-flight-school-progress:${patientId}` : "ehi-flight-school-progress:global";
}

function useProgress(patientId: string | null) {
  const key = localStorageKey(patientId);
  const [checked, setChecked] = useState<Record<string, boolean>>(() => {
    try {
      const raw = localStorage.getItem(key);
      if (!raw) return {};
      const parsed = JSON.parse(raw) as unknown;
      if (parsed && typeof parsed === "object") {
        return parsed as Record<string, boolean>;
      }
      return {};
    } catch {
      return {};
    }
  });

  function toggle(id: string) {
    setChecked((prev) => {
      const next = { ...prev, [id]: !prev[id] };
      localStorage.setItem(key, JSON.stringify(next));
      return next;
    });
  }

  return { checked, toggle };
}

export function AnalysisFlightSchool() {
  const [searchParams] = useSearchParams();
  const patientId = searchParams.get("patient");
  const { checked, toggle } = useProgress(patientId);

  const completedCount = useMemo(() => {
    return LESSONS.filter((lesson) => checked[lesson.id]).length;
  }, [checked]);

  const completionPct = Math.round((completedCount / LESSONS.length) * 100);

  return (
    <div className="mx-auto max-w-7xl px-6 py-8 lg:px-10">
      <section className="rounded-3xl border border-[#d1dff9] bg-[linear-gradient(135deg,#f7fbff_0%,#edf4ff_55%,#f9fcff_100%)] p-6 lg:p-8">
        <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
          <div className="max-w-3xl">
            <p className="inline-flex items-center gap-2 rounded-full bg-[#e8f0ff] px-3 py-1 text-xs font-semibold uppercase tracking-wider text-[#1d4ed8]">
              <GraduationCap size={13} />
              FHIR Flight School
            </p>
            <h1 className="mt-3 text-3xl font-semibold tracking-tight text-[#0f172a] lg:text-4xl">
              Learn the data model, then make clinical decisions with confidence
            </h1>
            <p className="mt-3 text-sm leading-6 text-[#334155] lg:text-base">
              This guided track teaches how to read FHIR signals in this platform, where interpretation is strong,
              and where the system should push back instead of pretending certainty.
            </p>
          </div>

          <div className="rounded-2xl bg-white p-4 shadow-[rgb(209_223_249)_0px_0px_0px_1px] lg:w-[280px]">
            <p className="text-xs font-semibold uppercase tracking-wider text-[#1d4ed8]">Progress</p>
            <p className="mt-1 text-3xl font-semibold text-[#0f172a]">{completionPct}%</p>
            <p className="mt-1 text-xs text-[#64748b]">
              {completedCount} of {LESSONS.length} lessons completed
            </p>
            <div className="mt-3 h-2.5 rounded-full bg-[#e2e8f0]">
              <div className="h-full rounded-full bg-[#3b82f6]" style={{ width: `${completionPct}%` }} />
            </div>
          </div>
        </div>
      </section>

      <section className="mt-6 grid gap-4 sm:grid-cols-3">
        <article className="rounded-2xl bg-white p-4 shadow-[rgb(224_226_232)_0px_0px_0px_1px]">
          <p className="flex items-center gap-2 text-sm font-semibold text-[#0f172a]">
            <Compass size={16} className="text-[#1d4ed8]" />
            Mode
          </p>
          <p className="mt-2 text-sm text-[#475569]">Five structured missions from source truth to provider chat.</p>
        </article>

        <article className="rounded-2xl bg-white p-4 shadow-[rgb(224_226_232)_0px_0px_0px_1px]">
          <p className="flex items-center gap-2 text-sm font-semibold text-[#0f172a]">
            <Target size={16} className="text-[#1d4ed8]" />
            Outcome
          </p>
          <p className="mt-2 text-sm text-[#475569]">Answer clinical questions quickly, with explicit evidence and caveats.</p>
        </article>

        <article className="rounded-2xl bg-white p-4 shadow-[rgb(224_226_232)_0px_0px_0px_1px]">
          <p className="flex items-center gap-2 text-sm font-semibold text-[#0f172a]">
            <Sparkles size={16} className="text-[#1d4ed8]" />
            Personality Target
          </p>
          <p className="mt-2 text-sm text-[#475569]">Direct, concise, responsive, and willing to challenge unsafe assumptions.</p>
        </article>
      </section>

      <section className="mt-7 space-y-4">
        {LESSONS.map((lesson, index) => {
          const complete = checked[lesson.id] === true;
          return (
            <article
              key={lesson.id}
              className={`rounded-2xl border p-5 ${
                complete ? "border-[#bbf7d0] bg-[#f0fdf4]" : "border-[#e2e8f0] bg-white"
              }`}
            >
              <div className="flex items-start justify-between gap-3">
                <div className="min-w-0">
                  <p className="text-xs font-semibold uppercase tracking-wider text-[#64748b]">
                    Lesson {index + 1}
                  </p>
                  <h2 className="mt-1 text-lg font-semibold text-[#0f172a]">{lesson.title}</h2>
                  <p className="mt-1 text-sm text-[#334155]">{lesson.goal}</p>
                </div>
                <button
                  onClick={() => toggle(lesson.id)}
                  className={`inline-flex shrink-0 items-center gap-1 rounded-full px-3 py-1 text-xs font-semibold ${
                    complete
                      ? "bg-[#dcfce7] text-[#166534] hover:bg-[#bbf7d0]"
                      : "bg-[#eef2ff] text-[#3730a3] hover:bg-[#e0e7ff]"
                  }`}
                >
                  {complete ? <CheckCircle2 size={13} /> : <Circle size={13} />}
                  {complete ? "Completed" : "Mark complete"}
                </button>
              </div>

              <div className="mt-4 grid gap-3 lg:grid-cols-[1.1fr_0.9fr]">
                <div className="space-y-3">
                  <div className="rounded-xl bg-[#f8fafc] p-3">
                    <p className="text-xs font-semibold uppercase tracking-wider text-[#64748b]">Why this matters</p>
                    <p className="mt-1 text-sm text-[#334155]">{lesson.why}</p>
                  </div>

                  <div className="rounded-xl bg-[#f8fafc] p-3">
                    <p className="text-xs font-semibold uppercase tracking-wider text-[#64748b]">Exercise</p>
                    <p className="mt-1 text-sm text-[#334155]">{lesson.exercise}</p>
                  </div>

                  <div className="rounded-xl bg-[#fff7ed] p-3">
                    <p className="text-xs font-semibold uppercase tracking-wider text-[#9a3412]">Complete when</p>
                    <p className="mt-1 text-sm text-[#7c2d12]">{lesson.completeWhen}</p>
                  </div>
                </div>

                <div className="space-y-3">
                  <div className="rounded-xl border border-[#e2e8f0] p-3">
                    <p className="text-xs font-semibold uppercase tracking-wider text-[#64748b]">Jump to views</p>
                    <div className="mt-2 space-y-2">
                      {lesson.links.map((link) => (
                        <a
                          key={link.label}
                          href={`${link.to}${patientId ? `?patient=${patientId}` : ""}`}
                          className="inline-flex items-center gap-1 text-sm font-medium text-[#1d4ed8] hover:text-[#1e40af]"
                        >
                          {link.label}
                          <ExternalLink size={13} />
                        </a>
                      ))}
                    </div>
                  </div>

                  <div className="rounded-xl border border-[#e2e8f0] p-3">
                    <p className="text-xs font-semibold uppercase tracking-wider text-[#64748b]">Prompt ideas</p>
                    <ul className="mt-2 space-y-2 text-sm text-[#334155]">
                      {lesson.chatPrompts.map((prompt) => (
                        <li key={prompt} className="rounded-lg bg-[#f8fafc] px-2.5 py-2">
                          {prompt}
                        </li>
                      ))}
                    </ul>
                  </div>
                </div>
              </div>
            </article>
          );
        })}
      </section>
    </div>
  );
}

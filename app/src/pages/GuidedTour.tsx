import { Link } from "react-router-dom";
import {
  ArrowRight,
  Camera,
  CheckCircle2,
  GitBranch,
  MonitorPlay,
  MousePointerClick,
  MousePointer2,
  Stethoscope,
} from "lucide-react";

const tourSteps = [
  {
    title: "Start with the patient data problem",
    body: "The tour introduces why scattered records need an aggregation and cleaning layer before any clinical module can be trusted.",
    icon: GitBranch,
  },
  {
    title: "Show the expected screen",
    body: "Each walkthrough step should have a screenshot, arrows, and labels that explain what the reviewer is looking at.",
    icon: Camera,
  },
  {
    title: "Demonstrate the interaction",
    body: "A future Clicky-style layer can move a cursor over the UI, click buttons, and show the expected result.",
    icon: MousePointer2,
  },
  {
    title: "Hand off to the real app",
    body: "After the learning tour, users should jump into Data Aggregator, FHIR Charts, or the clinical app demo with context.",
    icon: Stethoscope,
  },
];

export function GuidedTour() {
  return (
    <div className="min-h-screen bg-[#f5f6f8] text-[#1c1c1e]">
      <header className="border-b border-[#e1e4eb] bg-white px-6 py-4">
        <div className="mx-auto flex max-w-7xl items-center justify-between gap-6">
          <Link to="/" className="min-w-0">
            <p className="text-xs font-semibold uppercase tracking-[0.18em] text-[#9aa1b2]">
              EHI Exchange Platform
            </p>
            <p className="text-base font-semibold text-[#1c1c1e]">Guided tour</p>
          </Link>
          <Link
            to="/platform"
            className="inline-flex items-center gap-2 rounded-xl bg-[#5b76fe] px-4 py-2 text-sm font-semibold text-white shadow-sm transition-colors hover:bg-[#445ee8]"
          >
            Enter platform
            <ArrowRight size={15} />
          </Link>
        </div>
      </header>

      <main className="px-6 py-8">
        <section className="mx-auto max-w-7xl">
          <div className="grid gap-6 lg:grid-cols-[0.86fr_1.14fr] lg:items-end">
            <div>
              <p className="mb-3 text-xs font-semibold uppercase tracking-[0.16em] text-[#5b76fe]">
                Start here to learn about it
              </p>
              <h1 className="max-w-4xl text-4xl font-semibold tracking-tight text-[#18191f] lg:text-5xl">
                A guided learning path before the user enters the live app.
              </h1>
            </div>
            <p className="text-base leading-7 text-[#63708a]">
              This page is the placeholder for a first-time walkthrough. The goal is to explain what users should expect to see, why it matters, and which interactions demonstrate the product story.
            </p>
          </div>

          <div className="mt-8 grid gap-6 lg:grid-cols-[1.1fr_0.9fr]">
            <section className="rounded-[28px] border border-[#dfe5f0] bg-white p-6 shadow-sm">
              <div className="mb-5 flex items-center gap-2">
                <MonitorPlay size={19} className="text-[#5b76fe]" />
                <h2 className="text-lg font-semibold">Future interactive guide concept</h2>
              </div>
              <div className="rounded-[24px] border border-dashed border-[#cfd7ff] bg-[#f6f8ff] p-6">
                <div className="grid gap-5 lg:grid-cols-[1fr_220px]">
                  <div>
                    <p className="text-xs font-semibold uppercase tracking-[0.16em] text-[#5b76fe]">
                      Screenshot walkthrough placeholder
                    </p>
                    <h3 className="mt-3 text-2xl font-semibold">Show the platform screen, then annotate it.</h3>
                    <p className="mt-3 text-sm leading-6 text-[#63708a]">
                      We can later drop in real screenshots and layer arrows, labels, and guided cursor movement over the key controls.
                    </p>
                  </div>
                  <div className="rounded-2xl border border-[#dfe5ff] bg-white p-4">
                    <div className="mb-3 h-3 w-28 rounded-full bg-[#dfe5ff]" />
                    <div className="space-y-2">
                      <div className="h-9 rounded-xl bg-[#eef1ff]" />
                      <div className="h-9 rounded-xl bg-[#eef1ff]" />
                      <div className="h-9 rounded-xl bg-[#eef1ff]" />
                    </div>
                    <div className="mt-5 flex items-center gap-2 text-sm font-semibold text-[#5b76fe]">
                      <MousePointerClick size={16} />
                      Click target
                    </div>
                  </div>
                </div>
              </div>
            </section>

            <section className="rounded-[28px] border border-[#c9f0e7] bg-[#effbf8] p-6 shadow-sm">
              <h2 className="text-lg font-semibold">What the guide should teach</h2>
              <div className="mt-5 space-y-3">
                {[
                  "What the platform is and why the FHIR Chart matters.",
                  "How Data Aggregator pulls and cleans records.",
                  "How to tell private insights from external marketplace modules.",
                  "Where patient selection belongs in the real platform flow.",
                ].map((item) => (
                  <div key={item} className="flex gap-3 rounded-xl border border-[#bdebdc] bg-white/75 p-4 text-sm leading-6 text-[#405c69]">
                    <CheckCircle2 size={16} className="mt-0.5 shrink-0 text-[#008f7a]" />
                    <span>{item}</span>
                  </div>
                ))}
              </div>
            </section>
          </div>

          <section className="mt-6 grid gap-4 md:grid-cols-4">
            {tourSteps.map((step) => {
              const Icon = step.icon;
              return (
                <div key={step.title} className="rounded-[22px] border border-[#e1e6ef] bg-white p-5 shadow-sm">
                  <div className="mb-4 flex h-11 w-11 items-center justify-center rounded-xl bg-[#eef1ff] text-[#5b76fe]">
                    <Icon size={20} />
                  </div>
                  <h2 className="font-semibold">{step.title}</h2>
                  <p className="mt-2 text-sm leading-6 text-[#667289]">{step.body}</p>
                </div>
              );
            })}
          </section>

          <div className="mt-6 flex flex-col gap-3 rounded-[24px] border border-[#e1e6ef] bg-white p-6 shadow-sm sm:flex-row sm:items-center sm:justify-between">
            <div>
              <h2 className="text-lg font-semibold">Continue into the working app</h2>
              <p className="mt-1 text-sm text-[#667289]">
                The guided experience should eventually hand users into the platform with the right context.
              </p>
            </div>
            <div className="flex flex-col gap-2 sm:flex-row">
              <Link
                to="/platform"
                className="inline-flex items-center justify-center gap-2 rounded-xl bg-[#5b76fe] px-5 py-3 text-sm font-semibold text-white shadow-sm transition-colors hover:bg-[#445ee8]"
              >
                Open platform
                <ArrowRight size={16} />
              </Link>
              <Link
                to="/preop"
                className="inline-flex items-center justify-center gap-2 rounded-xl border border-[#dfe3eb] bg-white px-5 py-3 text-sm font-semibold text-[#526075] shadow-sm transition-colors hover:border-[#5b76fe] hover:text-[#5b76fe]"
              >
                Open clinical app demo
                <ArrowRight size={16} />
              </Link>
            </div>
          </div>
        </section>
      </main>
    </div>
  );
}

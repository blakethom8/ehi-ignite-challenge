import { Link } from "react-router-dom";
import { Boxes, Pill, Send, Telescope } from "lucide-react";

const PLUGINS = [
  {
    id: "trial-finder",
    icon: Telescope,
    title: "Trial Finder",
    version: "2.4.1",
    vendor: "Helix Clinical",
    desc: "Pulls a consented patient anchor from Caspian and runs a clinical-trial discovery loop against external registries. Produces ranked candidate boards, eligibility checks, and outreach packets — every outbound action gated by per-run approval.",
    boundary: "Consented external · per-run approval",
  },
  {
    id: "med-access",
    icon: Pill,
    title: "Medication Access",
    version: "1.7.0",
    vendor: "RxBridge",
    desc: "Coordinates patient-assistance program enrollment and prior-auth packets. Reads the active medication list from Caspian; submits packets to assistance programs after explicit clinician approval.",
    boundary: "Consented external · per-run approval",
  },
  {
    id: "site-coord",
    icon: Send,
    title: "Site Coordination",
    version: "0.9.3-beta",
    vendor: "TrialOps",
    desc: "Runs follow-up loops with trial sites: appointment confirmation, missing-records nudges, eligibility re-checks. Handles the operational overhead that nobody wants to manage by hand.",
    boundary: "Consented external · scheduled batch",
  },
];

export function PluginsIndex() {
  return (
    <div
      className="mx-auto w-full max-w-[1100px] flex-1 px-10 py-9"
      style={{ background: "var(--bg-app)" }}
    >
      <div
        className="border-b pb-7"
        style={{ borderColor: "var(--line-1)" }}
      >
        <div
          className="flex items-center gap-2 text-[10.5px] font-bold uppercase tracking-[0.12em]"
          style={{ color: "var(--ink-3)" }}
        >
          <Boxes className="h-3.5 w-3.5" strokeWidth={1.5} />
          Plugin marketplace
        </div>
        <h1
          className="mt-2 text-[26px] font-semibold leading-[1.1] tracking-tight"
          style={{ color: "var(--ink-1)" }}
        >
          Installable plugins
        </h1>
        <p
          className="mt-3 max-w-[70ch] text-[13.5px] leading-[1.55]"
          style={{ color: "var(--ink-2)" }}
        >
          Plugins run inside the same shell as Caspian, but with their own context strip, permissions ledger, and approval gates. Each plugin operates against a consented patient anchor. Outbound actions never leave the workspace without an explicit clinician approval.
        </p>
      </div>

      <div className="mt-7 grid grid-cols-1 gap-3 md:grid-cols-2">
        {PLUGINS.map((p) => {
          const Icon = p.icon;
          return (
            <Link
              key={p.id}
              to={`/workspaces/${p.id}`}
              className="group flex flex-col gap-2 rounded-md border p-4 transition-colors hover:border-[var(--action-line)]"
              style={{
                background: "var(--surface-1)",
                borderColor: "var(--line-1)",
              }}
            >
              <div className="flex items-center gap-2.5">
                <div
                  className="grid h-9 w-9 place-items-center rounded-md"
                  style={{
                    background: "rgba(67,56,202,0.10)",
                    color: "#4338ca",
                  }}
                >
                  <Icon className="h-4 w-4" strokeWidth={1.5} />
                </div>
                <div className="min-w-0 flex-1">
                  <div className="flex items-baseline gap-2">
                    <div
                      className="text-[13.5px] font-semibold"
                      style={{ color: "var(--ink-1)" }}
                    >
                      {p.title}
                    </div>
                    <div
                      className="rounded-[3px] px-1.5 py-px text-[11px] font-medium"
                      style={{
                        background: "rgba(67,56,202,0.08)",
                        color: "#4338ca",
                        fontFamily: "var(--font-mono)",
                      }}
                    >
                      @{p.version}
                    </div>
                  </div>
                  <div
                    className="text-[11.5px]"
                    style={{ color: "var(--ink-3)" }}
                  >
                    by {p.vendor}
                  </div>
                </div>
              </div>
              <p
                className="text-[12.5px] leading-[1.55]"
                style={{ color: "var(--ink-2)" }}
              >
                {p.desc}
              </p>
              <div
                className="mt-1 flex items-center justify-between border-t pt-2.5 text-[11px]"
                style={{ borderColor: "var(--line-1)", color: "var(--ink-3)" }}
              >
                <span>Boundary: {p.boundary}</span>
                <span
                  className="font-medium transition-colors group-hover:text-[var(--action)]"
                  style={{ color: "var(--ink-3)" }}
                >
                  Open plugin home →
                </span>
              </div>
            </Link>
          );
        })}
      </div>
    </div>
  );
}

import { useMemo, useState } from "react";
import { useSearchParams } from "react-router-dom";
import {
  useMutation,
  useQuery,
  useQueryClient,
} from "@tanstack/react-query";
import {
  Beaker,
  Loader2,
  Save,
  ScrollText,
  ShieldCheck,
  UserRound,
} from "lucide-react";
import { api } from "../../../api/client";
import { skillsApi } from "../../../api/skills";
import { EmptyState } from "../../../components/EmptyState";
import type {
  Citation,
  PendingEscalation,
  RunStateResponse,
  SaveRequest,
} from "../../../types/skills";

import { BriefPanel, type AnchorChoice } from "./components/BriefPanel";
import { EscalationBanner } from "./components/EscalationBanner";
import { PatientMemoryPanel } from "./components/PatientMemoryPanel";
import { RunHistorySidebar } from "./components/RunHistorySidebar";
import { SaveDestinationDrawer } from "./components/SaveDestinationDrawer";
import { TranscriptPane } from "./components/TranscriptPane";
import { WorkspacePane } from "./components/WorkspacePane";

const SKILL_NAME = "trial-matching";

/**
 * Trial Finder — net-new agentic-workspace module.
 *
 * Mounts at `/skills/trial-finder`. Two states share one route:
 * - Landing: brief panel on the left, run history on the right. The
 *   "Run trial finder" button starts a run and navigates with `?run=`.
 * - Run view: workspace.md + escalation banner + transcript pane.
 *   Polls every 2s while the run is in-flight; stops once
 *   `finished` / `failed`.
 */
export function TrialFinder() {
  const [searchParams] = useSearchParams();

  const patientId = searchParams.get("patient");
  const runId = searchParams.get("run");

  if (!patientId) {
    return (
      <div className="mx-auto max-w-2xl px-6 py-12">
        <EmptyState
          icon={UserRound}
          title="Pick a patient"
          bullets={[
            "Trial Finder runs against one patient's chart.",
            "Use the sidebar to pick a patient and start a run.",
          ]}
        />
      </div>
    );
  }

  if (!runId) {
    return <Landing patientId={patientId} />;
  }
  return <RunView patientId={patientId} runId={runId} />;
}

// ── Landing ────────────────────────────────────────────────────────────────

function Landing({ patientId }: { patientId: string }) {
  const [, setSearchParams] = useSearchParams();

  const acuityQuery = useQuery({
    queryKey: ["condition-acuity", patientId],
    queryFn: () => api.getConditionAcuity(patientId),
  });

  const overviewQuery = useQuery({
    queryKey: ["overview", patientId],
    queryFn: () => api.getOverview(patientId),
  });

  const runsQuery = useQuery({
    queryKey: ["skill-runs", patientId, SKILL_NAME],
    queryFn: () => skillsApi.listPatientRuns(patientId, SKILL_NAME),
    refetchOnWindowFocus: false,
  });

  const start = useMutation({
    mutationFn: (anchors: AnchorChoice[]) =>
      skillsApi.startRun(SKILL_NAME, {
        patient_id: patientId,
        brief: {
          anchors: anchors.map((a) => ({
            display: a.display,
            resource_id: a.resource_id,
            risk_category: a.risk_category,
            clinical_status: a.clinical_status,
          })),
          status: ["RECRUITING"],
          page_size: 8,
        },
      }),
    onSuccess: (data) => {
      const params = new URLSearchParams({
        patient: patientId,
        run: data.run_id,
      });
      setSearchParams(params, { replace: false });
    },
  });

  const patientName = overviewQuery.data?.name ?? "Patient";
  const ranked = acuityQuery.data?.ranked_active ?? [];

  return (
    <div className="mx-auto grid max-w-7xl gap-6 px-6 py-6 lg:grid-cols-[2fr_1fr]">
      <div>
        {acuityQuery.isLoading ? (
          <div className="flex h-48 items-center justify-center text-sm text-[#a5a8b5]">
            <Loader2 size={18} className="mr-2 animate-spin" />
            Loading chart anchors…
          </div>
        ) : (
          <BriefPanel
            patientName={patientName}
            rankedActive={ranked}
            isStarting={start.isPending}
            onStart={(anchors) => start.mutate(anchors)}
          />
        )}
      </div>

      <div className="space-y-4">
        <PatientMemoryPanel
          patientId={patientId}
          detailHref={`/skills/patients/memory?patient=${encodeURIComponent(
            patientId
          )}`}
        />
        <RunHistorySidebar
          patientId={patientId}
          runs={runsQuery.data ?? []}
          activeRunId={null}
        />
      </div>
    </div>
  );
}

// ── Run view ───────────────────────────────────────────────────────────────

function RunView({
  patientId,
  runId,
}: {
  patientId: string;
  runId: string;
}) {
  const queryClient = useQueryClient();
  const [drawerOpen, setDrawerOpen] = useState(false);

  const stateQuery = useQuery({
    queryKey: ["skill-run", SKILL_NAME, runId, patientId],
    queryFn: () => skillsApi.getRunState(SKILL_NAME, runId, patientId),
    refetchInterval: (query) => {
      const data = query.state.data;
      if (!data) return 2000;
      if (data.status === "finished" || data.status === "failed") return false;
      return 2000;
    },
  });

  const workspaceQuery = useQuery({
    queryKey: ["skill-workspace", SKILL_NAME, runId, patientId],
    queryFn: () => skillsApi.getWorkspace(SKILL_NAME, runId, patientId),
    refetchInterval: 2000,
    enabled: !!stateQuery.data,
  });

  const transcriptQuery = useQuery({
    queryKey: ["skill-transcript", SKILL_NAME, runId, patientId],
    queryFn: () => skillsApi.getTranscript(SKILL_NAME, runId, patientId),
    refetchInterval: 2000,
    enabled: !!stateQuery.data,
  });

  const runsQuery = useQuery({
    queryKey: ["skill-runs", patientId, SKILL_NAME],
    queryFn: () => skillsApi.listPatientRuns(patientId, SKILL_NAME),
    refetchOnWindowFocus: false,
  });

  const resolve = useMutation({
    mutationFn: ({
      approvalId,
      choice,
      notes,
    }: {
      approvalId: string;
      choice: string;
      notes: string;
    }) =>
      skillsApi.resolveEscalation(SKILL_NAME, runId, approvalId, patientId, {
        choice,
        notes,
        actor: "clinician",
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({
        queryKey: ["skill-run", SKILL_NAME, runId],
      });
    },
  });

  const save = useMutation({
    mutationFn: (payload: SaveRequest) =>
      skillsApi.saveRun(SKILL_NAME, runId, patientId, payload),
    onSuccess: () => {
      setDrawerOpen(false);
      queryClient.invalidateQueries({
        queryKey: ["skill-transcript", SKILL_NAME, runId],
      });
      queryClient.invalidateQueries({
        queryKey: ["skill-runs", patientId, SKILL_NAME],
      });
      // Pinned facts and context packages mutate the patient memory layer —
      // refresh the panel so the new content appears without a hard reload.
      queryClient.invalidateQueries({
        queryKey: ["skill-patient-memory", patientId],
      });
    },
  });

  const state = stateQuery.data;
  const workspace = workspaceQuery.data;
  const transcript = transcriptQuery.data;

  const pendingEscalation: PendingEscalation | null =
    state?.pending_escalations[0] ?? null;

  const finished = state?.status === "finished" || state?.status === "failed";

  return (
    <div className="mx-auto grid max-w-7xl gap-6 px-6 py-6 lg:grid-cols-[2fr_1fr]">
      <div className="space-y-5">
        {state ? <RunStatusHero state={state} /> : null}

        {pendingEscalation ? (
          <EscalationBanner
            escalation={pendingEscalation}
            isResolving={resolve.isPending}
            onResolve={async (choice, notes) => {
              await resolve.mutateAsync({
                approvalId: pendingEscalation.approval_id,
                choice,
                notes,
              });
            }}
          />
        ) : null}

        <section className="rounded-2xl bg-white p-6 shadow-[rgb(224_226_232)_0px_0px_0px_1px]">
          <div className="mb-4 flex items-center justify-between">
            <div className="flex items-center gap-2">
              <ScrollText size={16} className="text-[#5b76fe]" />
              <h2 className="text-sm font-semibold text-[#1c1c1e]">Workspace</h2>
            </div>
            <div className="flex items-center gap-2 text-[11px] text-[#a5a8b5]">
              <span>
                {workspace?.citations.length ?? 0} citations registered
              </span>
              {finished ? (
                <button
                  type="button"
                  onClick={() => setDrawerOpen(true)}
                  className="inline-flex items-center gap-1.5 rounded-lg border border-[#5b76fe] bg-[#eef1ff] px-3 py-1.5 text-xs font-semibold text-[#3a4ca8] hover:bg-[#dde3ff]"
                >
                  <Save size={12} />
                  Save…
                </button>
              ) : null}
            </div>
          </div>
          {workspace ? (
            <WorkspacePane
              markdown={workspace.markdown}
              citations={workspace.citations}
            />
          ) : (
            <div className="flex h-32 items-center justify-center text-xs text-[#a5a8b5]">
              <Loader2 size={14} className="mr-2 animate-spin" />
              Loading workspace…
            </div>
          )}
        </section>

        {finished && state?.status === "finished" ? (
          <FinishedSummary
            patientId={patientId}
            runId={runId}
            citations={workspace?.citations ?? []}
          />
        ) : null}
      </div>

      <div className="space-y-4">
        <section className="rounded-2xl bg-white p-4 shadow-[rgb(224_226_232)_0px_0px_0px_1px]">
          <div className="mb-3 flex items-center justify-between">
            <div className="flex items-center gap-2">
              <Beaker size={14} className="text-[#5b76fe]" />
              <h3 className="text-sm font-semibold text-[#1c1c1e]">Transcript</h3>
            </div>
            <span className="text-[11px] text-[#a5a8b5]">
              {transcript?.events.length ?? 0} events
            </span>
          </div>
          <TranscriptPane events={transcript?.events ?? []} />
        </section>

        <PatientMemoryPanel
          patientId={patientId}
          detailHref={`/skills/patients/memory?patient=${encodeURIComponent(
            patientId
          )}`}
        />

        <RunHistorySidebar
          patientId={patientId}
          runs={runsQuery.data ?? []}
          activeRunId={runId}
        />
      </div>

      <SaveDestinationDrawer
        open={drawerOpen}
        onClose={() => setDrawerOpen(false)}
        onSave={async (payload) => {
          await save.mutateAsync(payload);
        }}
        isSaving={save.isPending}
        citations={workspace?.citations ?? []}
        defaultPackageName="patient-trial-prefs"
      />
    </div>
  );
}

// ── Bits ───────────────────────────────────────────────────────────────────

function RunStatusHero({ state }: { state: RunStateResponse }) {
  const config = {
    created: { bg: "#f5f6f8", fg: "#555a6a", label: "Run created" },
    running: { bg: "#eef1ff", fg: "#3a4ca8", label: "Running" },
    escalated: { bg: "#fffbeb", fg: "#92400e", label: "Awaiting your decision" },
    validated: { bg: "#c3faf5", fg: "#187574", label: "Validated" },
    finished: { bg: "#f0fdf4", fg: "#166534", label: "Finished" },
    failed: { bg: "#fef2f2", fg: "#991b1b", label: "Failed" },
  }[state.status];

  return (
    <section
      className="rounded-2xl border p-4"
      style={{
        backgroundColor: config.bg,
        borderColor: "rgba(0,0,0,0.05)",
      }}
    >
      <div className="flex items-center justify-between gap-3">
        <div className="min-w-0">
          <p
            className="text-[10px] font-semibold uppercase tracking-wider"
            style={{ color: config.fg }}
          >
            {config.label}
          </p>
          <p className="mt-0.5 truncate font-mono text-xs text-[#1c1c1e]">
            run {state.run_id}
          </p>
        </div>
        <div className="flex items-center gap-2 text-[11px]" style={{ color: config.fg }}>
          <ShieldCheck size={13} />
          {state.skill_name} v{(state.brief.skill_version as string) ?? "0.1.0"}
        </div>
      </div>
      {state.failure_reason ? (
        <p className="mt-2 rounded-lg bg-white/50 p-2 text-xs text-[#991b1b]">
          {state.failure_reason}
        </p>
      ) : null}
    </section>
  );
}

function FinishedSummary({
  patientId,
  runId,
}: {
  patientId: string;
  runId: string;
  citations: Citation[];
}) {
  const outputQuery = useQuery({
    queryKey: ["skill-output", SKILL_NAME, runId, patientId],
    queryFn: () => skillsApi.getOutput(SKILL_NAME, runId, patientId),
    staleTime: Infinity,
  });

  const trials = useMemo(() => {
    const data = outputQuery.data as
      | { trials?: Array<Record<string, unknown>> }
      | undefined;
    return data?.trials ?? [];
  }, [outputQuery.data]);

  if (!trials.length) return <></>;

  return (
    <section className="rounded-2xl bg-white p-6 shadow-[rgb(224_226_232)_0px_0px_0px_1px]">
      <div className="mb-3 flex items-center justify-between">
        <h2 className="text-sm font-semibold text-[#1c1c1e]">Shortlist</h2>
        <span className="text-[11px] text-[#a5a8b5]">
          {trials.length} surviving · sorted by fit
        </span>
      </div>
      <ul className="space-y-2">
        {trials
          .slice()
          .sort((a, b) => Number(b.fit_score ?? 0) - Number(a.fit_score ?? 0))
          .map((trial) => {
            const nctId = String(trial.nct_id ?? "");
            const score = Number(trial.fit_score ?? 0);
            return (
              <li
                key={nctId}
                className="rounded-xl border border-[#e9eaef] p-3"
              >
                <div className="flex items-center justify-between gap-3">
                  <div className="min-w-0">
                    <p className="font-mono text-[10px] text-[#5b76fe]">{nctId}</p>
                    <p className="mt-0.5 text-sm font-semibold text-[#1c1c1e]">
                      {String(trial.title ?? "")}
                    </p>
                    <p className="mt-0.5 text-[11px] text-[#555a6a]">
                      {String(trial.sponsor ?? "")} · {String(trial.status ?? "")}
                    </p>
                  </div>
                  <div className="flex shrink-0 flex-col items-end gap-1">
                    <span
                      className="rounded-full bg-[#eef1ff] px-2.5 py-0.5 text-[11px] font-semibold text-[#3a4ca8]"
                    >
                      fit {score}
                    </span>
                    <span className="text-[10px] text-[#a5a8b5]">
                      {String(trial.evidence_tier ?? "")}
                    </span>
                  </div>
                </div>
              </li>
            );
          })}
      </ul>
    </section>
  );
}

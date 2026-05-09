import { useMemo, useState, type CSSProperties, type ReactNode } from "react";
import { useSearchParams } from "react-router-dom";
import {
  useMutation,
  useQuery,
  useQueryClient,
} from "@tanstack/react-query";
import {
  ArrowRight,
  Beaker,
  BookOpen,
  Bot,
  ChevronLeft,
  ChevronRight,
  Code2,
  Database,
  Eye,
  FileText,
  History,
  Info,
  Loader2,
  Maximize2,
  MessageSquareText,
  Minimize2,
  PanelRight,
  Save,
  Search,
  Settings2,
  ShieldCheck,
  Sparkles,
  Target,
  Wrench,
  X,
  UserRound,
} from "lucide-react";
import type { LucideIcon } from "lucide-react";
import { api } from "../../../api/client";
import { skillsApi } from "../../../api/skills";
import { EmptyState } from "../../../components/EmptyState";
import type {
  CanvasNode,
  Citation,
  PendingEscalation,
  RunMessage,
  RunInspectorResponse,
  RunStateResponse,
  SaveRequest,
  TrialPursuit,
  TrialPursuitStatus,
} from "../../../types/skills";

import { BriefPanel, type AnchorChoice } from "./components/BriefPanel";
import { EscalationBanner } from "./components/EscalationBanner";
import { PatientMemoryPanel } from "./components/PatientMemoryPanel";
import { RunHistorySidebar } from "./components/RunHistorySidebar";
import { SaveDestinationDrawer } from "./components/SaveDestinationDrawer";
import { TranscriptPane } from "./components/TranscriptPane";
import { WorkspacePane } from "./components/WorkspacePane";
import { useRunEvents } from "./hooks/useRunEvents";

const SKILL_NAME = "trial-matching";

const TRIAL_SOURCE_STACK = [
  {
    label: "Primary registries",
    body: "ClinicalTrials.gov first, then NCI for oncology and other official registries as the connector set grows.",
    url: "clinicaltrials.gov",
  },
  {
    label: "Global registry layer",
    body: "WHO ICTRP, EU CTIS, ISRCTN, ANZCTR, jRCT, UMIN, and related registry feeds where available.",
    url: "who.int / euclinicaltrials.eu / registry feeds",
  },
  {
    label: "Context sources",
    body: "Sponsor pages, academic medical-center listings, disease foundations, PubMed-linked NCT publications, and coordinator pages.",
    url: "sponsor, center, foundation, PubMed, site pages",
  },
];

const TRIAL_MATCH_DIMENSIONS = [
  {
    label: "Clinical fit",
    body: "Disease state, stage/severity, biomarkers, age, sex, comorbidities, labs, prior treatments, and exclusion criteria.",
  },
  {
    label: "Operational fit",
    body: "Recruiting status, geography, visit burden, duration, procedure burden, remote options, and patient effort required.",
  },
  {
    label: "Pursuit fit",
    body: "Enrollment size, site responsiveness, document needs, sponsor/site contactability, packet readiness, and follow-up risk.",
  },
];

const WORKSPACE_SURFACES = [
  {
    label: "Chat",
    body: "Intent, steering, clarifying questions, and agent narration. This is where the clinician tells the agent what trial pursuit means for this patient.",
  },
  {
    label: "Canvas",
    body: "Resizable object space for criteria, anchors, candidate trials, selected trials, packet tasks, and generated artifacts.",
  },
  {
    label: "Agent Inspector",
    body: "Transparency window for the skill file, assembled prompt, declared tools, source permissions, context, transcript, and artifacts.",
  },
  {
    label: "Pursuit Board",
    body: "Management surface backed by durable patient data for interested trials, packet prep, contacted sites, submissions, follow-up, and closure.",
  },
];

const CANVAS_OBJECTS = [
  ["Criteria", "Search constraints, geography, phase, status, exclusions, and clinician preferences."],
  ["Chart anchors", "Patient conditions or facts used as clinical search seeds."],
  ["Candidate trials", "Found trials with registry metadata and preliminary fit signals."],
  ["Selected trials", "Clinician-promoted candidates for deeper review."],
  ["Packet tasks", "Concrete work items required before outreach or submission."],
  ["Artifacts", "Generated summaries, packets, or saved structured outputs."],
];

interface ChatTurn {
  id: string;
  role: "user" | "agent";
  text: string;
}

/**
 * Trial Finder — net-new agentic-workspace module.
 *
 * Mounts at `/skills/trial-finder`. Two states share one route:
 * - Landing: chat-first intake with an adjustable right-side anchor canvas.
 *   Starting the search navigates with `?run=`.
 * - Run view: workspace.md + escalation banner + steering chat + transcript.
 *   Polls while the run is in-flight and uses SSE for live event updates.
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
    mutationFn: ({
      anchors,
      guidance,
    }: {
      anchors: AnchorChoice[];
      guidance: string;
    }) =>
      skillsApi.startRun(SKILL_NAME, {
        patient_id: patientId,
        brief: {
          anchors: anchors.map((a) => ({
            display: a.display,
            resource_id: a.resource_id,
            risk_category: a.risk_category,
            clinical_status: a.clinical_status,
          })),
          trial_guidance: guidance.trim(),
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
  const ranked = useMemo(
    () => acuityQuery.data?.ranked_active ?? [],
    [acuityQuery.data?.ranked_active],
  );
  const eligibleAnchors = useMemo(
    () => ranked.filter((condition) => condition.is_active && condition.risk_category !== "OTHER"),
    [ranked],
  );
  const defaultSelectedIds = useMemo(
    () => new Set(eligibleAnchors.slice(0, 3).map((condition) => condition.condition_id)),
    [eligibleAnchors],
  );
  const [selection, setSelection] = useState<{ patientId: string; ids: Set<string> | null }>({
    patientId,
    ids: null,
  });
  const [guideOpen, setGuideOpen] = useState(false);
  const [canvasOpen, setCanvasOpen] = useState(true);
  const [canvasWidth, setCanvasWidth] = useState(430);
  const [draftMessage, setDraftMessage] = useState("");
  const [trialGuidance, setTrialGuidance] = useState("");
  const [chatTurns, setChatTurns] = useState<ChatTurn[]>([]);
  const selectedIds = selection.patientId === patientId && selection.ids !== null ? selection.ids : defaultSelectedIds;
  const setSelectedIds = (ids: Set<string>) => setSelection({ patientId, ids });

  const anchorPayload: AnchorChoice[] = useMemo(
    () =>
      Array.from(selectedIds).flatMap((id) => {
        const condition = ranked.find((item) => item.condition_id === id);
        if (!condition) return [];
        return [
          {
            resource_id: condition.condition_id,
            display: condition.display,
            risk_category: condition.risk_category,
            clinical_status: condition.clinical_status,
          },
        ];
      }),
    [ranked, selectedIds],
  );
  const latestRun = runsQuery.data?.[0] ?? null;
  const workspaceStyle = canvasOpen
    ? ({ "--canvas-width": `${canvasWidth}px` } as CSSProperties)
    : undefined;

  function startFromChat() {
    if (!anchorPayload.length || start.isPending) return;
    start.mutate({ anchors: anchorPayload, guidance: trialGuidance });
  }

  function submitChatMessage() {
    const text = draftMessage.trim();
    if (!text) return;
    setDraftMessage("");
    setTrialGuidance((current) => [current, text].filter(Boolean).join("\n\n"));
    setChatTurns((current) => [
      ...current,
      { id: `u-${Date.now()}`, role: "user", text },
      {
        id: `a-${Date.now()}`,
        role: "agent",
        text: "Got it. I will use that as trial-search guidance when I start the run. You can add more guidance or adjust the canvas anchors before searching.",
      },
    ]);
  }

  function applyPrompt(text: string) {
    setDraftMessage(text);
  }

  return (
    <div
      className={`mx-auto grid max-w-7xl gap-6 px-5 py-6 ${
        canvasOpen
          ? "grid-cols-1 xl:[grid-template-columns:minmax(0,1fr)_var(--canvas-width)]"
          : "grid-cols-1"
      }`}
      style={workspaceStyle}
    >
      <div className="space-y-5">
        <section className="rounded-2xl bg-white p-0 shadow-[rgb(224_226_232)_0px_0px_0px_1px]">
          <div className="border-b border-[#eef0f5] px-5 py-4">
            <div className="flex items-center gap-2">
              <MessageSquareText size={16} className="text-[#5b76fe]" />
              <div>
                <h1 className="text-sm font-semibold text-[#1c1c1e]">Trial Finder agent</h1>
                <p className="text-[11px] text-[#8d92a3]">{patientName}</p>
              </div>
              <div className="ml-auto flex items-center gap-2">
                {!canvasOpen ? (
                  <button
                    type="button"
                    onClick={() => setCanvasOpen(true)}
                    className="inline-flex items-center gap-1.5 rounded-lg bg-[#eef1ff] px-2.5 py-1.5 text-[11px] font-semibold text-[#5b76fe]"
                  >
                    <PanelRight size={13} />
                    Show canvas
                  </button>
                ) : null}
                <button
                  type="button"
                  onClick={() => setGuideOpen(true)}
                  className="inline-flex h-8 w-8 items-center justify-center rounded-lg bg-white text-[#667085] shadow-[rgb(224_226_232)_0px_0px_0px_1px] hover:bg-[#f7f8ff] hover:text-[#5b76fe]"
                  title="Open workspace guide"
                >
                  <Info size={15} />
                </button>
              </div>
            </div>
          </div>
          <div className="space-y-4 p-5">
            <div className="flex items-start gap-3">
              <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-[#eef1ff] text-[#5b76fe]">
                <Bot size={18} />
              </div>
              <div className="max-w-3xl rounded-2xl rounded-tl-md bg-[#f7f8ff] px-4 py-3 shadow-[rgb(224_226_232)_0px_0px_0px_1px]">
                <p className="text-sm leading-6 text-[#1c1c1e]">
                  What sort of clinical trials are you interested in for this patient? Tell me the disease area,
                  intervention type, geography, trial phase, or any constraints from the clinician or patient.
                </p>
                <p className="mt-2 text-sm leading-6 text-[#555a6a]">
                  I found {eligibleAnchors.length} possible chart anchors and preselected {selectedIds.size || Math.min(3, eligibleAnchors.length)}.
                  You can adjust those in the canvas, or just describe what you want and I will translate it into search criteria.
                </p>
              </div>
            </div>

            <div className="ml-12 grid gap-3 md:grid-cols-2 xl:grid-cols-4">
              {[
                {
                  icon: Target,
                  title: "Disease focus",
                  body: "Cancer, cardiac, metabolic, rare disease, or any named diagnosis.",
                  prompt: "Focus on trials related to ",
                },
                {
                  icon: Search,
                  title: "Search constraints",
                  body: "Recruiting only, geography, phase, age band, sponsor, or intervention.",
                  prompt: "Search recruiting trials within 100 miles. Prefer phase ",
                },
                {
                  icon: PanelRight,
                  title: "Canvas anchors",
                  body: "Chart-derived conditions the search can use or ignore.",
                  prompt: "Use the selected chart anchors, but ignore ",
                },
                {
                  icon: FileText,
                  title: "Packet goal",
                  body: "Shortlist only, deeper trial review, or outreach packet preparation.",
                  prompt: "Create a shortlist first, then prepare an outreach packet for ",
                },
              ].map((item) => {
                const Icon = item.icon;
                return (
                  <button
                    key={item.title}
                    type="button"
                    onClick={() => applyPrompt(item.prompt)}
                    className="rounded-xl border border-[#e9eaef] bg-white p-3 text-left hover:border-[#c7d1ff] hover:bg-[#fbfcff]"
                  >
                    <div className="flex items-center gap-2">
                      <Icon size={14} className="text-[#5b76fe]" />
                      <p className="text-xs font-semibold text-[#1c1c1e]">{item.title}</p>
                    </div>
                    <p className="mt-1.5 text-[11px] leading-4 text-[#667085]">{item.body}</p>
                  </button>
                );
              })}
            </div>

            {chatTurns.length ? (
              <div className="ml-12 space-y-3">
                {chatTurns.map((turn) => (
                  <div
                    key={turn.id}
                    className={`max-w-3xl rounded-2xl px-4 py-3 text-sm leading-6 shadow-[rgb(224_226_232)_0px_0px_0px_1px] ${
                      turn.role === "user"
                        ? "ml-auto rounded-tr-md bg-[#1c1c1e] text-white"
                        : "rounded-tl-md bg-[#f7f8ff] text-[#1c1c1e]"
                    }`}
                  >
                    {turn.text}
                  </div>
                ))}
              </div>
            ) : null}

            {latestRun ? (
              <div className="ml-12 rounded-xl border border-[#e9eaef] bg-[#fafbff] p-3">
                <div className="flex items-center gap-2">
                  <Sparkles size={14} className="text-[#187574]" />
                  <p className="text-xs font-semibold text-[#1c1c1e]">Previous workspace found</p>
                </div>
                <p className="mt-1.5 text-[11px] leading-4 text-[#667085]">
                  Last run is {latestRun.status}. You can resume it from Recent runs, or start a fresh search with the
                  current canvas selections.
                </p>
              </div>
            ) : null}

            <div className="ml-12 flex flex-wrap gap-2">
              <button
                type="button"
                onClick={startFromChat}
                disabled={!anchorPayload.length || start.isPending}
                className="inline-flex items-center gap-2 rounded-xl bg-[#5b76fe] px-4 py-2.5 text-sm font-semibold text-white transition-colors hover:bg-[#4a63dc] disabled:cursor-not-allowed disabled:opacity-60"
              >
                <Target size={16} />
                {start.isPending ? "Starting search..." : "Search trials with canvas anchors"}
              </button>
              {!canvasOpen ? (
                <button
                  type="button"
                  onClick={() => setCanvasOpen(true)}
                  className="inline-flex items-center gap-1.5 rounded-xl bg-white px-4 py-2.5 text-sm font-semibold text-[#5b76fe] shadow-[rgb(224_226_232)_0px_0px_0px_1px] hover:bg-[#f7f8ff]"
                >
                  Open anchor canvas
                  <ArrowRight size={14} />
                </button>
              ) : null}
            </div>

            <div className="ml-12 rounded-2xl border border-[#e9eaef] bg-white p-3">
              <textarea
                value={draftMessage}
                onChange={(event) => setDraftMessage(event.target.value)}
                onKeyDown={(event) => {
                  if ((event.metaKey || event.ctrlKey) && event.key === "Enter") {
                    event.preventDefault();
                    submitChatMessage();
                  }
                }}
                placeholder="Describe the trials you want: disease area, geography, phase, intervention, exclusions, or packet goal..."
                className="min-h-24 w-full resize-y bg-transparent text-sm leading-6 text-[#1c1c1e] outline-none placeholder:text-[#a5a8b5]"
              />
              <div className="mt-2 flex items-center justify-between gap-3">
                <p className="text-[11px] text-[#8d92a3]">Press Cmd+Enter to add guidance.</p>
                <button
                  type="button"
                  onClick={submitChatMessage}
                  disabled={!draftMessage.trim()}
                  className="rounded-lg bg-[#1c1c1e] px-3 py-2 text-xs font-semibold text-white hover:bg-[#333438] disabled:cursor-not-allowed disabled:opacity-50"
                >
                  Add guidance
                </button>
              </div>
            </div>
          </div>
        </section>
      </div>

      {canvasOpen ? (
      <div id="trial-anchor-canvas" className="space-y-4">
        <section className="sticky top-3 z-10 rounded-2xl bg-white p-3 shadow-[rgb(224_226_232)_0px_0px_0px_1px]">
          <div className="flex items-center gap-2">
            <PanelRight size={15} className="text-[#5b76fe]" />
            <div>
              <p className="text-sm font-semibold text-[#1c1c1e]">Canvas</p>
              <p className="text-[11px] text-[#8d92a3]">Criteria and chart anchors</p>
            </div>
            <div className="ml-auto flex items-center gap-1">
              <button
                type="button"
                onClick={() => setCanvasWidth((current) => Math.max(340, current - 60))}
                className="inline-flex h-8 w-8 items-center justify-center rounded-lg text-[#667085] hover:bg-[#f7f8ff] hover:text-[#5b76fe]"
                title="Narrow canvas"
              >
                <ChevronRight size={15} />
              </button>
              <label className="mx-1 hidden items-center gap-2 md:flex">
                <span className="text-[10px] font-semibold uppercase tracking-wider text-[#8d92a3]">Width</span>
                <input
                  type="range"
                  min={340}
                  max={720}
                  step={10}
                  value={canvasWidth}
                  onChange={(event) => setCanvasWidth(Number(event.target.value))}
                  className="w-28 accent-[#5b76fe]"
                />
              </label>
              <button
                type="button"
                onClick={() => setCanvasWidth((current) => Math.min(720, current + 60))}
                className="inline-flex h-8 w-8 items-center justify-center rounded-lg text-[#667085] hover:bg-[#f7f8ff] hover:text-[#5b76fe]"
                title="Widen canvas"
              >
                <ChevronLeft size={15} />
              </button>
              <button
                type="button"
                onClick={() => setCanvasOpen(false)}
                className="inline-flex h-8 w-8 items-center justify-center rounded-lg text-[#667085] hover:bg-[#f7f8ff] hover:text-[#5b76fe]"
                title="Hide canvas"
              >
                <Minimize2 size={15} />
              </button>
            </div>
          </div>
        </section>

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
            onStart={(anchors) => start.mutate({ anchors, guidance: trialGuidance })}
            selectedIds={selectedIds}
            onSelectedIdsChange={setSelectedIds}
            showHero={false}
            showTrustContract={false}
            showStartButton={false}
          />
        )}

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
      ) : null}

      <WorkspaceGuideModal
        open={guideOpen}
        onClose={() => setGuideOpen(false)}
      />
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
  const [canvasOpen, setCanvasOpen] = useState(true);
  const [canvasWidth, setCanvasWidth] = useState(480);
  const [steeringDraft, setSteeringDraft] = useState("");
  const [guideOpen, setGuideOpen] = useState(false);
  const [inspectorOpen, setInspectorOpen] = useState(false);
  const [inspectorExpanded, setInspectorExpanded] = useState(false);

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
    // Polled at a relaxed cadence; SSE events of kind `workspace_write`
    // and `cite` invalidate this query for sub-second updates.
    refetchInterval: 5000,
    enabled: !!stateQuery.data,
  });

  // Live event feed via SSE — replaces the previous transcript polling.
  // Workspace markdown updates ride on top: when a relevant event lands,
  // the workspace query is invalidated so the rendered artifact tracks
  // the agent's writes in near-real-time.
  const liveEvents = useRunEvents({
    skillName: SKILL_NAME,
    runId,
    patientId,
    onEvent: (event) => {
      if (event.kind === "workspace_write" || event.kind === "cite") {
        queryClient.invalidateQueries({
          queryKey: ["skill-workspace", SKILL_NAME, runId, patientId],
        });
      }
      if (
        event.kind === "escalation" ||
        event.kind === "escalation_resolved" ||
        event.kind === "message_added" ||
        event.kind === "message_consumed" ||
        event.kind === "canvas_node_upserted" ||
        event.kind === "canvas_selection_changed" ||
        event.kind === "run_finished" ||
        event.kind === "run_failed" ||
        event.kind === "finalize_failed"
      ) {
        queryClient.invalidateQueries({
          queryKey: ["skill-run", SKILL_NAME, runId, patientId],
        });
      }
      if (event.kind === "message_added" || event.kind === "message_consumed") {
        queryClient.invalidateQueries({
          queryKey: ["skill-messages", SKILL_NAME, runId, patientId],
        });
      }
      if (event.kind === "canvas_node_upserted" || event.kind === "canvas_selection_changed") {
        queryClient.invalidateQueries({
          queryKey: ["skill-canvas", SKILL_NAME, runId, patientId],
        });
      }
      if (inspectorOpen) {
        queryClient.invalidateQueries({
          queryKey: ["skill-inspector", SKILL_NAME, runId, patientId],
        });
      }
    },
  });

  const runsQuery = useQuery({
    queryKey: ["skill-runs", patientId, SKILL_NAME],
    queryFn: () => skillsApi.listPatientRuns(patientId, SKILL_NAME),
    refetchOnWindowFocus: false,
  });

  const messagesQuery = useQuery({
    queryKey: ["skill-messages", SKILL_NAME, runId, patientId],
    queryFn: () => skillsApi.getMessages(SKILL_NAME, runId, patientId),
    refetchOnWindowFocus: false,
  });

  const canvasQuery = useQuery({
    queryKey: ["skill-canvas", SKILL_NAME, runId, patientId],
    queryFn: () => skillsApi.getCanvas(SKILL_NAME, runId, patientId),
    refetchOnWindowFocus: false,
  });

  const pursuitsQuery = useQuery({
    queryKey: ["trial-pursuits", patientId],
    queryFn: () => skillsApi.listTrialPursuits(patientId),
    refetchOnWindowFocus: false,
  });

  const inspectorQuery = useQuery({
    queryKey: ["skill-inspector", SKILL_NAME, runId, patientId],
    queryFn: () => skillsApi.getInspector(SKILL_NAME, runId, patientId),
    enabled: inspectorOpen,
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
        queryKey: ["skill-run", SKILL_NAME, runId, patientId],
      });
    },
  });

  const save = useMutation({
    mutationFn: (payload: SaveRequest) =>
      skillsApi.saveRun(SKILL_NAME, runId, patientId, payload),
    onSuccess: () => {
      setDrawerOpen(false);
      // The save event itself rides the SSE stream — no need to invalidate
      // a transcript query (we no longer have one). The run-list and
      // patient-memory caches still need a manual nudge.
      queryClient.invalidateQueries({
        queryKey: ["skill-runs", patientId, SKILL_NAME],
      });
      queryClient.invalidateQueries({
        queryKey: ["skill-patient-memory", patientId],
      });
    },
  });

  const sendSteering = useMutation({
    mutationFn: (message: string) =>
      skillsApi.addMessage(SKILL_NAME, runId, patientId, {
        actor: "clinician",
        message,
      }),
    onSuccess: () => {
      setSteeringDraft("");
      queryClient.invalidateQueries({
        queryKey: ["skill-messages", SKILL_NAME, runId, patientId],
      });
    },
  });

  const selectCanvasNode = useMutation({
    mutationFn: async ({
      node,
      selected,
    }: {
      node: CanvasNode;
      selected: boolean;
    }) => {
      const updated = await skillsApi.setCanvasNodeSelection(
        SKILL_NAME,
        runId,
        patientId,
        node.node_id,
        selected
      );
      const action = selected ? "Do a deeper dive on" : "Remove from consideration";
      await skillsApi.addMessage(SKILL_NAME, runId, patientId, {
        actor: "clinician",
        message: `${action} ${node.title}.`,
        canvas_ref: {
          node_id: node.node_id,
          kind: node.kind,
          selected,
          data: node.data,
        },
      });
      return updated;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({
        queryKey: ["skill-canvas", SKILL_NAME, runId, patientId],
      });
      queryClient.invalidateQueries({
        queryKey: ["skill-messages", SKILL_NAME, runId, patientId],
      });
    },
  });

  const trackTrial = useMutation({
    mutationFn: (node: CanvasNode) =>
      skillsApi.upsertTrialPursuit(patientId, {
        ...pursuitPayloadFromCanvasNode(node, runId),
        actor: "clinician",
      }),
    onSuccess: (pursuit) => {
      queryClient.invalidateQueries({ queryKey: ["trial-pursuits", patientId] });
      void skillsApi.addMessage(SKILL_NAME, runId, patientId, {
        actor: "clinician",
        message: `Track ${pursuit.nct_id} as a trial pursuit.`,
        canvas_ref: {
          kind: "trial_pursuit",
          pursuit_id: pursuit.pursuit_id,
          nct_id: pursuit.nct_id,
        },
      });
    },
  });

  const updatePursuit = useMutation({
    mutationFn: ({
      pursuit,
      status,
    }: {
      pursuit: TrialPursuit;
      status: TrialPursuitStatus;
    }) =>
      skillsApi.updateTrialPursuit(patientId, pursuit.pursuit_id, {
        status,
        next_step: nextStepForStatus(status),
        event_note: `Moved ${pursuit.nct_id} to ${pursuitStatusLabel(status)}.`,
        actor: "clinician",
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["trial-pursuits", patientId] });
    },
  });

  const addPursuitTask = useMutation({
    mutationFn: (pursuit: TrialPursuit) =>
      skillsApi.addTrialPursuitTask(patientId, pursuit.pursuit_id, {
        title: defaultTaskForStatus(pursuit.status),
        actor: "clinician",
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["trial-pursuits", patientId] });
    },
  });

  const state = stateQuery.data;
  const workspace = workspaceQuery.data;
  const canvas = canvasQuery.data;
  const transcriptEvents = liveEvents.events;
  const pursuits = useMemo(
    () => pursuitsQuery.data?.pursuits ?? [],
    [pursuitsQuery.data?.pursuits],
  );
  const trackedNctIds = useMemo(
    () => new Set(pursuits.map((pursuit) => pursuit.nct_id)),
    [pursuits],
  );

  const pendingEscalation: PendingEscalation | null =
    state?.pending_escalations[0] ?? null;

  const finished = state?.status === "finished" || state?.status === "failed";
  const runStyle = canvasOpen
    ? ({ "--canvas-width": `${canvasWidth}px` } as CSSProperties)
    : undefined;
  const sendCurrentSteering = async () => {
    const text = steeringDraft.trim();
    if (!text || sendSteering.isPending) return;
    await sendSteering.mutateAsync(text);
  };

  return (
    <div
      className={`mx-auto grid max-w-7xl gap-5 px-5 py-5 ${
        canvasOpen
          ? "grid-cols-1 xl:[grid-template-columns:minmax(0,1fr)_var(--canvas-width)]"
          : "grid-cols-1"
      }`}
      style={runStyle}
    >
      <RunChatPane
        state={state}
        events={transcriptEvents}
        messages={messagesQuery.data?.messages ?? []}
        draft={steeringDraft}
        isSending={sendSteering.isPending}
        pendingEscalation={pendingEscalation}
        onDraftChange={setSteeringDraft}
        onSend={sendCurrentSteering}
        onShowCanvas={() => setCanvasOpen(true)}
        onOpenGuide={() => setGuideOpen(true)}
        canvasOpen={canvasOpen}
        onResolveEscalation={async (choice, notes) => {
          if (!pendingEscalation) return;
          await resolve.mutateAsync({
            approvalId: pendingEscalation.approval_id,
            choice,
            notes,
          });
        }}
        isResolving={resolve.isPending}
      />

      {canvasOpen ? (
        <aside className="space-y-4">
          <section className="sticky top-3 z-10 rounded-2xl bg-white p-3 shadow-[rgb(224_226_232)_0px_0px_0px_1px]">
            <div className="flex items-center gap-2">
              <PanelRight size={15} className="text-[#5b76fe]" />
              <div>
                <p className="text-sm font-semibold text-[#1c1c1e]">Run canvas</p>
                <p className="text-[11px] text-[#8d92a3]">Criteria, results, artifacts</p>
              </div>
              <div className="ml-auto flex items-center gap-1">
                <button
                  type="button"
                  onClick={() => setGuideOpen(true)}
                  className="inline-flex h-8 w-8 items-center justify-center rounded-lg text-[#667085] hover:bg-[#f7f8ff] hover:text-[#5b76fe]"
                  title="Open workspace guide"
                >
                  <Info size={15} />
                </button>
                <button
                  type="button"
                  onClick={() => setInspectorOpen(true)}
                  className="inline-flex h-8 w-8 items-center justify-center rounded-lg text-[#667085] hover:bg-[#f7f8ff] hover:text-[#5b76fe]"
                  title="Open agent inspector"
                >
                  <Eye size={15} />
                </button>
                <button
                  type="button"
                  onClick={() => setCanvasWidth((current) => Math.max(360, current - 60))}
                  className="inline-flex h-8 w-8 items-center justify-center rounded-lg text-[#667085] hover:bg-[#f7f8ff] hover:text-[#5b76fe]"
                  title="Narrow canvas"
                >
                  <ChevronRight size={15} />
                </button>
                <input
                  type="range"
                  min={360}
                  max={760}
                  step={10}
                  value={canvasWidth}
                  onChange={(event) => setCanvasWidth(Number(event.target.value))}
                  className="hidden w-24 accent-[#5b76fe] md:block"
                />
                <button
                  type="button"
                  onClick={() => setCanvasWidth((current) => Math.min(760, current + 60))}
                  className="inline-flex h-8 w-8 items-center justify-center rounded-lg text-[#667085] hover:bg-[#f7f8ff] hover:text-[#5b76fe]"
                  title="Widen canvas"
                >
                  <ChevronLeft size={15} />
                </button>
                <button
                  type="button"
                  onClick={() => setCanvasOpen(false)}
                  className="inline-flex h-8 w-8 items-center justify-center rounded-lg text-[#667085] hover:bg-[#f7f8ff] hover:text-[#5b76fe]"
                  title="Hide canvas"
                >
                  <Minimize2 size={15} />
                </button>
              </div>
            </div>
          </section>

          {state ? (
            <RunCanvasSummary
              state={state}
              canvasNodes={canvas?.nodes ?? []}
              trackedNctIds={trackedNctIds}
              onToggleNode={(node, selected) =>
                selectCanvasNode.mutate({ node, selected })
              }
              onTrackNode={(node) => trackTrial.mutate(node)}
              isUpdatingSelection={selectCanvasNode.isPending}
              isTracking={trackTrial.isPending}
            />
          ) : null}

          <TrialPursuitBoard
            pursuits={pursuits}
            isLoading={pursuitsQuery.isLoading}
            isUpdating={updatePursuit.isPending || addPursuitTask.isPending}
            onMove={(pursuit, status) => updatePursuit.mutate({ pursuit, status })}
            onAddTask={(pursuit) => addPursuitTask.mutate(pursuit)}
          />

          {finished && state?.status === "finished" ? (
            <FinishedSummary
              patientId={patientId}
              runId={runId}
              citations={workspace?.citations ?? []}
            />
          ) : null}

          <PatientMemoryPanel
            patientId={patientId}
            detailHref={`/skills/patients/memory?patient=${encodeURIComponent(
              patientId
            )}`}
          />

          <RunDebugPanels
            workspace={workspace}
            events={transcriptEvents}
            connection={liveEvents.streamClosed ? "closed" : liveEvents.connection}
            finished={finished}
            onSave={() => setDrawerOpen(true)}
          />

          <RunHistorySidebar
            patientId={patientId}
            runs={runsQuery.data ?? []}
            activeRunId={runId}
          />
        </aside>
      ) : null}

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

      <RunInspectorSuite
        open={inspectorOpen}
        expanded={inspectorExpanded}
        data={inspectorQuery.data}
        isLoading={inspectorQuery.isLoading}
        onClose={() => setInspectorOpen(false)}
        onToggleExpanded={() => setInspectorExpanded((current) => !current)}
      />
      <WorkspaceGuideModal
        open={guideOpen}
        onClose={() => setGuideOpen(false)}
        onOpenInspector={() => {
          setGuideOpen(false);
          setInspectorOpen(true);
        }}
      />
    </div>
  );
}

// ── Bits ───────────────────────────────────────────────────────────────────

function RunChatPane({
  state,
  events,
  messages,
  draft,
  isSending,
  pendingEscalation,
  onDraftChange,
  onSend,
  onShowCanvas,
  onOpenGuide,
  canvasOpen,
  onResolveEscalation,
  isResolving,
}: {
  state: RunStateResponse | undefined;
  events: Array<{ kind: string; at: string; text?: string; reason?: string; tool?: string; result_preview?: string; message?: string }>;
  messages: RunMessage[];
  draft: string;
  isSending: boolean;
  pendingEscalation: PendingEscalation | null;
  onDraftChange: (value: string) => void;
  onSend: () => Promise<void>;
  onShowCanvas: () => void;
  onOpenGuide: () => void;
  canvasOpen: boolean;
  onResolveEscalation: (choice: string, notes: string) => Promise<void>;
  isResolving: boolean;
}) {
  const agentEvents = events.filter((event) =>
    [
      "agent_text",
      "agent_tool_result",
      "agent_tool_error",
      "run_finished",
      "agent_run_started",
      "message_consumed",
    ].includes(event.kind)
  );
  const statusCopy = state
    ? {
        created: "Starting",
        running: "Working",
        escalated: "Needs your decision",
        validated: "Validated",
        finished: "Complete",
        failed: "Needs setup",
      }[state.status]
    : "Connecting";

  return (
    <section className="flex min-h-[calc(100vh-13rem)] flex-col rounded-2xl bg-white shadow-[rgb(224_226_232)_0px_0px_0px_1px]">
      <div className="border-b border-[#eef0f5] px-5 py-4">
        <div className="flex items-center gap-2">
          <MessageSquareText size={16} className="text-[#5b76fe]" />
          <div>
            <h2 className="text-sm font-semibold text-[#1c1c1e]">Trial Finder agent</h2>
            <p className="text-[11px] text-[#8d92a3]">{statusCopy} · run {state?.run_id ?? "starting"}</p>
          </div>
          <button
            type="button"
            onClick={onOpenGuide}
            className="ml-auto inline-flex h-8 w-8 items-center justify-center rounded-lg text-[#667085] hover:bg-[#f7f8ff] hover:text-[#5b76fe]"
            title="Open workspace guide"
          >
            <Info size={15} />
          </button>
          {!canvasOpen ? (
            <button
              type="button"
              onClick={onShowCanvas}
              className="inline-flex items-center gap-1.5 rounded-lg bg-[#eef1ff] px-2.5 py-1.5 text-[11px] font-semibold text-[#5b76fe]"
            >
              <PanelRight size={13} />
              Show canvas
            </button>
          ) : null}
        </div>
      </div>

      <div className="flex-1 space-y-4 overflow-y-auto p-5">
        <AgentBubble>
          I am going to search clinical trials from the selected chart anchors, compare the trial criteria against the
          patient context, and keep the canvas updated with criteria, candidates, and next actions. Tell me if you want
          geography, phase, sponsor, intervention, or packet constraints applied.
        </AgentBubble>

        {state?.status === "failed" ? (
          <AgentBubble tone="error">
            The agent run did not start correctly. {state.failure_reason ? humanizeFailure(state.failure_reason) : "The run stopped before producing a result."}
          </AgentBubble>
        ) : null}

        {pendingEscalation ? (
          <div className="rounded-2xl border border-[#f7d58a] bg-[#fffbeb] p-3">
            <EscalationBanner
              escalation={pendingEscalation}
              isResolving={isResolving}
              onResolve={onResolveEscalation}
            />
          </div>
        ) : null}

        {messages.length ? (
          messages.map((message) => (
            <div
              key={message.message_id}
              className="ml-auto max-w-[82%] rounded-2xl rounded-tr-md bg-[#1c1c1e] px-4 py-3 text-sm leading-6 text-white"
            >
              <p>{message.message}</p>
              <p className="mt-1 text-[10px] text-white/55">{message.consumed ? "read by agent" : "queued"}</p>
            </div>
          ))
        ) : null}

        {agentEvents.map((event, index) => (
          <AgentEventBubble key={`${event.at}-${event.kind}-${index}`} event={event} />
        ))}

        {!agentEvents.length && state?.status === "running" ? (
          <AgentBubble muted>
            Waiting for the first agent update. The run is connected; tool calls and results will appear here as they
            stream in.
          </AgentBubble>
        ) : null}
      </div>

      <div className="border-t border-[#eef0f5] p-4">
        <div className="rounded-2xl border border-[#dfe3ee] bg-white p-3">
        <textarea
          value={draft}
          onChange={(event) => onDraftChange(event.target.value)}
          onKeyDown={(event) => {
            if ((event.metaKey || event.ctrlKey) && event.key === "Enter") {
              event.preventDefault();
              void onSend();
            }
          }}
          placeholder="Message the agent: include Boston, ignore obesity, deeper dive on NCT..., prepare a packet for..."
          className="min-h-24 w-full resize-y bg-transparent text-sm leading-6 text-[#1c1c1e] outline-none placeholder:text-[#a5a8b5]"
        />
        <div className="mt-2 flex items-center justify-between gap-2">
          <span className="text-[11px] text-[#8d92a3]">Cmd+Enter sends</span>
          <button
            type="button"
            onClick={() => void onSend()}
            disabled={!draft.trim() || isSending}
            className="rounded-lg bg-[#1c1c1e] px-4 py-2 text-xs font-semibold text-white hover:bg-[#333438] disabled:cursor-not-allowed disabled:opacity-50"
          >
            {isSending ? "Sending..." : "Send"}
          </button>
        </div>
        </div>
      </div>
    </section>
  );
}

function AgentBubble({
  children,
  muted = false,
  tone = "default",
}: {
  children: ReactNode;
  muted?: boolean;
  tone?: "default" | "error";
}) {
  return (
    <div
      className={`max-w-[86%] rounded-2xl rounded-tl-md px-4 py-3 text-sm leading-6 shadow-[rgb(224_226_232)_0px_0px_0px_1px] ${
        tone === "error"
          ? "bg-[#fef2f2] text-[#7f1d1d]"
          : muted
          ? "bg-[#fafbff] text-[#667085]"
          : "bg-[#f7f8ff] text-[#1c1c1e]"
      }`}
    >
      {children}
    </div>
  );
}

function AgentEventBubble({
  event,
}: {
  event: { kind: string; text?: string; reason?: string; tool?: string; result_preview?: string; message_id?: string };
}) {
  if (event.kind === "agent_text") return <AgentBubble>{event.text}</AgentBubble>;
  if (event.kind === "run_failed") return <AgentBubble tone="error">{humanizeFailure(event.reason ?? "Run failed.")}</AgentBubble>;
  if (event.kind === "run_finished") return <AgentBubble>The shortlist is ready in the canvas.</AgentBubble>;
  if (event.kind === "workspace_write") return <AgentBubble muted>I updated the workspace artifact.</AgentBubble>;
  if (event.kind === "message_consumed") return <AgentBubble muted>I read your latest steering message and will apply it on the next step.</AgentBubble>;
  if (event.kind === "agent_run_started") return <AgentBubble muted>Agent runtime connected. I am reading the brief and preparing tools.</AgentBubble>;
  if (event.kind === "agent_tool_error") return <AgentBubble tone="error">Tool error: {event.tool ?? "unknown tool"}</AgentBubble>;
  if (event.kind === "agent_tool_result") {
    return (
      <AgentBubble muted>
        Tool result: {event.tool ?? "tool"}
        {event.result_preview ? ` · ${event.result_preview}` : ""}
      </AgentBubble>
    );
  }
  return null;
}

type GuideTab = "overview" | "surfaces" | "sources" | "matching" | "management";

function WorkspaceGuideModal({
  open,
  onClose,
  onOpenInspector,
}: {
  open: boolean;
  onClose: () => void;
  onOpenInspector?: () => void;
}) {
  const [activeTab, setActiveTab] = useState<GuideTab>("overview");
  if (!open) return null;

  const tabs: Array<{ id: GuideTab; label: string; icon: LucideIcon }> = [
    { id: "overview", label: "Overview", icon: Info },
    { id: "surfaces", label: "Surfaces", icon: PanelRight },
    { id: "sources", label: "Sources", icon: Database },
    { id: "matching", label: "Matching", icon: Target },
    { id: "management", label: "Management", icon: FileText },
  ];

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-[#111827]/35 p-4 backdrop-blur-[1px]" onClick={onClose}>
      <section
        className="flex max-h-[88vh] w-full max-w-5xl flex-col overflow-hidden rounded-2xl bg-white shadow-2xl"
        onClick={(event) => event.stopPropagation()}
      >
        <header className="border-b border-[#eef0f5] px-5 py-4">
          <div className="flex items-center gap-3">
            <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-[#eef1ff] text-[#5b76fe]">
              <BookOpen size={18} />
            </div>
            <div className="min-w-0">
              <h2 className="text-lg font-semibold text-[#1c1c1e]">Trial Finder Workspace Guide</h2>
              <p className="mt-0.5 text-xs leading-5 text-[#667085]">
                A chat-led workspace with preconfigured micro-app surfaces for trial search, transparency, and pursuit management.
              </p>
            </div>
            <button
              type="button"
              onClick={onClose}
              className="ml-auto inline-flex h-8 w-8 items-center justify-center rounded-lg text-[#667085] hover:bg-[#f7f8ff] hover:text-[#5b76fe]"
              title="Close guide"
            >
              <X size={15} />
            </button>
          </div>
        </header>

        <div className="border-b border-[#eef0f5] px-4 py-2">
          <div className="flex gap-1 overflow-x-auto">
            {tabs.map((tab) => {
              const Icon = tab.icon;
              return (
                <button
                  key={tab.id}
                  type="button"
                  onClick={() => setActiveTab(tab.id)}
                  className={`inline-flex items-center gap-1.5 rounded-lg px-3 py-2 text-xs font-semibold ${
                    activeTab === tab.id
                      ? "bg-[#eef1ff] text-[#5b76fe]"
                      : "text-[#667085] hover:bg-[#f7f8ff] hover:text-[#1c1c1e]"
                  }`}
                >
                  <Icon size={13} />
                  {tab.label}
                </button>
              );
            })}
          </div>
        </div>

        <div className="flex-1 overflow-auto bg-[#f5f6f8] p-5">
          {activeTab === "overview" ? (
            <div className="grid gap-4 lg:grid-cols-[1.1fr_0.9fr]">
              <GuidePanel title="What this is" icon={MessageSquareText}>
                <p className="text-sm leading-6 text-[#555a6a]">
                  Trial Finder is a clinical-trial pursuit workspace. The chat captures intent and steering. The canvas
                  holds interactive objects. The inspector exposes the agent harness. The pursuit board persists trials
                  the clinician may actually pursue.
                </p>
                <p className="mt-3 text-sm leading-6 text-[#555a6a]">
                  Some panes are preconfigured micro-apps, not arbitrary generated HTML. The agent writes structured
                  canvas objects and durable pursuit records; React renders those objects into stable views.
                </p>
              </GuidePanel>
              <GuidePanel title="Core components" icon={PanelRight}>
                <GuideList items={WORKSPACE_SURFACES} />
              </GuidePanel>
            </div>
          ) : null}

          {activeTab === "surfaces" ? (
            <div className="grid gap-4 lg:grid-cols-2">
              <GuidePanel title="Canvas object model" icon={PanelRight}>
                <div className="space-y-2">
                  {CANVAS_OBJECTS.map(([label, body]) => (
                    <div key={label} className="rounded-xl border border-[#e9eaef] bg-white p-3">
                      <p className="text-xs font-semibold text-[#1c1c1e]">{label}</p>
                      <p className="mt-1 text-xs leading-5 text-[#667085]">{body}</p>
                    </div>
                  ))}
                </div>
              </GuidePanel>
              <GuidePanel title="Window behavior" icon={Maximize2}>
                <p className="text-sm leading-6 text-[#555a6a]">
                  The right side is a resizable workspace area. Canvas panes can collapse, widen, or expand into larger
                  inspection views. The goal is a Codex-like shell where chat remains the control surface and the right
                  side swaps between micro-app views.
                </p>
                <p className="mt-3 text-sm leading-6 text-[#555a6a]">
                  The inspector is the transparency window; the pursuit board is the clinical-trial management app; the
                  canvas summary is the active run state.
                </p>
              </GuidePanel>
            </div>
          ) : null}

          {activeTab === "sources" ? (
            <div className="grid gap-4 lg:grid-cols-3">
              {TRIAL_SOURCE_STACK.map((item) => (
                <GuidePanel key={item.label} title={item.label} icon={Database}>
                  <p className="font-mono text-[11px] text-[#5b76fe]">{item.url}</p>
                  <p className="mt-2 text-sm leading-6 text-[#555a6a]">{item.body}</p>
                </GuidePanel>
              ))}
            </div>
          ) : null}

          {activeTab === "matching" ? (
            <div className="grid gap-4 lg:grid-cols-3">
              {TRIAL_MATCH_DIMENSIONS.map((item) => (
                <GuidePanel key={item.label} title={item.label} icon={Target}>
                  <p className="text-sm leading-6 text-[#555a6a]">{item.body}</p>
                </GuidePanel>
              ))}
            </div>
          ) : null}

          {activeTab === "management" ? (
            <div className="grid gap-4 lg:grid-cols-[0.95fr_1.05fr]">
              <GuidePanel title="Pursuit lifecycle" icon={FileText}>
                <div className="flex flex-wrap gap-2">
                  {PURSUIT_STATUSES.map((status) => (
                    <span key={status.id} className="rounded-full bg-white px-3 py-1.5 text-xs font-semibold text-[#555a6a] shadow-[rgb(224_226_232)_0px_0px_0px_1px]">
                      {status.label}
                    </span>
                  ))}
                </div>
                <p className="mt-4 text-sm leading-6 text-[#555a6a]">
                  A tracked trial becomes a patient-level record backed by durable storage. The board can later move to
                  SQLite without changing the product contract: it stores trial metadata, status, next step, tasks,
                  events, evidence snapshot, and source provenance.
                </p>
              </GuidePanel>
              <GuidePanel title="Agent transparency" icon={Settings2}>
                <p className="text-sm leading-6 text-[#555a6a]">
                  The agent inspector shows exactly what the run received: skill instructions, assembled prompt, chart
                  context, steering messages, tools, permissions, source data tools, transcript, and generated artifacts.
                </p>
                {onOpenInspector ? (
                  <button
                    type="button"
                    onClick={onOpenInspector}
                    className="mt-4 inline-flex items-center gap-2 rounded-xl bg-[#1c1c1e] px-4 py-2 text-sm font-semibold text-white hover:bg-[#333438]"
                  >
                    <Eye size={15} />
                    Open agent inspector
                  </button>
                ) : null}
              </GuidePanel>
            </div>
          ) : null}
        </div>
      </section>
    </div>
  );
}

function GuidePanel({
  title,
  icon: Icon,
  children,
}: {
  title: string;
  icon: LucideIcon;
  children: ReactNode;
}) {
  return (
    <section className="rounded-2xl bg-white p-4 shadow-[rgb(224_226_232)_0px_0px_0px_1px]">
      <div className="mb-3 flex items-center gap-2">
        <Icon size={14} className="text-[#5b76fe]" />
        <h3 className="text-sm font-semibold text-[#1c1c1e]">{title}</h3>
      </div>
      {children}
    </section>
  );
}

function GuideList({
  items,
}: {
  items: Array<{ label: string; body: string }>;
}) {
  return (
    <div className="space-y-2">
      {items.map((item) => (
        <div key={item.label} className="rounded-xl border border-[#e9eaef] bg-[#fafbff] p-3">
          <p className="text-xs font-semibold text-[#1c1c1e]">{item.label}</p>
          <p className="mt-1 text-xs leading-5 text-[#667085]">{item.body}</p>
        </div>
      ))}
    </div>
  );
}

function RunCanvasSummary({
  state,
  canvasNodes,
  trackedNctIds,
  onToggleNode,
  onTrackNode,
  isUpdatingSelection,
  isTracking,
}: {
  state: RunStateResponse;
  canvasNodes: CanvasNode[];
  trackedNctIds: Set<string>;
  onToggleNode: (node: CanvasNode, selected: boolean) => void;
  onTrackNode: (node: CanvasNode) => void;
  isUpdatingSelection: boolean;
  isTracking: boolean;
}) {
  const criteria = canvasNodes.filter((node) => node.kind === "criteria");
  const anchors = canvasNodes.filter((node) => node.kind === "anchor");
  const candidates = canvasNodes.filter((node) => node.kind === "candidate_trial");
  const selectedTrials = candidates.filter((node) => node.selected);
  const packetTasks = canvasNodes.filter((node) => node.kind === "packet_task");
  const summaries = canvasNodes.filter((node) => node.kind === "summary");
  return (
    <div className="space-y-4">
      <section className="rounded-2xl bg-white p-4 shadow-[rgb(224_226_232)_0px_0px_0px_1px]">
        <div className="flex items-center gap-2">
          <Target size={14} className="text-[#5b76fe]" />
          <h3 className="text-sm font-semibold text-[#1c1c1e]">Search criteria</h3>
          <span className="ml-auto rounded-full bg-[#eef1ff] px-2 py-0.5 text-[10px] font-semibold text-[#5b76fe]">
            {state.status}
          </span>
        </div>
        <div className="mt-3 grid grid-cols-3 gap-2">
          <CanvasMetric label="Anchors" value={String(anchors.length)} />
          <CanvasMetric label="Candidates" value={String(candidates.length || "pending")} />
          <CanvasMetric label="Selected" value={String(selectedTrials.length)} />
        </div>
        <div className="mt-3 space-y-2">
          {criteria.map((node) => (
            <CanvasNodeCard key={node.node_id} node={node} compact />
          ))}
          {summaries.map((node) => (
            <CanvasNodeCard key={node.node_id} node={node} compact />
          ))}
        </div>
        <div className="mt-3 rounded-xl border border-[#e9eaef] bg-[#fafbff] p-3">
          <p className="text-[10px] font-semibold uppercase tracking-wider text-[#8d92a3]">Selected anchors</p>
          <div className="mt-2 flex flex-wrap gap-1.5">
            {anchors.length ? (
              anchors.map((node) => (
                <span key={node.node_id} className="rounded-full bg-white px-2 py-1 text-[11px] text-[#555a6a] shadow-[rgb(224_226_232)_0px_0px_0px_1px]">
                  {node.title}
                </span>
              ))
            ) : (
              <span className="text-[11px] text-[#a5a8b5]">No anchors selected.</span>
            )}
          </div>
        </div>
      </section>

      <section className="rounded-2xl bg-white p-4 shadow-[rgb(224_226_232)_0px_0px_0px_1px]">
        <div className="flex items-center gap-2">
          <Search size={14} className="text-[#5b76fe]" />
          <h3 className="text-sm font-semibold text-[#1c1c1e]">Candidate trials</h3>
          <span className="ml-auto text-[11px] text-[#a5a8b5]">{candidates.length} found</span>
        </div>
        <div className="mt-3 space-y-2">
          {candidates.length ? (
            candidates.map((node) => (
              <TrialCanvasCard
                key={node.node_id}
                node={node}
                isUpdating={isUpdatingSelection}
                isTracking={isTracking}
                isTracked={trackedNctIds.has(String(node.data.nct_id ?? node.node_id.replace(/^trial:/, "")).toUpperCase())}
                onToggle={(selected) => onToggleNode(node, selected)}
                onTrack={() => onTrackNode(node)}
              />
            ))
          ) : (
            <div className="rounded-xl border border-dashed border-[#e9eaef] p-3 text-xs leading-5 text-[#a5a8b5]">
              Candidate trials will appear here as the agent searches and reviews criteria.
            </div>
          )}
        </div>
      </section>

      {packetTasks.length ? (
        <section className="rounded-2xl bg-white p-4 shadow-[rgb(224_226_232)_0px_0px_0px_1px]">
          <div className="flex items-center gap-2">
            <FileText size={14} className="text-[#5b76fe]" />
            <h3 className="text-sm font-semibold text-[#1c1c1e]">Packet workflow</h3>
          </div>
          <div className="mt-3 space-y-2">
            {packetTasks.map((node) => (
              <CanvasNodeCard key={node.node_id} node={node} />
            ))}
          </div>
        </section>
      ) : null}
    </div>
  );
}

function CanvasMetric({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-lg border border-[#eef0f5] px-3 py-2">
      <span className="block text-[10px] text-[#8d92a3]">{label}</span>
      <span className="font-mono text-xs font-semibold text-[#1c1c1e]">{value}</span>
    </div>
  );
}

function CanvasNodeCard({ node, compact = false }: { node: CanvasNode; compact?: boolean }) {
  return (
    <div className="rounded-xl border border-[#e9eaef] bg-[#fafbff] p-3">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="text-xs font-semibold text-[#1c1c1e]">{node.title}</p>
          {node.summary ? (
            <p className={`${compact ? "mt-0.5" : "mt-1"} text-[11px] leading-5 text-[#667085]`}>
              {node.summary}
            </p>
          ) : null}
        </div>
        <span className="shrink-0 rounded-full bg-white px-2 py-0.5 text-[10px] font-semibold text-[#667085] shadow-[rgb(224_226_232)_0px_0px_0px_1px]">
          {node.status}
        </span>
      </div>
    </div>
  );
}

function TrialCanvasCard({
  node,
  isUpdating,
  isTracking,
  isTracked,
  onToggle,
  onTrack,
}: {
  node: CanvasNode;
  isUpdating: boolean;
  isTracking: boolean;
  isTracked: boolean;
  onToggle: (selected: boolean) => void;
  onTrack: () => void;
}) {
  const nctId = String(node.data.nct_id ?? node.node_id.replace(/^trial:/, ""));
  const fitScore = node.data.fit_score;
  const gaps = Array.isArray(node.data.gaps) ? node.data.gaps : [];
  const sponsor = typeof node.data.sponsor === "string" ? node.data.sponsor : "";
  return (
    <div className={`rounded-xl border p-3 ${node.selected ? "border-[#5b76fe] bg-[#f7f8ff]" : "border-[#e9eaef] bg-white"}`}>
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="font-mono text-[10px] font-semibold text-[#5b76fe]">{nctId}</p>
          <h4 className="mt-0.5 text-sm font-semibold leading-5 text-[#1c1c1e]">{node.title}</h4>
          <p className="mt-1 text-[11px] leading-4 text-[#667085]">
            {[sponsor, node.summary].filter(Boolean).join(" · ")}
          </p>
        </div>
        {fitScore !== undefined ? (
          <span className="shrink-0 rounded-full bg-[#eef1ff] px-2 py-0.5 text-[10px] font-semibold text-[#5b76fe]">
            fit {String(fitScore)}
          </span>
        ) : null}
      </div>
      {gaps.length ? (
        <p className="mt-2 text-[11px] leading-4 text-[#8d92a3]">
          {gaps.length} criteria need verification.
        </p>
      ) : null}
      <div className="mt-3 flex items-center justify-between gap-2">
        <span className="rounded-full bg-[#f5f6f8] px-2 py-0.5 text-[10px] font-semibold text-[#667085]">
          {node.status}
        </span>
        <div className="flex items-center gap-1.5">
          <button
            type="button"
            onClick={onTrack}
            disabled={isTracking || isTracked}
            className="rounded-lg bg-white px-3 py-1.5 text-[11px] font-semibold text-[#5b76fe] shadow-[rgb(224_226_232)_0px_0px_0px_1px] hover:bg-[#f7f8ff] disabled:cursor-not-allowed disabled:text-[#a5a8b5]"
          >
            {isTracked ? "Tracked" : "Track"}
          </button>
          <button
            type="button"
            onClick={() => onToggle(!node.selected)}
            disabled={isUpdating}
            className={`rounded-lg px-3 py-1.5 text-[11px] font-semibold ${
              node.selected
                ? "bg-[#1c1c1e] text-white hover:bg-[#333438]"
                : "bg-[#eef1ff] text-[#5b76fe] hover:bg-[#dde3ff]"
            } disabled:cursor-not-allowed disabled:opacity-50`}
          >
            {node.selected ? "Selected" : "Select"}
          </button>
        </div>
      </div>
    </div>
  );
}

const PURSUIT_STATUSES: Array<{ id: TrialPursuitStatus; label: string }> = [
  { id: "interested", label: "Interested" },
  { id: "reviewing", label: "Reviewing" },
  { id: "packet", label: "Packet" },
  { id: "contacted", label: "Contacted" },
  { id: "submitted", label: "Submitted" },
  { id: "follow_up", label: "Follow-up" },
  { id: "closed", label: "Closed" },
];

function TrialPursuitBoard({
  pursuits,
  isLoading,
  isUpdating,
  onMove,
  onAddTask,
}: {
  pursuits: TrialPursuit[];
  isLoading: boolean;
  isUpdating: boolean;
  onMove: (pursuit: TrialPursuit, status: TrialPursuitStatus) => void;
  onAddTask: (pursuit: TrialPursuit) => void;
}) {
  const active = pursuits.filter((pursuit) => pursuit.status !== "closed");
  return (
    <section className="rounded-2xl bg-white p-4 shadow-[rgb(224_226_232)_0px_0px_0px_1px]">
      <div className="flex items-center gap-2">
        <FileText size={14} className="text-[#5b76fe]" />
        <h3 className="text-sm font-semibold text-[#1c1c1e]">Trial pursuit board</h3>
        <span className="ml-auto text-[11px] text-[#a5a8b5]">{active.length} active</span>
      </div>
      <p className="mt-1 text-xs leading-5 text-[#667085]">
        Durable trials the clinician may pursue beyond this run: packet work, outreach, submission, and follow-up.
      </p>

      {isLoading ? (
        <div className="mt-3 flex h-24 items-center justify-center rounded-xl border border-[#e9eaef] text-xs text-[#a5a8b5]">
          <Loader2 size={14} className="mr-2 animate-spin" />
          Loading pursuits…
        </div>
      ) : null}

      {!isLoading && !pursuits.length ? (
        <div className="mt-3 rounded-xl border border-dashed border-[#e9eaef] p-3 text-xs leading-5 text-[#a5a8b5]">
          Track a candidate trial to start a patient-level pursuit. The board persists across trial-finder runs.
        </div>
      ) : null}

      <div className="mt-3 space-y-3">
        {pursuits.map((pursuit) => (
          <div key={pursuit.pursuit_id} className="rounded-xl border border-[#e9eaef] bg-[#fafbff] p-3">
            <div className="flex items-start justify-between gap-3">
              <div className="min-w-0">
                <p className="font-mono text-[10px] font-semibold text-[#5b76fe]">{pursuit.nct_id}</p>
                <h4 className="mt-0.5 text-sm font-semibold leading-5 text-[#1c1c1e]">{pursuit.title}</h4>
                <p className="mt-1 text-[11px] leading-4 text-[#667085]">
                  {[pursuit.sponsor, pursuit.trial_status, pursuit.fit_score !== null ? `fit ${pursuit.fit_score}` : ""]
                    .filter(Boolean)
                    .join(" · ")}
                </p>
              </div>
              <span className="shrink-0 rounded-full bg-white px-2 py-0.5 text-[10px] font-semibold text-[#667085] shadow-[rgb(224_226_232)_0px_0px_0px_1px]">
                {pursuitStatusLabel(pursuit.status)}
              </span>
            </div>
            <p className="mt-2 text-[11px] leading-4 text-[#555a6a]">{pursuit.next_step}</p>
            {pursuit.tasks.length ? (
              <div className="mt-2 space-y-1">
                {pursuit.tasks.slice(-2).map((task) => (
                  <div key={task.task_id} className="rounded-lg bg-white px-2 py-1.5 text-[11px] text-[#667085] shadow-[rgb(224_226_232)_0px_0px_0px_1px]">
                    {task.title}
                  </div>
                ))}
              </div>
            ) : null}
            <div className="mt-3 flex flex-wrap items-center gap-1.5">
              {PURSUIT_STATUSES.filter((status) => status.id !== pursuit.status).slice(0, 4).map((status) => (
                <button
                  key={status.id}
                  type="button"
                  onClick={() => onMove(pursuit, status.id)}
                  disabled={isUpdating}
                  className="rounded-lg bg-white px-2.5 py-1.5 text-[11px] font-semibold text-[#555a6a] shadow-[rgb(224_226_232)_0px_0px_0px_1px] hover:bg-[#f7f8ff] hover:text-[#5b76fe] disabled:cursor-not-allowed disabled:opacity-50"
                >
                  {status.label}
                </button>
              ))}
              <button
                type="button"
                onClick={() => onAddTask(pursuit)}
                disabled={isUpdating}
                className="ml-auto rounded-lg bg-[#eef1ff] px-2.5 py-1.5 text-[11px] font-semibold text-[#5b76fe] hover:bg-[#dde3ff] disabled:cursor-not-allowed disabled:opacity-50"
              >
                Add task
              </button>
            </div>
          </div>
        ))}
      </div>
    </section>
  );
}

function pursuitPayloadFromCanvasNode(node: CanvasNode, runId: string) {
  const nctId = String(node.data.nct_id ?? node.node_id.replace(/^trial:/, "")).toUpperCase();
  const sponsor = typeof node.data.sponsor === "string" ? node.data.sponsor : null;
  const trialStatus = typeof node.data.status === "string" ? node.data.status : node.status;
  const fitScore = Number(node.data.fit_score);
  return {
    nct_id: nctId,
    title: node.title,
    status: "interested" as TrialPursuitStatus,
    sponsor,
    trial_status: trialStatus,
    source_url: `https://clinicaltrials.gov/study/${nctId}`,
    source_kind: "clinicaltrials.gov",
    fit_score: Number.isFinite(fitScore) ? fitScore : null,
    next_step: "Review eligibility gaps and decide whether to prepare an outreach packet.",
    created_from_run_id: runId,
    created_from_canvas_node_id: node.node_id,
    evidence_snapshot: {
      canvas_summary: node.summary,
      canvas_data: node.data,
    },
  };
}

function pursuitStatusLabel(status: TrialPursuitStatus | string) {
  return PURSUIT_STATUSES.find((item) => item.id === status)?.label ?? status;
}

function nextStepForStatus(status: TrialPursuitStatus) {
  return {
    interested: "Review eligibility gaps and decide whether to prepare an outreach packet.",
    reviewing: "Complete a deeper eligibility review against the patient chart.",
    packet: "Prepare the patient-facing outreach packet and missing-document checklist.",
    contacted: "Track coordinator response and confirm next requested materials.",
    submitted: "Monitor submission status and next site follow-up.",
    follow_up: "Follow up with the site and update the pursuit timeline.",
    closed: "No further action unless the clinician reopens this pursuit.",
  }[status];
}

function defaultTaskForStatus(status: TrialPursuitStatus) {
  return {
    interested: "Confirm this trial is worth a deeper eligibility review.",
    reviewing: "Check eligibility gaps against latest chart evidence.",
    packet: "Prepare outreach packet and document checklist.",
    contacted: "Follow up with trial coordinator.",
    submitted: "Check submission status.",
    follow_up: "Log trial-site response.",
    closed: "Record closure reason.",
  }[status];
}

type InspectorTab =
  | "overview"
  | "instructions"
  | "context"
  | "tools"
  | "transcript"
  | "artifacts"
  | "permissions";

function RunInspectorSuite({
  open,
  expanded,
  data,
  isLoading,
  onClose,
  onToggleExpanded,
}: {
  open: boolean;
  expanded: boolean;
  data: RunInspectorResponse | undefined;
  isLoading: boolean;
  onClose: () => void;
  onToggleExpanded: () => void;
}) {
  const [activeTab, setActiveTab] = useState<InspectorTab>("overview");
  if (!open) return null;

  const tabs: Array<{ id: InspectorTab; label: string; icon: LucideIcon }> = [
    { id: "overview", label: "Overview", icon: Eye },
    { id: "instructions", label: "Instructions", icon: BookOpen },
    { id: "context", label: "Context", icon: Database },
    { id: "tools", label: "Tools", icon: Wrench },
    { id: "transcript", label: "Transcript", icon: History },
    { id: "artifacts", label: "Artifacts", icon: FileText },
    { id: "permissions", label: "Permissions", icon: ShieldCheck },
  ];

  return (
    <div className="fixed inset-0 z-50 bg-[#111827]/20 backdrop-blur-[1px]">
      <section
        className={`absolute bg-white shadow-2xl ${
          expanded
            ? "inset-3 rounded-2xl"
            : "bottom-0 right-0 top-0 w-full max-w-[920px] rounded-l-2xl"
        }`}
      >
        <div className="flex h-full flex-col">
          <header className="border-b border-[#eef0f5] px-5 py-4">
            <div className="flex items-center gap-3">
              <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-[#eef1ff] text-[#5b76fe]">
                <Settings2 size={18} />
              </div>
              <div>
                <h2 className="text-sm font-semibold text-[#1c1c1e]">Agent Inspector</h2>
                <p className="text-[11px] text-[#8d92a3]">
                  Skill files, source tools, context, permissions, transcript, and artifacts for this run.
                </p>
              </div>
              <div className="ml-auto flex items-center gap-1">
                <button
                  type="button"
                  onClick={onToggleExpanded}
                  className="inline-flex h-8 w-8 items-center justify-center rounded-lg text-[#667085] hover:bg-[#f7f8ff] hover:text-[#5b76fe]"
                  title={expanded ? "Collapse inspector" : "Expand inspector"}
                >
                  {expanded ? <Minimize2 size={15} /> : <Maximize2 size={15} />}
                </button>
                <button
                  type="button"
                  onClick={onClose}
                  className="inline-flex h-8 w-8 items-center justify-center rounded-lg text-[#667085] hover:bg-[#f7f8ff] hover:text-[#5b76fe]"
                  title="Close inspector"
                >
                  <X size={15} />
                </button>
              </div>
            </div>
          </header>

          <div className="border-b border-[#eef0f5] px-4 py-2">
            <div className="flex gap-1 overflow-x-auto">
              {tabs.map((tab) => {
                const Icon = tab.icon;
                return (
                  <button
                    key={tab.id}
                    type="button"
                    onClick={() => setActiveTab(tab.id)}
                    className={`inline-flex items-center gap-1.5 rounded-lg px-3 py-2 text-xs font-semibold ${
                      activeTab === tab.id
                        ? "bg-[#eef1ff] text-[#5b76fe]"
                        : "text-[#667085] hover:bg-[#f7f8ff] hover:text-[#1c1c1e]"
                    }`}
                  >
                    <Icon size={13} />
                    {tab.label}
                  </button>
                );
              })}
            </div>
          </div>

          <div className="flex-1 overflow-auto bg-[#f5f6f8] p-5">
            {isLoading && !data ? (
              <div className="flex h-64 items-center justify-center rounded-2xl bg-white text-sm text-[#667085] shadow-[rgb(224_226_232)_0px_0px_0px_1px]">
                <Loader2 size={16} className="mr-2 animate-spin" />
                Loading inspector…
              </div>
            ) : null}
            {data ? <InspectorTabBody tab={activeTab} data={data} /> : null}
          </div>
        </div>
      </section>
    </div>
  );
}

function InspectorTabBody({
  tab,
  data,
}: {
  tab: InspectorTab;
  data: RunInspectorResponse;
}) {
  if (tab === "overview") {
    const transcriptSummary = data.transcript.summary;
    return (
      <div className="grid gap-4 xl:grid-cols-3">
        <InspectorSection title="Run" icon={Eye}>
          <KeyValues value={data.run} />
        </InspectorSection>
        <InspectorSection title="Skill" icon={BookOpen}>
          <KeyValues value={data.skill} />
        </InspectorSection>
        <InspectorSection title="Counts" icon={History}>
          <KeyValues value={transcriptSummary} />
        </InspectorSection>
      </div>
    );
  }

  if (tab === "instructions") {
    return (
      <div className="space-y-4">
        <InspectorSection title="Assembled Prompt" icon={Code2}>
          <CodeBlock value={data.instructions.assembled_prompt} />
        </InspectorSection>
        <div className="grid gap-4 xl:grid-cols-2">
          <InspectorSection title="Skill Instructions" icon={BookOpen}>
            <CodeBlock value={data.instructions.skill_md} />
          </InspectorSection>
          <InspectorSection title="Workspace Template" icon={FileText}>
            <CodeBlock value={data.instructions.workspace_template ?? "(none)"} />
          </InspectorSection>
        </div>
        <InspectorSection title="Output Schema" icon={Code2}>
          <JsonBlock value={data.instructions.output_schema} />
        </InspectorSection>
        <InspectorFileList files={data.instructions.files} showContent />
      </div>
    );
  }

  if (tab === "context") {
    return (
      <div className="space-y-4">
        <div className="grid gap-4 xl:grid-cols-2">
          <InspectorSection title="Run Brief" icon={Target}>
            <JsonBlock value={data.context.brief} />
          </InspectorSection>
          <InspectorSection title="Patient Memory" icon={Sparkles}>
            <JsonBlock value={data.context.patient_memory} />
          </InspectorSection>
        </div>
        <InspectorSection title="Steering Messages" icon={MessageSquareText}>
          <JsonBlock value={data.context.messages} />
        </InspectorSection>
        <InspectorSection title="Canvas State" icon={PanelRight}>
          <JsonBlock value={data.context.canvas} />
        </InspectorSection>
      </div>
    );
  }

  if (tab === "tools") {
    return <InspectorTools tools={data.tools} />;
  }

  if (tab === "transcript") {
    return (
      <div className="space-y-4">
        <InspectorSection title="Transcript Summary" icon={History}>
          <JsonBlock value={data.transcript.summary} />
        </InspectorSection>
        <InspectorSection title="Event Timeline" icon={History}>
          <TranscriptPane events={data.transcript.events} />
        </InspectorSection>
        <InspectorSection title="Raw Events" icon={Code2}>
          <JsonBlock value={data.transcript.events} />
        </InspectorSection>
      </div>
    );
  }

  if (tab === "artifacts") {
    return (
      <div className="space-y-4">
        <InspectorSection title="Workspace Markdown" icon={FileText}>
          <CodeBlock value={data.artifacts.workspace_markdown || "(empty)"} />
        </InspectorSection>
        <div className="grid gap-4 xl:grid-cols-2">
          <InspectorSection title="Canvas JSON" icon={PanelRight}>
            <JsonBlock value={data.artifacts.canvas} />
          </InspectorSection>
          <InspectorSection title="Output JSON" icon={Code2}>
            <JsonBlock value={data.artifacts.output ?? { status: "not finalized" }} />
          </InspectorSection>
        </div>
        <InspectorFileList files={data.artifacts.files} />
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <InspectorSection title="Permission Model" icon={ShieldCheck}>
        <JsonBlock value={data.permissions} />
      </InspectorSection>
      <InspectorSection title="Tool Permissions" icon={Wrench}>
        <InspectorTools tools={data.tools} compact />
      </InspectorSection>
    </div>
  );
}

function InspectorSection({
  title,
  icon: Icon,
  children,
}: {
  title: string;
  icon: LucideIcon;
  children: ReactNode;
}) {
  return (
    <section className="rounded-2xl bg-white p-4 shadow-[rgb(224_226_232)_0px_0px_0px_1px]">
      <div className="mb-3 flex items-center gap-2">
        <Icon size={14} className="text-[#5b76fe]" />
        <h3 className="text-sm font-semibold text-[#1c1c1e]">{title}</h3>
      </div>
      {children}
    </section>
  );
}

function InspectorTools({
  tools,
  compact = false,
}: {
  tools: RunInspectorResponse["tools"];
  compact?: boolean;
}) {
  return (
    <div className="space-y-3">
      {tools.map((tool) => (
        <section key={tool.alias} className="rounded-2xl bg-white p-4 shadow-[rgb(224_226_232)_0px_0px_0px_1px]">
          <div className="flex flex-wrap items-start gap-3">
            <div className="min-w-0 flex-1">
              <div className="flex flex-wrap items-center gap-2">
                <h3 className="font-mono text-sm font-semibold text-[#1c1c1e]">{tool.name}</h3>
                <InspectorPill>{tool.kind}</InspectorPill>
                <InspectorPill tone={tool.available ? "blue" : "red"}>
                  {tool.available ? "available" : "unavailable"}
                </InspectorPill>
              </div>
              <p className="mt-2 text-xs leading-5 text-[#667085]">{tool.description}</p>
              <p className="mt-2 text-[11px] font-semibold text-[#555a6a]">{tool.permission}</p>
            </div>
            <span className="font-mono text-[11px] text-[#8d92a3]">{tool.alias}</span>
          </div>
          {!compact ? (
            <details className="mt-3 rounded-xl border border-[#e9eaef] p-3">
              <summary className="cursor-pointer text-xs font-semibold text-[#555a6a]">Input schema</summary>
              <div className="mt-3">
                <JsonBlock value={tool.input_schema} />
              </div>
            </details>
          ) : null}
        </section>
      ))}
    </div>
  );
}

function InspectorFileList({
  files,
  showContent = false,
}: {
  files: RunInspectorResponse["instructions"]["files"];
  showContent?: boolean;
}) {
  if (!files.length) {
    return (
      <InspectorSection title="Files" icon={FileText}>
        <p className="text-sm text-[#8d92a3]">No files found.</p>
      </InspectorSection>
    );
  }
  return (
    <InspectorSection title="Files" icon={FileText}>
      <div className="space-y-2">
        {files.map((file) => (
          <details key={`${file.kind}-${file.path}`} className="rounded-xl border border-[#e9eaef] bg-[#fafbff] p-3">
            <summary className="cursor-pointer">
              <span className="font-mono text-xs font-semibold text-[#1c1c1e]">{file.path}</span>
              <span className="ml-2 text-[11px] text-[#8d92a3]">
                {file.kind} · {formatBytes(file.size_bytes)}
              </span>
            </summary>
            {showContent && file.content !== null ? (
              <div className="mt-3">
                <CodeBlock value={file.content} />
              </div>
            ) : null}
          </details>
        ))}
      </div>
    </InspectorSection>
  );
}

function InspectorPill({
  children,
  tone = "neutral",
}: {
  children: ReactNode;
  tone?: "neutral" | "blue" | "red";
}) {
  const classes = {
    neutral: "bg-[#f5f6f8] text-[#667085]",
    blue: "bg-[#eef1ff] text-[#5b76fe]",
    red: "bg-[#fef2f2] text-[#991b1b]",
  }[tone];
  return <span className={`rounded-full px-2 py-0.5 text-[10px] font-semibold ${classes}`}>{children}</span>;
}

function KeyValues({ value }: { value: Record<string, unknown> }) {
  return (
    <dl className="space-y-2">
      {Object.entries(value).map(([key, raw]) => (
        <div key={key} className="flex gap-3 border-b border-[#f0f1f4] pb-2 last:border-0 last:pb-0">
          <dt className="w-32 shrink-0 text-[11px] font-semibold uppercase tracking-wide text-[#8d92a3]">{key}</dt>
          <dd className="min-w-0 flex-1 break-words font-mono text-xs text-[#1c1c1e]">{formatInspectorValue(raw)}</dd>
        </div>
      ))}
    </dl>
  );
}

function JsonBlock({ value }: { value: unknown }) {
  return <CodeBlock value={JSON.stringify(value, null, 2)} />;
}

function CodeBlock({ value }: { value: string }) {
  return (
    <pre className="max-h-[520px] overflow-auto rounded-xl bg-[#111827] p-4 text-xs leading-5 text-[#e5e7eb]">
      <code>{value}</code>
    </pre>
  );
}

function formatInspectorValue(value: unknown): string {
  if (value === null || value === undefined) return "";
  if (typeof value === "string" || typeof value === "number" || typeof value === "boolean") return String(value);
  return JSON.stringify(value);
}

function formatBytes(value: number): string {
  if (value < 1024) return `${value} B`;
  if (value < 1024 * 1024) return `${(value / 1024).toFixed(1)} KB`;
  return `${(value / (1024 * 1024)).toFixed(1)} MB`;
}

function RunDebugPanels({
  workspace,
  events,
  connection,
  finished,
  onSave,
}: {
  workspace: { markdown: string; citations: Citation[] } | undefined;
  events: Parameters<typeof TranscriptPane>[0]["events"];
  connection: string;
  finished: boolean;
  onSave: () => void;
}) {
  return (
    <section className="rounded-2xl bg-white p-4 shadow-[rgb(224_226_232)_0px_0px_0px_1px]">
      <div className="flex items-center justify-between gap-3">
        <div className="flex items-center gap-2">
          <Beaker size={14} className="text-[#5b76fe]" />
          <h3 className="text-sm font-semibold text-[#1c1c1e]">Debug artifacts</h3>
        </div>
        {finished ? (
          <button
            type="button"
            onClick={onSave}
            className="inline-flex items-center gap-1.5 rounded-lg border border-[#5b76fe] bg-[#eef1ff] px-3 py-1.5 text-xs font-semibold text-[#3a4ca8] hover:bg-[#dde3ff]"
          >
            <Save size={12} />
            Save
          </button>
        ) : null}
      </div>
      <details className="mt-3 rounded-xl border border-[#e9eaef] p-3">
        <summary className="cursor-pointer text-xs font-semibold text-[#555a6a]">
          Workspace markdown · {workspace?.citations.length ?? 0} citations
        </summary>
        <div className="mt-3 max-h-[520px] overflow-auto">
          {workspace ? (
            <WorkspacePane markdown={workspace.markdown} citations={workspace.citations} />
          ) : (
            <div className="flex h-24 items-center justify-center text-xs text-[#a5a8b5]">
              <Loader2 size={14} className="mr-2 animate-spin" />
              Loading artifact…
            </div>
          )}
        </div>
      </details>
      <details className="mt-2 rounded-xl border border-[#e9eaef] p-3">
        <summary className="cursor-pointer text-xs font-semibold text-[#555a6a]">
          Event transcript · {events.length} events · {connection}
        </summary>
        <div className="mt-3 max-h-[420px] overflow-auto">
          <TranscriptPane events={events} />
        </div>
      </details>
    </section>
  );
}

function humanizeFailure(reason: string) {
  if (reason.includes("ANTHROPIC_API_KEY")) {
    return "The production agent runtime is missing ANTHROPIC_API_KEY. Configure the key and start a new run.";
  }
  if (reason.includes("deterministic skill runs are disabled")) {
    return "This workspace no longer supports deterministic trial runs. Configure the agent runtime and start again.";
  }
  if (reason.includes("schema validation")) {
    return "The agent produced a structured result that did not pass validation. The workspace artifact is preserved in the canvas for review, but this run should be retried after tightening the output schema handling.";
  }
  return reason;
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

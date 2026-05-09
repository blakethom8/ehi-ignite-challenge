import { useMemo, useState } from "react";
import {
  AlertTriangle,
  Bot,
  CheckCircle2,
  ClipboardList,
  Database,
  FileText,
  ListChecks,
  LockKeyhole,
  MapPin,
  MessageSquareText,
  Package,
  Search,
  Send,
  ShieldCheck,
  Sparkles,
  UserRound,
} from "lucide-react";
import type { TrialCandidate, TrialPursuitStatus, WorkspaceEvent, WorkspaceSurfaceDefinition } from "./contracts";
import {
  mockArtifacts,
  mockCandidates,
  mockEvents,
  mockMessages,
  mockPursuits,
  mockSession,
} from "./fixtures";
import { trialFinderWorkspace } from "./workspaceDefinition";
import { WorkspaceFrame } from "./WorkspaceFrame";

const PURSUIT_STATUSES: TrialPursuitStatus[] = [
  "interested",
  "reviewing",
  "packet",
  "contacted",
  "submitted",
  "follow-up",
  "closed",
];

const panelCard = "rounded-xl border border-[#e8edf3] bg-white shadow-[rgb(224_226_232)_0px_0px_0px_1px]";

function percent(value: number | undefined): string {
  return typeof value === "number" ? `${value}%` : "-";
}

function burdenTone(value: TrialCandidate["operationalBurden"]): string {
  if (value === "low") return "bg-[#f4fffc] text-[#047857] border-[#cdeee9]";
  if (value === "medium") return "bg-[#fff8f1] text-[#9a5a16] border-[#f6dfc9]";
  if (value === "high") return "bg-[#fff5f5] text-[#b42318] border-[#f3c4c4]";
  return "bg-[#f7f8fc] text-[#667085] border-[#e8edf3]";
}

function scoreTone(value: number | undefined): string {
  if (!value) return "bg-[#f5f7fb] text-[#667085]";
  if (value >= 80) return "bg-[#edf9f5] text-[#047857]";
  if (value >= 65) return "bg-[#fff8f1] text-[#9a5a16]";
  return "bg-[#fff5f5] text-[#b42318]";
}

function SurfaceHeader({
  icon,
  title,
  meta,
}: {
  icon: React.ReactNode;
  title: string;
  meta?: string;
}) {
  return (
    <div className="flex min-h-14 items-center justify-between gap-3 border-b border-[#eef2f6] bg-[#fbfcff] px-4 py-3">
      <div className="flex min-w-0 items-center gap-2">
        {icon}
        <div className="min-w-0">
          <div className="truncate text-sm font-semibold text-[#1d2433]">{title}</div>
          {meta && <div className="mt-0.5 text-xs text-[#667085]">{meta}</div>}
        </div>
      </div>
    </div>
  );
}

function ChatSurface() {
  return (
    <div className="flex h-full min-h-0 flex-col bg-[#fcfdff]">
      <SurfaceHeader
        icon={<MessageSquareText size={16} className="text-[#5b76fe]" />}
        title="Clinical brief"
        meta="Trial fit, exclusion risk, next step"
      />
      <div className="flex-1 space-y-4 overflow-auto px-4 py-5">
        {mockMessages.map((message) => (
          <div key={message.id} className={`flex gap-3 ${message.role === "user" ? "justify-end" : ""}`}>
            {message.role === "assistant" && (
              <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-[#eef1ff] text-[#5b76fe]">
                <Bot size={16} />
              </div>
            )}
            <div
              className={`max-w-[84%] rounded-2xl px-3.5 py-2.5 text-sm leading-6 ${
                message.role === "user"
                  ? "bg-[#5b76fe] text-white"
                  : "border border-[#e8edf3] bg-white text-[#344054] shadow-[rgba(17,24,39,0.03)_0px_8px_18px]"
              }`}
            >
              <div>{message.content}</div>
              <div className={`mt-1 text-[11px] font-medium ${message.role === "user" ? "text-white/70" : "text-[#98a2b3]"}`}>
                {message.at}
              </div>
            </div>
            {message.role === "user" && (
              <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-[#f1f3f7] text-[#667085]">
                <UserRound size={16} />
              </div>
            )}
          </div>
        ))}
      </div>
      <div className="border-t border-[#eef2f6] bg-white p-3">
        <div className="mb-2 flex flex-wrap gap-2">
          {["Recruiting only", "Explain exclusions", "Draft outreach"].map((label) => (
            <button
              key={label}
              type="button"
              className="rounded-lg border border-[#dfe4ea] bg-white px-2.5 py-1.5 text-xs font-medium text-[#555a6a] transition hover:border-[#cfd7ff] hover:text-[#1c1c1e]"
            >
              {label}
            </button>
          ))}
        </div>
        <div className="flex items-center gap-2 rounded-xl border border-[#dfe4ea] bg-[#f7f8fb] px-3 py-2.5 text-sm text-[#667085]">
          <Sparkles size={16} className="shrink-0 text-[#5b76fe]" />
          <span className="min-w-0 flex-1 truncate">Ask about eligibility, burden, or referral timing</span>
          <button type="button" className="flex h-7 w-7 shrink-0 items-center justify-center rounded-lg bg-[#5b76fe] text-white">
            <Send size={14} />
          </button>
        </div>
      </div>
    </div>
  );
}

function CandidateSurface({
  selectedCandidateId,
  onSelectCandidate,
}: {
  selectedCandidateId: string;
  onSelectCandidate: (candidateId: string) => void;
}) {
  return (
    <div className="min-h-full bg-[#fcfdff]">
      <SurfaceHeader
        icon={<Search size={16} className="text-[#5b76fe]" />}
        title="Ranked candidates"
        meta={`${mockCandidates.length} candidates ranked`}
      />
      <div className="space-y-3 p-4">
        {mockCandidates.map((candidate) => {
          const selected = candidate.id === selectedCandidateId;
          return (
            <button
              key={candidate.id}
              type="button"
              aria-pressed={selected}
              onClick={() => onSelectCandidate(candidate.id)}
              className={`w-full rounded-2xl p-4 text-left transition ${
                selected
                  ? "border border-[#cfd7ff] bg-[#f8f9ff] shadow-[rgb(207_215_255)_0px_0px_0px_1px]"
                  : "border border-[#e8edf3] bg-white hover:border-[#cfd7ff] hover:bg-[#fbfcff]"
              }`}
            >
              <div className="flex items-start justify-between gap-3">
                <div className="min-w-0">
                  <div className="text-[11px] font-semibold uppercase text-[#667085]">{candidate.nctId}</div>
                  <div className="mt-1 text-sm font-semibold leading-5 text-[#1d2433]">{candidate.title}</div>
                </div>
                <div className={`shrink-0 rounded-xl px-2.5 py-1.5 text-lg font-semibold tabular-nums ${scoreTone(candidate.matchScore)}`}>
                  {percent(candidate.matchScore)}
                </div>
              </div>

              <div className="mt-3 flex flex-wrap gap-1.5">
                <span className="rounded-lg bg-[#f1f3f7] px-2 py-1 text-xs font-medium text-[#667085]">{candidate.status}</span>
                {candidate.phase && (
                  <span className="rounded-lg bg-[#eef1ff] px-2 py-1 text-xs font-medium text-[#5b76fe]">{candidate.phase}</span>
                )}
                <span className={`rounded-lg border px-2 py-1 text-xs font-semibold ${burdenTone(candidate.operationalBurden)}`}>
                  {candidate.operationalBurden} burden
                </span>
              </div>

              <div className="mt-4 grid gap-2 text-xs">
                <SignalLine tone="fit" label="Fit" value={candidate.inclusionMatches[0]} />
                <SignalLine tone="risk" label="Risk" value={candidate.exclusionRisks[0]} />
              </div>
            </button>
          );
        })}
      </div>
    </div>
  );
}

function SignalLine({ tone, label, value }: { tone: "fit" | "risk"; label: string; value: string }) {
  return (
    <div className="flex gap-2 rounded-xl bg-white/70">
      <span className={`mt-1.5 h-2 w-2 shrink-0 rounded-full ${tone === "fit" ? "bg-[#00b473]" : "bg-[#f59e0b]"}`} />
      <div className="min-w-0">
        <span className={`font-semibold ${tone === "fit" ? "text-[#047857]" : "text-[#9a5a16]"}`}>{label}</span>
        <span className="text-[#667085]"> · {value}</span>
      </div>
    </div>
  );
}

function TrialDetailSurface({ candidate }: { candidate: TrialCandidate }) {
  return (
    <div className="min-h-full bg-[#fcfdff]">
      <SurfaceHeader
        icon={<FileText size={16} className="text-[#5b76fe]" />}
        title="Selected trial"
        meta={candidate.nctId}
      />
      <div className="space-y-4 p-4">
        <div className="rounded-2xl border border-[#dfe4ea] bg-white p-4 shadow-[rgba(17,24,39,0.03)_0px_10px_24px]">
          <div className="flex items-start justify-between gap-4">
            <div className="min-w-0">
              <h2 className="text-lg font-semibold leading-6 text-[#111827]">{candidate.title}</h2>
              <div className="mt-3 flex flex-wrap gap-1.5 text-xs font-medium">
                {candidate.conditions.map((condition) => (
                  <span key={condition} className="rounded-lg bg-[#f1f3f7] px-2 py-1 text-[#667085]">
                    {condition}
                  </span>
                ))}
              </div>
            </div>
            <div className={`shrink-0 rounded-2xl px-3 py-2 text-2xl font-semibold tabular-nums ${scoreTone(candidate.matchScore)}`}>
              {percent(candidate.matchScore)}
            </div>
          </div>
        </div>

        <div className="grid grid-cols-3 gap-2">
          <MetricCard label="Status" value={candidate.status} />
          <MetricCard label="Phase" value={candidate.phase ?? "Any"} />
          <MetricCard label="Enrollment" value={String(candidate.enrollment ?? "Unknown")} />
        </div>

        <DetailBlock
          title="Fit signals"
          tone="fit"
          icon={<CheckCircle2 size={15} />}
          items={candidate.inclusionMatches}
        />
        <DetailBlock
          title="Review risks"
          tone="risk"
          icon={<AlertTriangle size={15} />}
          items={candidate.exclusionRisks}
        />
        <DetailBlock
          title="Logistics"
          tone="neutral"
          icon={<MapPin size={15} />}
          items={[
            `${candidate.operationalBurden} operational burden`,
            `${candidate.enrollment ?? "Unknown"} target enrollment`,
            "Referral packet and site outreach require approval",
          ]}
        />

        <div className={`${panelCard} p-3`}>
          <div className="grid gap-2 sm:grid-cols-3">
            {["Keep", "Ask clinician", "Defer"].map((label) => (
              <button
                key={label}
                type="button"
                className="rounded-lg border border-[#dfe4ea] bg-white px-3 py-2 text-sm font-semibold text-[#344054] transition hover:border-[#cfd7ff] hover:text-[#1c1c1e]"
              >
                {label}
              </button>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}

function MetricCard({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-xl border border-[#e8edf3] bg-white px-3 py-2">
      <div className="text-[10px] font-semibold uppercase text-[#98a2b3]">{label}</div>
      <div className="mt-1 truncate text-sm font-semibold text-[#1d2433]">{value}</div>
    </div>
  );
}

function DetailBlock({
  title,
  tone,
  icon,
  items,
}: {
  title: string;
  tone: "fit" | "risk" | "neutral";
  icon: React.ReactNode;
  items: string[];
}) {
  const toneClass =
    tone === "fit"
      ? "bg-[#f4fffc] text-[#047857] border-[#cdeee9]"
      : tone === "risk"
        ? "bg-[#fff8f1] text-[#9a5a16] border-[#f6dfc9]"
        : "bg-[#f8f9ff] text-[#5b76fe] border-[#dfe4ff]";

  return (
    <div className={`${panelCard} p-4`}>
      <div className={`inline-flex items-center gap-2 rounded-lg border px-2.5 py-1.5 text-sm font-semibold ${toneClass}`}>
        {icon}
        {title}
      </div>
      <ul className="mt-3 space-y-2 text-sm leading-5 text-[#555a6a]">
        {items.map((item) => (
          <li key={item} className="flex gap-2">
            <span className="mt-2 h-1.5 w-1.5 shrink-0 rounded-full bg-[#98a2b3]" />
            <span>{item}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}

function PursuitBoardSurface() {
  const pursuitsByStatus = useMemo(
    () =>
      Object.fromEntries(
        PURSUIT_STATUSES.map((status) => [status, mockPursuits.filter((pursuit) => pursuit.status === status)]),
      ) as Record<TrialPursuitStatus, typeof mockPursuits>,
    [],
  );

  return (
    <div className="min-h-full bg-[#fcfdff]">
      <SurfaceHeader
        icon={<ClipboardList size={16} className="text-[#047857]" />}
        title="Pursuit board"
        meta={`${mockPursuits.length} active pursuits`}
      />
      <div className="flex gap-3 overflow-x-auto p-4">
        {PURSUIT_STATUSES.map((status) => (
          <div key={status} className="w-64 shrink-0 rounded-2xl border border-[#e8edf3] bg-[#f7f8fb]">
            <div className="border-b border-[#eef2f6] px-3 py-2 text-sm font-semibold capitalize text-[#1d2433]">
              {status}
            </div>
            <div className="space-y-2 p-3">
              {pursuitsByStatus[status].map((pursuit) => {
                const candidate = mockCandidates.find((item) => item.id === pursuit.candidateId);
                return (
                  <div key={pursuit.id} className="rounded-xl border border-[#e8edf3] bg-white p-3">
                    <div className="text-[11px] font-semibold uppercase text-[#667085]">{candidate?.nctId}</div>
                    <div className="mt-1 text-sm font-semibold leading-5 text-[#1d2433]">{candidate?.title}</div>
                    <div className="mt-3 text-xs text-[#667085]">{pursuit.tasks.filter((task) => task.status === "open").length} open tasks</div>
                  </div>
                );
              })}
              {pursuitsByStatus[status].length === 0 && (
                <div className="rounded-xl border border-dashed border-[#dfe4ea] bg-white p-3 text-xs text-[#98a2b3]">No trials</div>
              )}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

function InspectorSurface() {
  const [tab, setTab] = useState("Workspace");
  const tabs = ["Workspace", "Tools", "Context", "Sources", "Events", "Artifacts", "Approvals"];
  return (
    <div className="min-h-full bg-[#fcfdff]">
      <SurfaceHeader
        icon={<ShieldCheck size={16} className="text-[#6d28d9]" />}
        title="Inspector"
        meta="Controls and provenance"
      />
      <div className="border-b border-[#eef2f6] px-3 py-2">
        <div className="flex gap-1 overflow-x-auto rounded-xl bg-[#f7f8fb] p-1">
          {tabs.map((item) => (
            <button
              key={item}
              type="button"
              onClick={() => setTab(item)}
              className={`rounded-lg px-2.5 py-1.5 text-xs font-semibold ${
                tab === item ? "bg-white text-[#6d28d9] shadow-[rgb(224_226_232)_0px_0px_0px_1px]" : "text-[#667085] hover:text-[#1c1c1e]"
              }`}
            >
              {item}
            </button>
          ))}
        </div>
      </div>
      <div className="p-4">{renderInspectorTab(tab)}</div>
    </div>
  );
}

function renderInspectorTab(tab: string) {
  if (tab === "Workspace") {
    return (
      <div className="space-y-3">
        <InspectorRow icon={<Package size={15} />} label="Session" value={mockSession.id} />
        <InspectorRow icon={<UserRound size={15} />} label="Patient" value={mockSession.patientId || "None"} />
        <InspectorRow icon={<Sparkles size={15} />} label="Skill" value={mockSession.activeSkill} />
        <InspectorRow icon={<LockKeyhole size={15} />} label="State" value="Draft workspace" />
      </div>
    );
  }
  if (tab === "Tools") {
    return <InspectorList items={trialFinderWorkspace.tools.map((tool) => `${tool.label} · ${tool.permission}`)} />;
  }
  if (tab === "Context") {
    return (
      <InspectorList
        items={[
          "Patient package: workspace-shelly431",
          "Relevant facts: CKD signal, anticoagulation, surgical risk",
          "User steering: realistic travel, avoid perioperative conflicts",
        ]}
      />
    );
  }
  if (tab === "Sources") {
    return (
      <div className="space-y-3">
        {trialFinderWorkspace.sourceGroups.map((group) => (
          <div key={group.id} className={`${panelCard} p-3`}>
            <div className="text-sm font-semibold text-[#1d2433]">{group.label}</div>
            <div className="mt-1 text-xs text-[#667085]">{group.description}</div>
          </div>
        ))}
      </div>
    );
  }
  if (tab === "Events") {
    return <EventList events={mockEvents} />;
  }
  if (tab === "Artifacts") {
    return <InspectorList items={mockArtifacts.map((artifact) => `${artifact.label}: ${artifact.summary}`)} />;
  }
  return <InspectorList items={["Approval requested before external trial-site outreach."]} />;
}

function InspectorRow({ icon, label, value }: { icon: React.ReactNode; label: string; value: string }) {
  return (
    <div className={`${panelCard} flex items-start gap-3 p-3`}>
      <div className="mt-0.5 text-[#667085]">{icon}</div>
      <div className="min-w-0">
        <div className="text-[10px] font-semibold uppercase text-[#98a2b3]">{label}</div>
        <div className="mt-1 break-words text-sm font-medium text-[#1d2433]">{value}</div>
      </div>
    </div>
  );
}

function InspectorList({ items }: { items: string[] }) {
  return (
    <div className="space-y-2">
      {items.map((item) => (
        <div key={item} className={`${panelCard} p-3 text-sm leading-5 text-[#4a5168]`}>
          {item}
        </div>
      ))}
    </div>
  );
}

function EventList({ events }: { events: WorkspaceEvent[] }) {
  return (
    <div className="space-y-2">
      {events.map((event) => {
        let summary: string = event.type;
        if (event.type === "tool.call") summary = `${event.toolId} called`;
        if (event.type === "tool.result") summary = `${event.toolId}: ${event.summary}`;
        if (event.type === "canvas.object.updated") summary = `${event.objectKind} updated`;
        if (event.type === "approval.requested") summary = event.label;
        if (event.type === "user.message" || event.type === "assistant.message") summary = event.content;
        return (
          <div key={event.id} className={`${panelCard} p-3`}>
            <div className="text-[10px] font-semibold uppercase text-[#98a2b3]">{event.type}</div>
            <div className="mt-1 text-sm leading-5 text-[#344054]">{summary}</div>
          </div>
        );
      })}
    </div>
  );
}

function SourcePlaceholderSurface() {
  return (
    <div className="min-h-full bg-[#fcfdff]">
      <SurfaceHeader
        icon={<Database size={16} className="text-[#b86e00]" />}
        title="Sources"
        meta={`${trialFinderWorkspace.sourceGroups.length} groups`}
      />
      <div className="p-4">
        <InspectorList items={trialFinderWorkspace.sourceGroups.flatMap((group) => group.sources.map((source) => source.label))} />
      </div>
    </div>
  );
}

function ArtifactPlaceholderSurface() {
  return (
    <div className="min-h-full bg-[#fcfdff]">
      <SurfaceHeader
        icon={<ListChecks size={16} className="text-[#475569]" />}
        title="Artifacts"
        meta={`${mockArtifacts.length} files`}
      />
      <div className="p-4">
        <InspectorList items={mockArtifacts.map((artifact) => `${artifact.kind}: ${artifact.label}`)} />
      </div>
    </div>
  );
}

export function TrialFinderWorkspace() {
  const [selectedCandidateId, setSelectedCandidateId] = useState(mockCandidates[0].id);
  const selectedCandidate = mockCandidates.find((candidate) => candidate.id === selectedCandidateId) || mockCandidates[0];

  const renderSurface = (surface: WorkspaceSurfaceDefinition) => {
    if (surface.id === "chat") return <ChatSurface />;
    if (surface.id === "trial-candidates") {
      return <CandidateSurface selectedCandidateId={selectedCandidateId} onSelectCandidate={setSelectedCandidateId} />;
    }
    if (surface.id === "trial-detail") return <TrialDetailSurface candidate={selectedCandidate} />;
    if (surface.id === "pursuit-board") return <PursuitBoardSurface />;
    if (surface.id === "agent-inspector") return <InspectorSurface />;
    if (surface.role === "source") return <SourcePlaceholderSurface />;
    if (surface.role === "artifact") return <ArtifactPlaceholderSurface />;
    return null;
  };

  return (
    <WorkspaceFrame
      definition={trialFinderWorkspace}
      storageKey="ai-workspace:trial-finder:layout:v2"
      renderSurface={renderSurface}
    />
  );
}

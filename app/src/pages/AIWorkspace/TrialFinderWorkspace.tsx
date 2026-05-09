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
  if (!value) return "text-[#667085]";
  if (value >= 80) return "text-[#047857]";
  if (value >= 65) return "text-[#9a5a16]";
  return "text-[#b42318]";
}

function SurfaceHeader({ icon, title, description }: { icon: React.ReactNode; title: string; description: string }) {
  return (
    <div className="border-b border-[#eef2f6] bg-[#fbfcff] px-4 py-3">
      <div className="flex items-center gap-2 text-sm font-semibold text-[#1d2433]">
        {icon}
        {title}
      </div>
      <p className="mt-1 text-xs leading-5 text-[#667085]">{description}</p>
    </div>
  );
}

function ChatSurface() {
  return (
    <div className="flex h-full min-h-0 flex-col">
      <SurfaceHeader
        icon={<MessageSquareText size={16} className="text-[#5b76fe]" />}
        title="Agent Chat"
        description="Mock conversation surface. The future runtime streams assistant, tool, and checkpoint events here."
      />
      <div className="flex-1 space-y-3 overflow-auto p-4">
        {mockMessages.map((message) => (
          <div key={message.id} className={`flex gap-3 ${message.role === "user" ? "justify-end" : ""}`}>
            {message.role === "assistant" && (
              <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded bg-[#eef1ff] text-[#5b76fe]">
                <Bot size={16} />
              </div>
            )}
            <div
              className={`max-w-[82%] border px-3 py-2 text-sm leading-6 ${
                message.role === "user"
                  ? "border-[#cfd7ff] bg-[#f8f9ff] text-[#1d2433]"
                  : "border-[#e8edf3] bg-white text-[#344054]"
              }`}
            >
              <div>{message.content}</div>
              <div className="mt-1 text-[11px] font-medium text-[#98a2b3]">{message.at}</div>
            </div>
            {message.role === "user" && (
              <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded bg-[#f4f5f7] text-[#667085]">
                <UserRound size={16} />
              </div>
            )}
          </div>
        ))}
      </div>
      <div className="border-t border-[#eef2f6] p-3">
        <div className="mb-2 flex flex-wrap gap-2">
          {["Narrow to recruiting only", "Explain exclusion risks", "Draft site outreach"].map((label) => (
            <button
              key={label}
              type="button"
              className="rounded border border-[#dfe4ea] bg-white px-2.5 py-1.5 text-xs font-medium text-[#555a6a]"
            >
              {label}
            </button>
          ))}
        </div>
        <div className="flex items-center gap-2 border border-[#dfe4ea] bg-white px-3 py-2 text-sm text-[#98a2b3]">
          <Sparkles size={16} />
          Mock shell only. Backend session API is intentionally not wired yet.
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
    <div>
      <SurfaceHeader
        icon={<Search size={16} className="text-[#5b76fe]" />}
        title="Candidate Trials"
        description="Typed trial candidate objects rendered from fixtures. The agent will update this canvas through validated object events."
      />
      <div className="space-y-3 p-4">
        {mockCandidates.map((candidate) => {
          const selected = candidate.id === selectedCandidateId;
          return (
            <button
              key={candidate.id}
              type="button"
              onClick={() => onSelectCandidate(candidate.id)}
              className={`w-full border p-4 text-left transition ${
                selected ? "border-[#5b76fe] bg-[#f8f9ff]" : "border-[#e8edf3] bg-white hover:border-[#cfd7ff]"
              }`}
            >
              <div className="flex items-start justify-between gap-3">
                <div className="min-w-0">
                  <div className="text-xs font-semibold uppercase text-[#667085]">{candidate.nctId}</div>
                  <div className="mt-1 text-sm font-semibold leading-5 text-[#1d2433]">{candidate.title}</div>
                  <div className="mt-2 flex flex-wrap gap-1.5">
                    <span className="rounded bg-[#f5f7fb] px-2 py-1 text-xs font-medium text-[#667085]">{candidate.status}</span>
                    {candidate.phase && (
                      <span className="rounded bg-[#eef1ff] px-2 py-1 text-xs font-medium text-[#5b76fe]">{candidate.phase}</span>
                    )}
                    <span className={`rounded border px-2 py-1 text-xs font-semibold ${burdenTone(candidate.operationalBurden)}`}>
                      {candidate.operationalBurden} burden
                    </span>
                  </div>
                </div>
                <div className={`shrink-0 text-2xl font-semibold tabular-nums ${scoreTone(candidate.matchScore)}`}>
                  {percent(candidate.matchScore)}
                </div>
              </div>
              <div className="mt-3 grid gap-3 text-xs md:grid-cols-2">
                <div>
                  <div className="font-semibold text-[#047857]">Inclusion signal</div>
                  <div className="mt-1 text-[#667085]">{candidate.inclusionMatches[0]}</div>
                </div>
                <div>
                  <div className="font-semibold text-[#b42318]">Review risk</div>
                  <div className="mt-1 text-[#667085]">{candidate.exclusionRisks[0]}</div>
                </div>
              </div>
            </button>
          );
        })}
      </div>
    </div>
  );
}

function TrialDetailSurface({ candidate }: { candidate: TrialCandidate }) {
  return (
    <div>
      <SurfaceHeader
        icon={<FileText size={16} className="text-[#5b76fe]" />}
        title="Trial Detail"
        description="Focused candidate review: fit, mismatch risks, operational requirements, and source snapshots."
      />
      <div className="space-y-4 p-4">
        <div className="border border-[#e8edf3] bg-white p-4">
          <div className="text-xs font-semibold uppercase text-[#667085]">{candidate.nctId}</div>
          <h2 className="mt-1 text-lg font-semibold leading-6 text-[#111827]">{candidate.title}</h2>
          <div className="mt-3 flex flex-wrap gap-2 text-xs font-medium">
            {candidate.conditions.map((condition) => (
              <span key={condition} className="rounded bg-[#f5f7fb] px-2 py-1 text-[#667085]">
                {condition}
              </span>
            ))}
          </div>
        </div>

        <div className="grid gap-3">
          <DetailBlock
            title="Why it may fit"
            icon={<CheckCircle2 size={15} className="text-[#047857]" />}
            items={candidate.inclusionMatches}
          />
          <DetailBlock
            title="Why it may not fit"
            icon={<AlertTriangle size={15} className="text-[#b42318]" />}
            items={candidate.exclusionRisks}
          />
          <DetailBlock
            title="Operational requirements"
            icon={<MapPin size={15} className="text-[#5b76fe]" />}
            items={[
              `${candidate.operationalBurden} overall burden`,
              `${candidate.enrollment ?? "Unknown"} target enrollment`,
              "Site contact and source snapshot pending approval gate",
            ]}
          />
        </div>

        <div className="border border-[#e8edf3] bg-[#fbfcff] p-4">
          <div className="text-sm font-semibold text-[#1d2433]">User decisions</div>
          <div className="mt-3 grid gap-2 sm:grid-cols-3">
            {["Keep", "Ask clinician", "Defer"].map((label) => (
              <button key={label} type="button" className="rounded border border-[#dfe4ea] bg-white px-3 py-2 text-sm font-medium text-[#344054]">
                {label}
              </button>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}

function DetailBlock({ title, icon, items }: { title: string; icon: React.ReactNode; items: string[] }) {
  return (
    <div className="border border-[#e8edf3] bg-white p-4">
      <div className="flex items-center gap-2 text-sm font-semibold text-[#1d2433]">
        {icon}
        {title}
      </div>
      <ul className="mt-3 space-y-2 text-sm text-[#555a6a]">
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
    <div>
      <SurfaceHeader
        icon={<ClipboardList size={16} className="text-[#047857]" />}
        title="Pursuit Board"
        description="Durable project-management state for trials the user wants to actively consider."
      />
      <div className="flex gap-3 overflow-x-auto p-4">
        {PURSUIT_STATUSES.map((status) => (
          <div key={status} className="w-64 shrink-0 border border-[#e8edf3] bg-[#fbfcff]">
            <div className="border-b border-[#eef2f6] px-3 py-2 text-sm font-semibold capitalize text-[#1d2433]">
              {status}
            </div>
            <div className="space-y-2 p-3">
              {pursuitsByStatus[status].map((pursuit) => {
                const candidate = mockCandidates.find((item) => item.id === pursuit.candidateId);
                return (
                  <div key={pursuit.id} className="border border-[#e8edf3] bg-white p-3">
                    <div className="text-xs font-semibold uppercase text-[#667085]">{candidate?.nctId}</div>
                    <div className="mt-1 text-sm font-semibold leading-5 text-[#1d2433]">{candidate?.title}</div>
                    <div className="mt-3 text-xs text-[#667085]">{pursuit.tasks.filter((task) => task.status === "open").length} open tasks</div>
                  </div>
                );
              })}
              {pursuitsByStatus[status].length === 0 && (
                <div className="border border-dashed border-[#dfe4ea] bg-white p-3 text-xs text-[#98a2b3]">No trials</div>
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
    <div>
      <SurfaceHeader
        icon={<ShieldCheck size={16} className="text-[#6d28d9]" />}
        title="Agent Inspector"
        description="Trust and control surface for active tools, context, sources, events, artifacts, and approvals."
      />
      <div className="border-b border-[#eef2f6] px-3 py-2">
        <div className="flex gap-1 overflow-x-auto">
          {tabs.map((item) => (
            <button
              key={item}
              type="button"
              onClick={() => setTab(item)}
              className={`rounded px-2.5 py-1.5 text-xs font-semibold ${
                tab === item ? "bg-[#f4ecff] text-[#6d28d9]" : "text-[#667085] hover:bg-[#f5f6f8]"
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
        <InspectorRow icon={<LockKeyhole size={15} />} label="State" value="Mock shell; no backend writes" />
      </div>
    );
  }
  if (tab === "Tools") {
    return <InspectorList items={trialFinderWorkspace.tools.map((tool) => `${tool.label} - ${tool.permission}`)} />;
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
          <div key={group.id} className="border border-[#e8edf3] bg-white p-3">
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
    <div className="flex items-start gap-3 border border-[#e8edf3] bg-white p-3">
      <div className="mt-0.5 text-[#667085]">{icon}</div>
      <div className="min-w-0">
        <div className="text-xs font-semibold uppercase text-[#98a2b3]">{label}</div>
        <div className="mt-1 break-words text-sm font-medium text-[#1d2433]">{value}</div>
      </div>
    </div>
  );
}

function InspectorList({ items }: { items: string[] }) {
  return (
    <div className="space-y-2">
      {items.map((item) => (
        <div key={item} className="border border-[#e8edf3] bg-white p-3 text-sm leading-5 text-[#4a5168]">
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
          <div key={event.id} className="border border-[#e8edf3] bg-white p-3">
            <div className="text-xs font-semibold uppercase text-[#98a2b3]">{event.type}</div>
            <div className="mt-1 text-sm leading-5 text-[#344054]">{summary}</div>
          </div>
        );
      })}
    </div>
  );
}

function SourcePlaceholderSurface() {
  return (
    <div>
      <SurfaceHeader
        icon={<Database size={16} className="text-[#b86e00]" />}
        title="Sources"
        description="Source snapshots will render here in the backend-backed build."
      />
      <div className="p-4">
        <InspectorList items={trialFinderWorkspace.sourceGroups.flatMap((group) => group.sources.map((source) => source.label))} />
      </div>
    </div>
  );
}

function ArtifactPlaceholderSurface() {
  return (
    <div>
      <SurfaceHeader
        icon={<ListChecks size={16} className="text-[#475569]" />}
        title="Artifacts"
        description="Generated packets, markdown, source snapshots, and exports will live here."
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
      storageKey="ai-workspace:trial-finder:layout:v1"
      renderSurface={renderSurface}
    />
  );
}

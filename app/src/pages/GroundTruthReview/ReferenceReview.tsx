import { useEffect, useMemo, useRef, useState } from "react";
import type { PointerEvent as ReactPointerEvent, ReactNode } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  ArrowLeft,
  Check,
  ChevronsLeft,
  ChevronsRight,
  ChevronRight,
  CircleHelp,
  Code2,
  FileJson2,
  FileText,
  Loader2,
  Save,
  Search,
  Send,
  Sparkles,
  Table2,
  ZoomIn,
  ZoomOut,
  X,
} from "lucide-react";
import { api } from "../../api/client";
import type {
  GroundTruthReviewFactDecision,
  GroundTruthReviewFactStatus,
  GroundTruthReviewFactSummary,
  GroundTruthReviewPdfTextMatch,
  GroundTruthReviewProgress,
  GroundTruthReviewReasonCode,
  GroundTruthReviewSession,
} from "../../types";

const RESOURCE_ORDER = [
  "Patient",
  "Observation",
  "Condition",
  "MedicationRequest",
  "Encounter",
  "Procedure",
  "Immunization",
  "AllergyIntolerance",
  "DocumentReference",
  "Composition",
];

const REASON_LABELS: { code: GroundTruthReviewReasonCode; label: string }[] = [
  { code: "wrong_value", label: "Wrong value" },
  { code: "wrong_code", label: "Wrong code" },
  { code: "wrong_date", label: "Wrong date" },
  { code: "wrong_unit", label: "Wrong unit" },
  { code: "wrong_status", label: "Wrong status" },
  { code: "wrong_linkage", label: "Wrong linkage" },
  { code: "unsupported_by_pdf", label: "Unsupported" },
  { code: "missing_from_output", label: "Missing" },
];

type ReviewPane = "pdf" | "facts" | "detail";

function nowIso() {
  return new Date().toISOString();
}

function newId(prefix: string) {
  if ("crypto" in window && "randomUUID" in window.crypto) {
    return `${prefix}-${window.crypto.randomUUID()}`;
  }
  return `${prefix}-${Date.now()}-${Math.random().toString(16).slice(2)}`;
}

function pct(part: number, total: number) {
  if (!total) return 0;
  return Math.round((part / total) * 100);
}

function decisionLabel(status?: GroundTruthReviewFactStatus) {
  if (!status) return "Needs review";
  return status.replaceAll("_", " ");
}

function statusClass(status?: GroundTruthReviewFactStatus) {
  if (status === "accepted") return "border-[#b7e4cd] bg-[#ecfdf3] text-[#027a48]";
  if (status === "rejected" || status === "unsupported" || status === "duplicate") return "border-[#fecaca] bg-[#fff1f1] text-[#b42318]";
  if (status === "edited") return "border-[#bfdbfe] bg-[#eff6ff] text-[#175cd3]";
  if (status === "uncertain" || status === "needs_follow_up") return "border-[#fedf89] bg-[#fffaeb] text-[#b54708]";
  if (status === "missing") return "border-[#e9d7fe] bg-[#f9f5ff] text-[#6941c6]";
  return "border-[#dfe4ea] bg-white text-[#667085]";
}

function computeProgress(review: GroundTruthReviewSession | null, facts: GroundTruthReviewFactSummary[]): GroundTruthReviewProgress {
  const counts = new Map<GroundTruthReviewFactStatus, number>();
  for (const decision of review?.decisions ?? []) {
    counts.set(decision.status, (counts.get(decision.status) ?? 0) + 1);
  }
  const reviewedFacts = (review?.decisions ?? []).filter((decision) => decision.status !== "missing").length;
  const rejectedFacts =
    (counts.get("rejected") ?? 0) + (counts.get("unsupported") ?? 0) + (counts.get("duplicate") ?? 0);
  const uncertainFacts = (counts.get("uncertain") ?? 0) + (counts.get("needs_follow_up") ?? 0);
  return {
    total_facts: facts.length,
    reviewed_facts: reviewedFacts,
    accepted_facts: counts.get("accepted") ?? 0,
    rejected_facts: rejectedFacts,
    edited_facts: counts.get("edited") ?? 0,
    uncertain_facts: uncertainFacts,
    missing_facts: counts.get("missing") ?? 0,
    needs_review: Math.max(facts.length - reviewedFacts, 0),
  };
}

function resourceTypes(facts: GroundTruthReviewFactSummary[]) {
  const present = new Set(facts.map((fact) => fact.resource_type));
  return [
    ...RESOURCE_ORDER.filter((type) => present.has(type)),
    ...Array.from(present).filter((type) => !RESOURCE_ORDER.includes(type)).sort(),
  ];
}

function sortedFacts(facts: GroundTruthReviewFactSummary[]) {
  const order = new Map(RESOURCE_ORDER.map((type, index) => [type, index]));
  return [...facts].sort((a, b) => {
    const ai = order.get(a.resource_type) ?? 999;
    const bi = order.get(b.resource_type) ?? 999;
    if (ai !== bi) return ai - bi;
    return a.display.localeCompare(b.display);
  });
}

function RunList() {
  const navigate = useNavigate();
  const [query, setQuery] = useState("");
  const { data: runs = [], isLoading, error } = useQuery({
    queryKey: ["ground-truth-review-runs"],
    queryFn: api.listGroundTruthReviewRuns,
  });

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return runs;
    return runs.filter((run) =>
      [run.run_id, run.pipeline_name, run.pdf_label, run.pdf_sha256 ?? ""].some((value) =>
        value.toLowerCase().includes(q),
      ),
    );
  }, [query, runs]);

  return (
    <div className="mx-auto flex min-h-[calc(100vh-170px)] w-full max-w-[1500px] flex-col gap-3">
      <section className="flex flex-wrap items-center justify-between gap-3 border-b border-[#d7e9e4] pb-3">
        <div>
          <p className="text-xs font-semibold uppercase tracking-wider text-[#0f766e]">Reference Review</p>
          <h1 className="mt-1 text-2xl font-semibold tracking-tight text-[#0f172a]">Review candidate bundles</h1>
          <p className="mt-1 max-w-3xl text-sm leading-6 text-[#55706c]">
            Model-generated candidate output becomes a reviewed reference bundle only after this human review and versioned publish step.
          </p>
        </div>
        <Link
          to="/learn/pipeline-lab"
          className="inline-flex items-center gap-2 rounded-lg border border-[#cdeee9] bg-white px-3 py-2 text-sm font-semibold text-[#0f766e] hover:bg-[#f4fffc]"
        >
          <ArrowLeft size={15} />
          Pipeline Lab
        </Link>
      </section>

      <div className="flex items-center gap-2 rounded-lg border border-[#cdeee9] bg-white px-3 py-2">
        <Search size={16} className="text-[#55706c]" />
        <input
          value={query}
          onChange={(event) => setQuery(event.target.value)}
          placeholder="Search run, pipeline, PDF, or SHA..."
          className="flex-1 bg-transparent text-sm text-[#0f172a] outline-none placeholder:text-[#8aa19d]"
        />
      </div>

      <section className="min-h-0 overflow-hidden rounded-lg border border-[#cdeee9] bg-white">
        <div className="grid grid-cols-[minmax(260px,1fr)_160px_120px_140px_120px] border-b border-[#e5f1ee] bg-[#f7fffc] px-3 py-2 text-xs font-semibold uppercase tracking-wider text-[#55706c]">
          <div>Run</div>
          <div>Pipeline</div>
          <div>Facts</div>
          <div>Review</div>
          <div>Reference</div>
        </div>
        <div className="max-h-[66vh] overflow-y-auto">
          {isLoading && <div className="p-6 text-sm text-[#55706c]">Loading reviewable runs...</div>}
          {error && <div className="p-6 text-sm text-[#b42318]">Could not load review runs.</div>}
          {!isLoading && filtered.length === 0 && (
            <div className="p-6 text-sm text-[#55706c]">No reviewable pipeline runs found.</div>
          )}
          {filtered.map((run) => (
            <button
              key={run.run_id}
              type="button"
              onClick={() => navigate(`/ground-truth-review/${encodeURIComponent(run.run_id)}`)}
              className="grid w-full grid-cols-[minmax(260px,1fr)_160px_120px_140px_120px] items-center border-b border-[#eef5f3] px-3 py-3 text-left text-sm hover:bg-[#f7fffc]"
            >
              <div className="min-w-0">
                <p className="truncate font-semibold text-[#0f172a]">{run.pdf_label}</p>
                <p className="mt-0.5 truncate text-xs text-[#55706c]">{run.run_id}</p>
              </div>
              <div className="truncate text-[#344054]">{run.pipeline_name}</div>
              <div className="font-medium text-[#0f172a]">{run.total_entries.toLocaleString()}</div>
              <div>
                <span className={`rounded-full border px-2 py-1 text-xs font-semibold ${statusClass(run.review_status === "not_started" ? undefined : run.review_status === "published" ? "accepted" : "uncertain")}`}>
                  {run.review_status === "not_started" ? "Not started" : run.review_status}
                </span>
                {run.reviewed_facts > 0 && <p className="mt-1 text-xs text-[#55706c]">{run.reviewed_facts} decisions</p>}
              </div>
              <div className="text-xs text-[#55706c]">
                {run.published_ground_truth_version
                  ? `v${run.published_ground_truth_version}`
                  : run.existing_ground_truth_versions.length
                    ? `${run.existing_ground_truth_versions.length} versions`
                    : "None"}
              </div>
            </button>
          ))}
        </div>
      </section>
    </div>
  );
}

function ReferenceReviewWorkspace({ runId }: { runId: string }) {
  const queryClient = useQueryClient();
  const [selectedRef, setSelectedRef] = useState<string | null>(null);
  const [typeFilter, setTypeFilter] = useState<string>("All");
  const [factQuery, setFactQuery] = useState("");
  const [review, setReview] = useState<GroundTruthReviewSession | null>(null);
  const [dirty, setDirty] = useState(false);
  const [editorOpen, setEditorOpen] = useState(false);
  const [jsonDraft, setJsonDraft] = useState("");
  const [jsonError, setJsonError] = useState<string | null>(null);
  const [pdfPage, setPdfPage] = useState(1);
  const [pdfZoom, setPdfZoom] = useState(0.72);
  const [openPanes, setOpenPanes] = useState<Record<ReviewPane, boolean>>({ pdf: true, facts: true, detail: true });
  const [paneWidths, setPaneWidths] = useState<Record<ReviewPane, number>>({ pdf: 34, facts: 42, detail: 24 });
  const [pdfMatches, setPdfMatches] = useState<GroundTruthReviewPdfTextMatch[]>([]);
  const [locationQuery, setLocationQuery] = useState("");
  const [locatorVersion, setLocatorVersion] = useState("");
  const noteRef = useRef<HTMLTextAreaElement>(null);

  const { data, isLoading, error } = useQuery({
    queryKey: ["ground-truth-review-run", runId],
    queryFn: () => api.getGroundTruthReviewRun(runId),
  });

  const { data: pdfPages, isLoading: pdfPagesLoading } = useQuery({
    queryKey: ["ground-truth-review-pdf-pages", runId],
    queryFn: () => api.getGroundTruthReviewPdfPages(runId),
  });

  useEffect(() => {
    if (!data) return;
    setReview(data.review);
    setDirty(false);
    setSelectedRef((current) => current ?? data.facts[0]?.resource_ref ?? null);
  }, [data]);

  useEffect(() => {
    setPdfMatches([]);
    setLocationQuery("");
    setLocatorVersion("");
  }, [selectedRef]);

  const decisionsByRef = useMemo(() => {
    const map = new Map<string, GroundTruthReviewFactDecision>();
    for (const decision of review?.decisions ?? []) map.set(decision.resource_ref, decision);
    return map;
  }, [review]);

  const facts = useMemo(() => sortedFacts(data?.facts ?? []), [data?.facts]);
  const visibleFacts = useMemo(() => {
    const q = factQuery.trim().toLowerCase();
    return facts.filter((fact) => {
      if (typeFilter !== "All" && fact.resource_type !== typeFilter) return false;
      if (!q) return true;
      return [
        fact.display,
        fact.value ?? "",
        fact.date ?? "",
        fact.status ?? "",
        fact.resource_ref,
        fact.codes.join(" "),
      ].some((value) => value.toLowerCase().includes(q));
    });
  }, [factQuery, facts, typeFilter]);
  const selectedFact = facts.find((fact) => fact.resource_ref === selectedRef) ?? facts[0] ?? null;
  const selectedDecision = selectedFact ? decisionsByRef.get(selectedFact.resource_ref) : undefined;
  const progress = useMemo(() => computeProgress(review, facts), [review, facts]);
  const completion = pct(progress.reviewed_facts, progress.total_facts);
  const currentPdfPage = pdfPages?.pages.find((page) => page.page_number === pdfPage) ?? pdfPages?.pages[0] ?? null;
  const pageMatches = pdfMatches.filter((match) => match.page_number === currentPdfPage?.page_number);
  const activePanes = (["pdf", "facts", "detail"] as ReviewPane[]).filter((pane) => openPanes[pane]);
  const workspaceColumns = activePanes.length
    ? activePanes.map((pane) => `minmax(${pane === "facts" ? 420 : pane === "pdf" ? 360 : 300}px, ${paneWidths[pane]}fr)`).join(" 10px ")
    : "1fr";

  const saveMutation = useMutation({
    mutationFn: (nextReview: GroundTruthReviewSession) => api.saveGroundTruthReview(runId, nextReview),
    onSuccess: (saved) => {
      setReview(saved);
      setDirty(false);
      void queryClient.invalidateQueries({ queryKey: ["ground-truth-review-runs"] });
    },
  });

  const publishMutation = useMutation({
    mutationFn: async (currentReview: GroundTruthReviewSession) => {
      const saved = await api.saveGroundTruthReview(runId, currentReview);
      return api.publishGroundTruthReview(runId, { reviewer: saved.reviewer, notes: saved.notes });
    },
    onSuccess: (result) => {
      setReview(result.review);
      setDirty(false);
      void queryClient.invalidateQueries({ queryKey: ["ground-truth-review-run", runId] });
      void queryClient.invalidateQueries({ queryKey: ["ground-truth-review-runs"] });
    },
  });

  const locateMutation = useMutation({
    mutationFn: (fact: GroundTruthReviewFactSummary) => api.locateGroundTruthReviewFact(runId, fact.resource_ref),
    onSuccess: (result) => {
      setPdfMatches(result.matches);
      setLocationQuery(result.query);
      setLocatorVersion(result.locator_version);
      const first = result.matches[0];
      if (first) {
        setPdfPage(first.page_number);
        setOpenPanes((current) => ({ ...current, pdf: true }));
      }
    },
  });

  const updateReview = (updater: (current: GroundTruthReviewSession) => GroundTruthReviewSession) => {
    setReview((current) => {
      if (!current) return current;
      const next = updater(current);
      setDirty(true);
      return next;
    });
  };

  const upsertDecision = (
    fact: GroundTruthReviewFactSummary,
    status: GroundTruthReviewFactStatus,
    patch: Partial<GroundTruthReviewFactDecision> = {},
  ) => {
    updateReview((current) => {
      const existing = current.decisions.find((decision) => decision.resource_ref === fact.resource_ref);
      const timestamp = nowIso();
      const nextDecision: GroundTruthReviewFactDecision = {
        decision_id: existing?.decision_id ?? newId("decision"),
        resource_ref: fact.resource_ref,
        resource_type: fact.resource_type,
        resource_id: fact.resource_id,
        status,
        reason_codes: existing?.reason_codes ?? [],
        original_resource: existing?.original_resource ?? fact.original_resource,
        edited_resource: existing?.edited_resource ?? null,
        reviewer_note: existing?.reviewer_note ?? "",
        linked_annotation_ids: existing?.linked_annotation_ids ?? [],
        created_at: existing?.created_at ?? timestamp,
        updated_at: timestamp,
        ...patch,
      };
      return {
        ...current,
        status: "draft",
        updated_at: timestamp,
        decisions: existing
          ? current.decisions.map((decision) => (decision.resource_ref === fact.resource_ref ? nextDecision : decision))
          : [...current.decisions, nextDecision],
      };
    });
  };

  const saveNow = () => {
    if (review) saveMutation.mutate(review);
  };

  const togglePane = (pane: ReviewPane) => {
    setOpenPanes((current) => ({ ...current, [pane]: !current[pane] }));
  };

  const startResize = (left: ReviewPane, right: ReviewPane, event: ReactPointerEvent<HTMLDivElement>) => {
    const container = event.currentTarget.parentElement;
    if (!container) return;
    event.preventDefault();
    const startX = event.clientX;
    const startLeft = paneWidths[left];
    const startRight = paneWidths[right];
    const totalPair = startLeft + startRight;
    const containerWidth = container.getBoundingClientRect().width;

    const onMove = (moveEvent: PointerEvent) => {
      const delta = ((moveEvent.clientX - startX) / Math.max(containerWidth, 1)) * 100;
      const nextLeft = Math.min(Math.max(startLeft + delta, 14), totalPair - 14);
      const nextRight = totalPair - nextLeft;
      setPaneWidths((current) => ({ ...current, [left]: nextLeft, [right]: nextRight }));
    };
    const onUp = () => {
      window.removeEventListener("pointermove", onMove);
      window.removeEventListener("pointerup", onUp);
    };
    window.addEventListener("pointermove", onMove);
    window.addEventListener("pointerup", onUp);
  };

  const moveSelection = (delta: number) => {
    if (!visibleFacts.length) return;
    const currentIndex = Math.max(visibleFacts.findIndex((fact) => fact.resource_ref === selectedRef), 0);
    const nextIndex = Math.min(Math.max(currentIndex + delta, 0), visibleFacts.length - 1);
    setSelectedRef(visibleFacts[nextIndex].resource_ref);
  };

  const openEditor = () => {
    if (!selectedFact) return;
    setJsonDraft(JSON.stringify(selectedDecision?.edited_resource ?? selectedFact.original_resource, null, 2));
    setJsonError(null);
    setEditorOpen(true);
  };

  useEffect(() => {
    function onKeyDown(event: KeyboardEvent) {
      const tag = (event.target as HTMLElement | null)?.tagName;
      if (tag === "INPUT" || tag === "TEXTAREA" || tag === "SELECT") return;
      if (!selectedFact) return;
      if (event.key === "a" || event.key === "A") upsertDecision(selectedFact, "accepted");
      if (event.key === "r" || event.key === "R") upsertDecision(selectedFact, "rejected");
      if (event.key === "u" || event.key === "U") upsertDecision(selectedFact, "uncertain");
      if (event.key === "e" || event.key === "E") openEditor();
      if (event.key === "n" || event.key === "N") noteRef.current?.focus();
      if (event.key === "ArrowDown") moveSelection(1);
      if (event.key === "ArrowUp") moveSelection(-1);
    }
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  });

  if (isLoading) {
    return <div className="p-8 text-sm text-[#55706c]">Loading review workspace...</div>;
  }

  if (error || !data || !review) {
    return <div className="p-8 text-sm text-[#b42318]">Could not load this review run.</div>;
  }

  return (
    <div className="flex h-[calc(100vh-150px)] min-h-[720px] flex-col gap-3">
      <header className="flex shrink-0 flex-wrap items-center justify-between gap-3 border-b border-[#d7e9e4] pb-3">
        <div className="min-w-0">
          <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-[#0f766e]">
            <Link to="/learn/ground-truth-review" className="inline-flex items-center gap-1 hover:text-[#064e3b]">
              <ArrowLeft size={13} />
              Reference Review
            </Link>
            <ChevronRight size={13} />
            <span>Candidate Bundle</span>
          </div>
          <h1 className="mt-1 truncate text-xl font-semibold tracking-tight text-[#0f172a]">{data.run.pdf_label}</h1>
          <p className="mt-1 truncate text-xs text-[#55706c]">
            {data.run.pipeline_name} · {data.run.run_id} · {data.run.pdf_sha256?.slice(0, 12)}
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <div className="min-w-[220px] rounded-lg border border-[#cdeee9] bg-white px-3 py-2">
            <div className="flex items-center justify-between text-xs text-[#55706c]">
              <span>Review Progress</span>
              <span className="font-semibold text-[#0f172a]">{completion}%</span>
            </div>
            <div className="mt-2 h-2 overflow-hidden rounded-full bg-[#e5f1ee]">
              <div className="h-full bg-[#0f766e]" style={{ width: `${completion}%` }} />
            </div>
          </div>
          <button
            type="button"
            onClick={saveNow}
            disabled={!dirty || saveMutation.isPending}
            className="inline-flex items-center gap-2 rounded-lg border border-[#cdeee9] bg-white px-3 py-2 text-sm font-semibold text-[#0f766e] disabled:cursor-not-allowed disabled:opacity-50"
          >
            {saveMutation.isPending ? <Loader2 size={15} className="animate-spin" /> : <Save size={15} />}
            {dirty ? "Save Draft" : "Saved"}
          </button>
          <button
            type="button"
            onClick={() => publishMutation.mutate(review)}
            disabled={publishMutation.isPending || progress.reviewed_facts === 0}
            className="inline-flex items-center gap-2 rounded-lg bg-[#0f766e] px-3 py-2 text-sm font-semibold text-white disabled:cursor-not-allowed disabled:opacity-50"
          >
            {publishMutation.isPending ? <Loader2 size={15} className="animate-spin" /> : <Send size={15} />}
            Publish Reference Version
          </button>
        </div>
      </header>

      <div className="flex shrink-0 items-center gap-2">
        {(["pdf", "facts", "detail"] as ReviewPane[]).map((pane) => (
          <button
            key={pane}
            type="button"
            onClick={() => togglePane(pane)}
            className={`inline-flex items-center gap-2 rounded-lg border px-3 py-1.5 text-xs font-semibold capitalize ${
              openPanes[pane] ? "border-[#0f766e] bg-[#e7fbf7] text-[#0f766e]" : "border-[#dfe4ea] bg-white text-[#667085]"
            }`}
          >
            {openPanes[pane] ? <ChevronsLeft size={13} /> : <ChevronsRight size={13} />}
            {pane === "pdf" ? "Source PDF" : pane === "facts" ? "Extracted facts" : "Fact detail"}
          </button>
        ))}
      </div>

      <div className="grid min-h-0 flex-1 gap-3" style={{ gridTemplateColumns: workspaceColumns }}>
        {activePanes.includes("pdf") && (
          <section className="flex min-h-0 flex-col overflow-hidden rounded-lg border border-[#cdeee9] bg-white">
            <PaneHeader
              icon={<FileText size={16} className="text-[#0f766e]" />}
              title="Source PDF"
              onCollapse={() => togglePane("pdf")}
            >
              <div className="flex items-center gap-1">
                <button type="button" onClick={() => setPdfPage((page) => Math.max(1, page - 1))} disabled={pdfPage <= 1} className="rounded-md border border-[#cdeee9] bg-white px-2 py-1 text-xs font-semibold text-[#0f766e] disabled:opacity-40">Prev</button>
                <span className="min-w-20 text-center text-xs font-medium text-[#55706c]">{pdfPagesLoading ? "Pages..." : `${pdfPage} / ${pdfPages?.page_count ?? 1}`}</span>
                <button type="button" onClick={() => setPdfPage((page) => Math.min(pdfPages?.page_count ?? page, page + 1))} disabled={pdfPage >= (pdfPages?.page_count ?? 1)} className="rounded-md border border-[#cdeee9] bg-white px-2 py-1 text-xs font-semibold text-[#0f766e] disabled:opacity-40">Next</button>
                <button type="button" onClick={() => setPdfZoom((zoom) => Math.max(0.42, Number((zoom - 0.1).toFixed(2))))} className="ml-1 inline-flex h-7 w-7 items-center justify-center rounded-md border border-[#cdeee9] bg-white text-[#0f766e]" title="Zoom out"><ZoomOut size={14} /></button>
                <button type="button" onClick={() => setPdfZoom((zoom) => Math.min(1.6, Number((zoom + 0.1).toFixed(2))))} className="inline-flex h-7 w-7 items-center justify-center rounded-md border border-[#cdeee9] bg-white text-[#0f766e]" title="Zoom in"><ZoomIn size={14} /></button>
                <a href={data.artifact_urls.pdf} target="_blank" rel="noreferrer" className="ml-1 text-xs font-semibold text-[#0f766e] hover:underline">Raw</a>
              </div>
            </PaneHeader>
            <div className="min-h-0 flex-1 overflow-auto bg-[#dfe9e6] p-4">
              {pdfPagesLoading && <div className="flex h-full items-center justify-center text-sm text-[#55706c]">Rendering PDF pages...</div>}
              {!pdfPagesLoading && !currentPdfPage && <div className="flex h-full items-center justify-center text-sm text-[#b42318]">No rendered PDF page is available.</div>}
              {currentPdfPage && (
                <div className="mx-auto w-max">
                  <div className="relative bg-white shadow-[0_12px_32px_rgba(15,23,42,0.18)]" style={{ width: Math.round(currentPdfPage.width * pdfZoom), height: Math.round(currentPdfPage.height * pdfZoom) }}>
                    <img src={currentPdfPage.image_url} alt={`PDF page ${currentPdfPage.page_number}`} className="h-full w-full select-none object-contain" draggable={false} />
                    {pageMatches.map((match, index) => (
                      <button
                        key={`${match.page_number}-${index}-${match.bbox.x}`}
                        type="button"
                        title={`${match.confidence} confidence · ${Math.round(match.score * 100)}% · ${match.text}`}
                        className="absolute border-2 border-[#f79009] bg-[#fdb022]/30 shadow-[0_0_0_1px_rgba(255,255,255,0.7)]"
                        style={{
                          left: `${match.bbox.x * 100}%`,
                          top: `${match.bbox.y * 100}%`,
                          width: `${match.bbox.width * 100}%`,
                          height: `${match.bbox.height * 100}%`,
                        }}
                      />
                    ))}
                    <div className="pointer-events-none absolute left-2 top-2 rounded bg-white/90 px-2 py-1 text-[11px] font-semibold text-[#344054] shadow-sm">
                      Page {currentPdfPage.page_number}
                    </div>
                  </div>
                </div>
              )}
            </div>
            {(pdfMatches.length > 0 || locationQuery) && (
              <div className="shrink-0 border-t border-[#e5f1ee] bg-white px-3 py-2 text-xs text-[#55706c]">
                <span className="font-semibold text-[#0f172a]">{pdfMatches.length}</span> candidate evidence regions
                {locationQuery && <span> for "{locationQuery.slice(0, 80)}"</span>}
                {locatorVersion && <span className="ml-2 text-[#8aa19d]">· {locatorVersion}</span>}
              </div>
            )}
          </section>
        )}

        {activePanes.includes("pdf") && activePanes.includes("facts") && (
          <ResizeHandle onPointerDown={(event) => startResize("pdf", "facts", event)} />
        )}

        {activePanes.includes("facts") && (
          <section className="flex min-h-0 flex-col overflow-hidden rounded-lg border border-[#cdeee9] bg-white">
            <PaneHeader
              icon={<Table2 size={16} className="text-[#0f766e]" />}
              title={`Extracted Facts (${visibleFacts.length})`}
              onCollapse={() => togglePane("facts")}
            >
              <select value={typeFilter} onChange={(event) => setTypeFilter(event.target.value)} className="rounded-md border border-[#cdeee9] bg-white px-2 py-1.5 text-xs text-[#0f172a] outline-none">
                <option>All</option>
                {resourceTypes(facts).map((type) => <option key={type}>{type}</option>)}
              </select>
            </PaneHeader>
            <div className="flex shrink-0 items-center gap-2 border-b border-[#e5f1ee] bg-white px-3 py-2">
              <Search size={14} className="text-[#55706c]" />
              <input
                value={factQuery}
                onChange={(event) => setFactQuery(event.target.value)}
                placeholder="Search extracted facts, values, dates, codes..."
                className="min-w-0 flex-1 bg-transparent text-sm text-[#0f172a] outline-none placeholder:text-[#8aa19d]"
              />
            </div>
            <div className="min-h-0 flex-1 overflow-auto">
              <table className="min-w-[860px] border-separate border-spacing-0 text-left text-sm">
                <thead className="sticky top-0 z-10 bg-[#f7fffc] text-[#55706c]">
                  <tr>
                    <th className="w-[46%] border-b border-[#e5f1ee] px-4 py-2 font-semibold">Fact</th>
                    <th className="w-[28%] border-b border-[#e5f1ee] px-4 py-2 font-semibold">Extracted Fields</th>
                    <th className="w-[16%] border-b border-[#e5f1ee] px-4 py-2 font-semibold">Review</th>
                    <th className="w-[10%] border-b border-[#e5f1ee] px-4 py-2 font-semibold">PDF</th>
                  </tr>
                </thead>
                <tbody>
                  {visibleFacts.map((fact) => {
                    const decision = decisionsByRef.get(fact.resource_ref);
                    const active = fact.resource_ref === selectedFact?.resource_ref;
                    return (
                      <tr key={fact.resource_ref} onClick={() => setSelectedRef(fact.resource_ref)} className={`cursor-pointer border-b border-[#eef5f3] ${active ? "bg-[#e7fbf7]" : "hover:bg-[#f7fffc]"}`}>
                        <td className="border-b border-[#eef5f3] px-4 py-3 align-top">
                          <div className="mb-1 flex items-center gap-2">
                            <span className="rounded-full border border-[#cdeee9] bg-[#f4fffc] px-2 py-0.5 text-[11px] font-semibold text-[#0f766e]">{fact.resource_type}</span>
                            <span className="truncate text-[11px] text-[#667085]">{fact.resource_id ?? fact.resource_ref}</span>
                          </div>
                          <p className="whitespace-normal break-words font-semibold leading-5 text-[#0f172a]">{fact.display}</p>
                          <p className="mt-1 whitespace-normal break-words text-xs leading-5 text-[#667085]">{fact.codes.slice(0, 2).join(" · ") || "No code surfaced"}</p>
                        </td>
                        <td className="border-b border-[#eef5f3] px-4 py-3 align-top text-[#344054]">
                          <div className="grid gap-1 text-xs leading-5">
                            <div><span className="font-semibold text-[#667085]">Value:</span> {fact.value ?? "—"}</div>
                            <div><span className="font-semibold text-[#667085]">Date:</span> {fact.date ?? "—"}</div>
                            <div><span className="font-semibold text-[#667085]">Status:</span> {fact.status ?? "—"}</div>
                          </div>
                        </td>
                        <td className="border-b border-[#eef5f3] px-4 py-3 align-top">
                          <span className={`rounded-full border px-2 py-1 text-[11px] font-semibold capitalize ${statusClass(decision?.status)}`}>{decisionLabel(decision?.status)}</span>
                        </td>
                        <td className="border-b border-[#eef5f3] px-4 py-3 align-top">
                          <button
                            type="button"
                            onClick={(event) => {
                              event.stopPropagation();
                              setSelectedRef(fact.resource_ref);
                              locateMutation.mutate(fact);
                            }}
                            className="inline-flex items-center gap-1 rounded-md border border-[#cdeee9] bg-white px-2 py-1 font-semibold text-[#0f766e] hover:bg-[#f4fffc]"
                          >
                            <Sparkles size={12} />
                            Find
                          </button>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </section>
        )}

        {activePanes.includes("facts") && activePanes.includes("detail") && (
          <ResizeHandle onPointerDown={(event) => startResize("facts", "detail", event)} />
        )}
        {activePanes.includes("pdf") && !activePanes.includes("facts") && activePanes.includes("detail") && (
          <ResizeHandle onPointerDown={(event) => startResize("pdf", "detail", event)} />
        )}

        {activePanes.includes("detail") && (
          <section className="flex min-h-0 flex-col overflow-hidden rounded-lg border border-[#cdeee9] bg-white">
            <PaneHeader
              icon={<FileJson2 size={16} className="text-[#0f766e]" />}
              title="Fact Detail"
              onCollapse={() => togglePane("detail")}
            />
            {selectedFact ? (
              <>
                <div className="shrink-0 border-b border-[#e5f1ee] bg-[#f7fffc] px-4 py-3">
                  <div className="flex items-start justify-between gap-3">
                    <div className="min-w-0">
                      <p className="text-xs font-semibold uppercase tracking-wider text-[#0f766e]">{selectedFact.resource_type}</p>
                      <h2 className="mt-1 text-base font-semibold text-[#0f172a]">{selectedFact.display}</h2>
                      <p className="mt-1 text-xs text-[#55706c]">{selectedFact.resource_ref}</p>
                    </div>
                    <span className={`shrink-0 rounded-full border px-2 py-1 text-xs font-semibold capitalize ${statusClass(selectedDecision?.status)}`}>{decisionLabel(selectedDecision?.status)}</span>
                  </div>
                  <div className="mt-3 grid grid-cols-2 gap-2 text-xs">
                    <Metric label="Value" value={selectedFact.value ?? "—"} />
                    <Metric label="Date" value={selectedFact.date ?? "—"} />
                    <Metric label="Status" value={selectedFact.status ?? "—"} />
                    <Metric label="Encounter" value={selectedFact.encounter_ref ?? "—"} />
                  </div>
                </div>
                <div className="min-h-0 flex-1 overflow-y-auto px-4 py-3">
                  <div className="flex flex-wrap gap-2">
                    <DecisionButton label="Accept" icon={<Check size={14} />} active={selectedDecision?.status === "accepted"} onClick={() => upsertDecision(selectedFact, "accepted")} />
                    <DecisionButton label="Reject" icon={<X size={14} />} active={selectedDecision?.status === "rejected"} danger onClick={() => upsertDecision(selectedFact, "rejected")} />
                    <DecisionButton label="Uncertain" icon={<CircleHelp size={14} />} active={selectedDecision?.status === "uncertain"} warn onClick={() => upsertDecision(selectedFact, "uncertain")} />
                    <DecisionButton label={locateMutation.isPending ? "Finding..." : "Find in PDF"} icon={<Sparkles size={14} />} active={pdfMatches.length > 0} onClick={() => locateMutation.mutate(selectedFact)} />
                    <DecisionButton label="JSON Edit" icon={<Code2 size={14} />} active={selectedDecision?.status === "edited"} onClick={openEditor} />
                  </div>
                  {pdfMatches.length > 0 && (
                    <div className="mt-3 rounded-lg border border-[#fedf89] bg-[#fffaeb] p-2 text-xs text-[#7a4b00]">
                      Best candidate: page {pdfMatches[0].page_number}, {pdfMatches[0].confidence} confidence, {Math.round(pdfMatches[0].score * 100)}% score. {pdfMatches[0].text}
                      {pdfMatches[0].matched_terms.length > 0 && (
                        <span className="block pt-1 text-[#8a5a24]">Matched terms: {pdfMatches[0].matched_terms.join(", ")}</span>
                      )}
                    </div>
                  )}
                  <div className="mt-4">
                    <p className="mb-2 text-xs font-semibold uppercase tracking-wider text-[#55706c]">Reason Codes</p>
                    <div className="flex flex-wrap gap-2">
                      {REASON_LABELS.map((reason) => {
                        const active = selectedDecision?.reason_codes.includes(reason.code) ?? false;
                        return (
                          <button key={reason.code} type="button" onClick={() => {
                            const nextReasons = active ? (selectedDecision?.reason_codes ?? []).filter((code) => code !== reason.code) : [...(selectedDecision?.reason_codes ?? []), reason.code];
                            upsertDecision(selectedFact, selectedDecision?.status ?? "uncertain", { reason_codes: nextReasons });
                          }} className={`rounded-full border px-2.5 py-1 text-xs font-medium ${active ? "border-[#0f766e] bg-[#e7fbf7] text-[#0f766e]" : "border-[#dfe4ea] bg-white text-[#55706c]"}`}>
                            {reason.label}
                          </button>
                        );
                      })}
                    </div>
                  </div>
                  <label className="mt-4 block">
                    <span className="text-xs font-semibold uppercase tracking-wider text-[#55706c]">Reviewer Note</span>
                    <textarea ref={noteRef} value={selectedDecision?.reviewer_note ?? ""} onChange={(event) => upsertDecision(selectedFact, selectedDecision?.status ?? "uncertain", { reviewer_note: event.target.value })} placeholder="Capture support, contradiction, correction rationale, or follow-up needed." className="mt-2 min-h-24 w-full resize-y rounded-lg border border-[#dfe4ea] px-3 py-2 text-sm leading-6 text-[#0f172a] outline-none focus:border-[#0f766e]" />
                  </label>
                  <div className="mt-4">
                    <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-[#55706c]"><FileJson2 size={14} />Key Codes</div>
                    <div className="mt-2 flex flex-wrap gap-1.5">
                      {selectedFact.codes.length ? selectedFact.codes.map((code) => <span key={code} className="rounded-full border border-[#dfe4ea] bg-[#f8fafc] px-2 py-1 text-xs text-[#344054]">{code}</span>) : <span className="text-sm text-[#8aa19d]">No codes detected.</span>}
                    </div>
                  </div>
                  <details className="mt-4 rounded-lg border border-[#dfe4ea] bg-[#fbfcfd]">
                    <summary className="cursor-pointer px-3 py-2 text-sm font-semibold text-[#0f172a]">Resource JSON</summary>
                    <pre className="max-h-80 overflow-auto border-t border-[#e9eaef] p-3 text-xs leading-5 text-[#344054]">{JSON.stringify(selectedDecision?.edited_resource ?? selectedFact.original_resource, null, 2)}</pre>
                  </details>
                </div>
              </>
            ) : (
              <div className="flex min-h-0 flex-1 items-center justify-center text-sm text-[#55706c]">No facts in this bundle.</div>
            )}
          </section>
        )}
      </div>

      <footer className="grid shrink-0 grid-cols-6 gap-2 text-xs">
        <ProgressCell label="Accepted Facts" value={progress.accepted_facts} tone="green" />
        <ProgressCell label="Rejected Facts" value={progress.rejected_facts} tone="red" />
        <ProgressCell label="Edited Facts" value={progress.edited_facts} tone="blue" />
        <ProgressCell label="Uncertain" value={progress.uncertain_facts} tone="amber" />
        <ProgressCell label="Needs Review" value={progress.needs_review} tone="gray" />
        <ProgressCell label="Reference Version" value={review.published_ground_truth_version ? `v${review.published_ground_truth_version}` : "Draft"} tone="purple" />
      </footer>

      {editorOpen && selectedFact && (
        <div className="fixed inset-0 z-[80] flex items-center justify-center bg-[#101828]/40 px-4 py-8 backdrop-blur-[2px]">
          <section className="flex max-h-[86vh] w-full max-w-4xl flex-col overflow-hidden rounded-lg border border-[#dfe4ea] bg-white shadow-2xl">
            <header className="flex items-center justify-between border-b border-[#e9eaef] px-4 py-3">
              <div>
                <p className="text-xs font-semibold uppercase tracking-wider text-[#0f766e]">JSON Edit</p>
                <h3 className="text-base font-semibold text-[#0f172a]">{selectedFact.resource_ref}</h3>
              </div>
              <button type="button" onClick={() => setEditorOpen(false)} className="rounded-lg p-2 text-[#667085] hover:bg-[#f5f6f8]">
                <X size={18} />
              </button>
            </header>
            <div className="min-h-0 flex-1 p-4">
              <textarea
                value={jsonDraft}
                onChange={(event) => setJsonDraft(event.target.value)}
                spellCheck={false}
                className="h-[52vh] w-full resize-none rounded-lg border border-[#dfe4ea] bg-[#0f172a] p-3 font-mono text-xs leading-5 text-[#e5e7eb] outline-none focus:border-[#0f766e]"
              />
              {jsonError && <p className="mt-2 text-sm text-[#b42318]">{jsonError}</p>}
            </div>
            <footer className="flex justify-end gap-2 border-t border-[#e9eaef] bg-[#fbfcfd] px-4 py-3">
              <button type="button" onClick={() => setEditorOpen(false)} className="rounded-lg border border-[#dfe4ea] bg-white px-3 py-2 text-sm font-semibold text-[#555a6a]">
                Cancel
              </button>
              <button
                type="button"
                onClick={() => {
                  try {
                    const parsed = JSON.parse(jsonDraft) as Record<string, unknown>;
                    if (!parsed || typeof parsed !== "object" || Array.isArray(parsed)) {
                      setJsonError("Edited resource must be a JSON object.");
                      return;
                    }
                    upsertDecision(selectedFact, "edited", { edited_resource: parsed });
                    setEditorOpen(false);
                  } catch (err) {
                    setJsonError(err instanceof Error ? err.message : "Invalid JSON.");
                  }
                }}
                className="rounded-lg bg-[#0f766e] px-3 py-2 text-sm font-semibold text-white"
              >
                Apply Edit
              </button>
            </footer>
          </section>
        </div>
      )}
    </div>
  );
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div className="min-w-0 rounded-md border border-[#dfe4ea] bg-white px-2 py-1.5">
      <p className="text-[10px] uppercase tracking-wider text-[#667085]">{label}</p>
      <p className="mt-0.5 truncate font-medium text-[#0f172a]">{value}</p>
    </div>
  );
}

function PaneHeader({
  icon,
  title,
  children,
  onCollapse,
}: {
  icon: ReactNode;
  title: string;
  children?: ReactNode;
  onCollapse: () => void;
}) {
  return (
    <div className="flex shrink-0 items-center justify-between gap-2 border-b border-[#e5f1ee] bg-[#f7fffc] px-3 py-2">
      <div className="inline-flex min-w-0 items-center gap-2 text-sm font-semibold text-[#0f172a]">
        {icon}
        <span className="truncate">{title}</span>
      </div>
      <div className="flex shrink-0 items-center gap-1">
        {children}
        <button
          type="button"
          onClick={onCollapse}
          className="inline-flex h-7 w-7 items-center justify-center rounded-md border border-[#dfe4ea] bg-white text-[#667085]"
          title="Collapse pane"
        >
          <X size={14} />
        </button>
      </div>
    </div>
  );
}

function ResizeHandle({ onPointerDown }: { onPointerDown: (event: ReactPointerEvent<HTMLDivElement>) => void }) {
  return (
    <div
      role="separator"
      aria-orientation="vertical"
      onPointerDown={onPointerDown}
      className="group flex cursor-col-resize items-stretch justify-center"
      title="Drag to resize panes"
    >
      <div className="my-2 w-1 rounded-full bg-[#cdeee9] transition-colors group-hover:bg-[#0f766e]" />
    </div>
  );
}

function DecisionButton({
  label,
  icon,
  active,
  danger,
  warn,
  onClick,
}: {
  label: string;
  icon: ReactNode;
  active?: boolean;
  danger?: boolean;
  warn?: boolean;
  onClick: () => void;
}) {
  const activeClass = danger
    ? "border-[#fda29b] bg-[#fff1f1] text-[#b42318]"
    : warn
      ? "border-[#fedf89] bg-[#fffaeb] text-[#b54708]"
      : "border-[#0f766e] bg-[#e7fbf7] text-[#0f766e]";
  return (
    <button
      type="button"
      onClick={onClick}
      className={`inline-flex items-center gap-2 rounded-lg border px-3 py-2 text-sm font-semibold ${
        active ? activeClass : "border-[#dfe4ea] bg-white text-[#344054] hover:border-[#0f766e] hover:text-[#0f766e]"
      }`}
    >
      {icon}
      {label}
    </button>
  );
}

function ProgressCell({
  label,
  value,
  tone,
}: {
  label: string;
  value: number | string;
  tone: "green" | "red" | "blue" | "amber" | "gray" | "purple";
}) {
  const tones = {
    green: "border-[#b7e4cd] bg-[#ecfdf3] text-[#027a48]",
    red: "border-[#fecaca] bg-[#fff1f1] text-[#b42318]",
    blue: "border-[#bfdbfe] bg-[#eff6ff] text-[#175cd3]",
    amber: "border-[#fedf89] bg-[#fffaeb] text-[#b54708]",
    gray: "border-[#dfe4ea] bg-white text-[#344054]",
    purple: "border-[#e9d7fe] bg-[#f9f5ff] text-[#6941c6]",
  };
  return (
    <div className={`rounded-lg border px-3 py-2 ${tones[tone]}`}>
      <p className="text-[10px] font-semibold uppercase tracking-wider opacity-75">{label}</p>
      <p className="mt-1 text-base font-semibold">{value}</p>
    </div>
  );
}

export function GroundTruthReview() {
  const params = useParams();
  const runId = params.runId ? decodeURIComponent(params.runId) : null;
  return runId ? <ReferenceReviewWorkspace runId={runId} /> : <RunList />;
}

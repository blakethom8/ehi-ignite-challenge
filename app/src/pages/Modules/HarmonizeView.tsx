import { useEffect, useMemo, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Activity,
  AlertTriangle,
  FileText,
  Layers3,
  Link2,
  Loader2,
  Pill,
  ShieldAlert,
  Sparkles,
  Stethoscope,
  Syringe,
} from "lucide-react";
import { api } from "../../api/client";
import type {
  HarmonizeMergedAllergy,
  HarmonizeMergedCondition,
  HarmonizeMergedImmunization,
  HarmonizeMergedMedication,
  HarmonizeMergedObservation,
  HarmonizeProvenanceResponse,
} from "../../types";

type ResourceTab =
  | "labs"
  | "conditions"
  | "medications"
  | "allergies"
  | "immunizations";

function cls(...parts: (string | false | null | undefined)[]): string {
  return parts.filter(Boolean).join(" ");
}

/** Source kind → small badge label/color. */
function kindBadge(kind: string): { label: string; color: string } {
  if (kind === "fhir-pull") return { label: "FHIR pull", color: "bg-emerald-100 text-emerald-800" };
  if (kind === "extracted-pdf") return { label: "PDF extraction", color: "bg-amber-100 text-amber-800" };
  return { label: kind, color: "bg-slate-100 text-slate-700" };
}

function MetricCard({
  label,
  value,
  detail,
}: {
  label: string;
  value: string | number;
  detail?: string;
}) {
  return (
    <div className="rounded-xl bg-white p-4 shadow-[rgb(224_226_232)_0px_0px_0px_1px]">
      <p className="text-xs font-semibold uppercase tracking-wider text-[#667085]">{label}</p>
      <p className="mt-2 text-2xl font-semibold text-[#1c1c1e]">{value}</p>
      {detail && <p className="mt-1 text-sm leading-5 text-[#667085]">{detail}</p>}
    </div>
  );
}

function SourcesPanel({ collectionId }: { collectionId: string }) {
  const [selectedDocRef, setSelectedDocRef] = useState<string | null>(null);

  const { data, isLoading, error } = useQuery({
    queryKey: ["harmonize-sources", collectionId],
    queryFn: () => api.getHarmonizeSources(collectionId),
    enabled: !!collectionId,
  });

  if (isLoading) return <p className="text-sm text-[#667085]">Loading sources…</p>;
  if (error || !data) return <p className="text-sm text-red-700">Couldn't load sources.</p>;

  return (
    <div className="rounded-2xl bg-white p-5 shadow-[rgb(224_226_232)_0px_0px_0px_1px]">
      <div className="mb-3 flex items-center gap-2">
        <FileText size={16} className="text-[#5b76fe]" />
        <h3 className="text-sm font-semibold text-[#1c1c1e]">
          Sources in this collection
        </h3>
        <span className="ml-2 text-xs text-[#a5a8b5]">
          (click a row to see what it contributed)
        </span>
      </div>
      <div className="overflow-hidden rounded-xl border border-[#dfe4ea]">
        <table className="w-full text-sm">
          <thead className="bg-[#f7f9fc] text-left text-xs font-semibold uppercase tracking-wider text-[#667085]">
            <tr>
              <th className="px-4 py-2">Source</th>
              <th className="px-4 py-2">Kind</th>
              <th className="px-4 py-2 text-right">Observations</th>
              <th className="px-4 py-2 text-right">Conditions</th>
              <th className="px-4 py-2 text-right">Total</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-[#eef0f4] bg-white">
            {data.sources.map((s) => {
              const badge = kindBadge(s.kind);
              const clickable = !!s.document_reference;
              const isSelected =
                clickable && selectedDocRef === s.document_reference;
              return (
                <tr
                  key={s.id}
                  onClick={() =>
                    clickable
                      ? setSelectedDocRef(
                          isSelected ? null : s.document_reference,
                        )
                      : undefined
                  }
                  className={cls(
                    !s.available && "opacity-50",
                    clickable && "cursor-pointer hover:bg-[#f7f9fc]",
                    isSelected && "bg-[#eef2ff]",
                  )}
                >
                  <td className="px-4 py-2 font-medium text-[#1c1c1e]">{s.label}</td>
                  <td className="px-4 py-2">
                    <span
                      className={cls(
                        "rounded-full px-2 py-0.5 text-xs font-medium",
                        badge.color,
                      )}
                    >
                      {badge.label}
                    </span>
                  </td>
                  <td className="px-4 py-2 text-right tabular-nums text-[#1c1c1e]">
                    {s.resource_counts.Observation ?? 0}
                  </td>
                  <td className="px-4 py-2 text-right tabular-nums text-[#1c1c1e]">
                    {s.resource_counts.Condition ?? 0}
                  </td>
                  <td className="px-4 py-2 text-right tabular-nums text-[#667085]">
                    {s.total_resources}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
      {selectedDocRef && (
        <ContributionsPanel
          collectionId={collectionId}
          documentReference={selectedDocRef}
          onClose={() => setSelectedDocRef(null)}
        />
      )}
    </div>
  );
}


function ContributionsPanel({
  collectionId,
  documentReference,
  onClose,
}: {
  collectionId: string;
  documentReference: string;
  onClose: () => void;
}) {
  const { data, isLoading } = useQuery({
    queryKey: ["harmonize-contributions", collectionId, documentReference],
    queryFn: () =>
      api.getHarmonizeContributions(collectionId, documentReference),
  });

  return (
    <div className="mt-4 rounded-xl border border-[#dfe4ea] bg-[#fafbfd] p-4">
      <div className="flex items-center justify-between gap-2">
        <div>
          <p className="text-xs font-semibold uppercase tracking-wider text-[#5b76fe]">
            Reverse Provenance walk
          </p>
          <p className="mt-1 text-sm font-semibold text-[#1c1c1e]">
            What did <span className="font-mono">{data?.label ?? "this source"}</span> contribute?
          </p>
        </div>
        <button
          type="button"
          onClick={onClose}
          className="rounded-lg border border-[#dfe4ea] bg-white px-2 py-1 text-xs text-[#667085]"
        >
          Close
        </button>
      </div>

      {isLoading || !data ? (
        <p className="mt-3 text-sm text-[#667085]">Walking the Provenance graph…</p>
      ) : (
        <>
          <div className="mt-3 grid grid-cols-2 gap-2 sm:grid-cols-5">
            <ContributionStat label="Labs" value={data.totals.observations} />
            <ContributionStat label="Conditions" value={data.totals.conditions} />
            <ContributionStat label="Medications" value={data.totals.medications} />
            <ContributionStat label="Allergies" value={data.totals.allergies} />
            <ContributionStat label="Immunizations" value={data.totals.immunizations} />
          </div>
          <div className="mt-4 grid grid-cols-1 gap-3 lg:grid-cols-2">
            <ContributionList
              title="Conditions"
              items={data.conditions.map((c) => ({
                primary: c.canonical_name,
                secondary: c.snomed
                  ? `SCT ${c.snomed}`
                  : c.icd10
                    ? `ICD-10 ${c.icd10}`
                    : "text-only",
              }))}
            />
            <ContributionList
              title="Medications"
              items={data.medications.map((m) => ({
                primary: m.canonical_name,
                secondary:
                  m.rxnorm_codes.length > 0
                    ? `RxNorm ${m.rxnorm_codes[0]}${m.rxnorm_codes.length > 1 ? ` +${m.rxnorm_codes.length - 1}` : ""}`
                    : "text-only",
              }))}
            />
            <ContributionList
              title="Immunizations"
              items={data.immunizations.map((i) => ({
                primary: i.canonical_name,
                secondary: `${i.occurrence_date?.slice(0, 10) ?? "—"}${i.cvx ? ` · CVX ${i.cvx}` : ""}`,
              }))}
            />
            <ContributionList
              title="Allergies"
              items={data.allergies.map((a) => ({
                primary: a.canonical_name,
                secondary: a.snomed
                  ? `SCT ${a.snomed}`
                  : a.rxnorm
                    ? `RxNorm ${a.rxnorm}`
                    : "text-only",
              }))}
            />
          </div>
          {data.totals.observations > 0 && (
            <p className="mt-3 text-xs text-[#a5a8b5]">
              + {data.totals.observations} lab observation
              {data.totals.observations === 1 ? "" : "s"} contributed (open the
              Labs tab to drill in).
            </p>
          )}
        </>
      )}
    </div>
  );
}

function ContributionStat({ label, value }: { label: string; value: number }) {
  return (
    <div className="rounded-lg border border-[#dfe4ea] bg-white p-2 text-center">
      <p className="text-xs font-semibold uppercase tracking-wider text-[#667085]">
        {label}
      </p>
      <p className="mt-0.5 text-lg font-semibold tabular-nums text-[#1c1c1e]">
        {value}
      </p>
    </div>
  );
}

function ContributionList({
  title,
  items,
}: {
  title: string;
  items: { primary: string; secondary: string }[];
}) {
  if (items.length === 0) return null;
  return (
    <div className="rounded-lg border border-[#dfe4ea] bg-white p-3">
      <p className="text-xs font-semibold uppercase tracking-wider text-[#667085]">
        {title} · {items.length}
      </p>
      <ul className="mt-2 space-y-1 text-sm">
        {items.map((it, i) => (
          <li key={i} className="flex items-start justify-between gap-2">
            <span className="truncate font-medium text-[#1c1c1e]">{it.primary}</span>
            <span className="shrink-0 text-xs text-[#667085]">{it.secondary}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}

function ProvenancePanel({
  collectionId,
  mergedRef,
}: {
  collectionId: string;
  mergedRef: string | null;
}) {
  const { data, isLoading } = useQuery<HarmonizeProvenanceResponse>({
    queryKey: ["harmonize-provenance", collectionId, mergedRef],
    queryFn: () => api.getHarmonizeProvenance(collectionId, mergedRef as string),
    enabled: !!mergedRef,
  });

  if (!mergedRef) {
    return (
      <p className="text-sm text-[#667085]">
        Pick a merged fact to see its Provenance lineage.
      </p>
    );
  }
  if (isLoading) return <p className="text-sm text-[#667085]">Loading lineage…</p>;
  if (!data) return <p className="text-sm text-red-700">Couldn't load Provenance.</p>;

  const prov = data.provenance;
  const activity = prov.activity?.coding?.[0]?.code ?? "—";
  return (
    <div className="space-y-3">
      <div className="flex items-center gap-2 text-xs uppercase tracking-wider text-[#667085]">
        <Link2 size={14} />
        <span className="font-semibold">Activity:</span>
        <code className="rounded bg-[#f0f3fa] px-1.5 py-0.5 text-[11px] text-[#1c1c1e]">
          {activity}
        </code>
        <span>· {prov.entity?.length ?? 0} source edge(s)</span>
      </div>
      <ul className="space-y-2">
        {prov.entity?.map((e, idx) => {
          const ext = Object.fromEntries(
            (e.extension ?? []).map((x) => [
              x.url.split("/").pop() ?? x.url,
              x.valueString,
            ]),
          );
          return (
            <li
              key={idx}
              className="rounded-lg border border-[#dfe4ea] bg-white p-3 text-sm"
            >
              <div className="flex items-center justify-between gap-2">
                <span className="font-semibold text-[#1c1c1e]">
                  {ext["source-label"] ?? "?"}
                </span>
                <code className="rounded bg-[#f0f3fa] px-1.5 py-0.5 text-[11px] text-[#5b76fe]">
                  {ext["harmonize-activity"] ?? "?"}
                </code>
              </div>
              <code className="mt-1 block truncate text-xs text-[#667085]">
                {e.what?.reference}
              </code>
            </li>
          );
        })}
      </ul>
      <details className="rounded-lg border border-[#dfe4ea] bg-[#fafbfd] p-2 text-xs">
        <summary className="cursor-pointer font-semibold text-[#667085]">
          Raw FHIR Provenance JSON
        </summary>
        <pre className="mt-2 max-h-96 overflow-auto whitespace-pre-wrap break-all text-[10px] leading-snug text-[#1c1c1e]">
          {JSON.stringify(prov, null, 2)}
        </pre>
      </details>
    </div>
  );
}

function LabsTab({ collectionId }: { collectionId: string }) {
  const [crossOnly, setCrossOnly] = useState(true);
  const [selectedRef, setSelectedRef] = useState<string | null>(null);

  const { data, isLoading } = useQuery({
    queryKey: ["harmonize-observations", collectionId, crossOnly],
    queryFn: () => api.getHarmonizeObservations(collectionId, crossOnly),
    enabled: !!collectionId,
  });

  const merged: HarmonizeMergedObservation[] = data?.merged ?? [];
  const selected = useMemo(
    () => merged.find((m) => m.merged_ref === selectedRef) ?? merged[0] ?? null,
    [merged, selectedRef],
  );

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-1 gap-3 md:grid-cols-3">
        <MetricCard
          label="Canonical labs"
          value={data?.total ?? 0}
          detail="Distinct facts after identity resolution"
        />
        <MetricCard
          label="Cross-source merges"
          value={data?.cross_source ?? 0}
          detail="Labs found in ≥2 sources"
        />
        <MetricCard
          label="Conflicts"
          value={merged.filter((m) => m.has_conflict).length}
          detail=">10% same-day spread"
        />
      </div>

      <div className="flex items-center justify-between">
        <label className="flex items-center gap-2 text-sm text-[#667085]">
          <input
            type="checkbox"
            checked={crossOnly}
            onChange={(e) => {
              setCrossOnly(e.target.checked);
              setSelectedRef(null);
            }}
            className="h-4 w-4 rounded border-[#dfe4ea]"
          />
          Show only cross-source merges
        </label>
      </div>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
        <div className="lg:col-span-2 overflow-hidden rounded-2xl bg-white shadow-[rgb(224_226_232)_0px_0px_0px_1px]">
          {isLoading ? (
            <p className="p-6 text-sm text-[#667085]">Loading labs…</p>
          ) : merged.length === 0 ? (
            <p className="p-6 text-sm text-[#667085]">No labs to display.</p>
          ) : (
            <div className="max-h-[640px] overflow-y-auto">
              <table className="w-full text-sm">
                <thead className="sticky top-0 bg-[#f7f9fc] text-left text-xs font-semibold uppercase tracking-wider text-[#667085]">
                  <tr>
                    <th className="px-4 py-2">Lab</th>
                    <th className="px-4 py-2">LOINC</th>
                    <th className="px-4 py-2 text-right">Sources</th>
                    <th className="px-4 py-2 text-right">Latest</th>
                    <th className="px-4 py-2"></th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-[#eef0f4] bg-white">
                  {merged.map((m) => {
                    const isSelected = selected?.merged_ref === m.merged_ref;
                    return (
                      <tr
                        key={m.merged_ref ?? m.canonical_name}
                        onClick={() => setSelectedRef(m.merged_ref)}
                        className={cls(
                          "cursor-pointer hover:bg-[#f7f9fc]",
                          isSelected && "bg-[#eef2ff]",
                        )}
                      >
                        <td className="px-4 py-2 font-medium text-[#1c1c1e]">
                          {m.canonical_name.length > 50
                            ? m.canonical_name.slice(0, 50) + "…"
                            : m.canonical_name}
                        </td>
                        <td className="px-4 py-2 text-[#667085]">
                          <code className="text-xs">{m.loinc_code ?? "—"}</code>
                        </td>
                        <td className="px-4 py-2 text-right tabular-nums text-[#1c1c1e]">
                          {m.source_count}
                        </td>
                        <td className="px-4 py-2 text-right tabular-nums text-[#1c1c1e]">
                          {m.latest?.value != null
                            ? `${m.latest.value} ${m.latest.unit ?? ""}`
                            : "—"}
                        </td>
                        <td className="px-4 py-2">
                          {m.has_conflict && (
                            <AlertTriangle
                              size={14}
                              className="text-amber-600"
                              aria-label="Same-day cross-source conflict"
                            />
                          )}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}
        </div>

        <div className="space-y-4">
          <div className="rounded-2xl bg-white p-4 shadow-[rgb(224_226_232)_0px_0px_0px_1px]">
            <h4 className="text-sm font-semibold text-[#1c1c1e]">
              {selected?.canonical_name ?? "—"}
            </h4>
            {selected?.loinc_code && (
              <p className="mt-1 text-xs text-[#667085]">
                LOINC <code>{selected.loinc_code}</code> · canonical unit{" "}
                <code>{selected.canonical_unit ?? "—"}</code>
              </p>
            )}
            {selected && (
              <ul className="mt-3 space-y-1 text-sm">
                {selected.sources.map((s, i) => (
                  <li
                    key={i}
                    className="flex items-center justify-between border-b border-[#eef0f4] py-1 last:border-b-0"
                  >
                    <span className="text-[#667085]">
                      {s.effective_date ? s.effective_date.slice(0, 10) : "—"} ·{" "}
                      {s.source_label}
                    </span>
                    <span className="tabular-nums font-medium text-[#1c1c1e]">
                      {s.value != null ? `${s.value} ${s.unit ?? ""}` : "—"}
                    </span>
                  </li>
                ))}
              </ul>
            )}
          </div>
          <div className="rounded-2xl bg-white p-4 shadow-[rgb(224_226_232)_0px_0px_0px_1px]">
            <h4 className="mb-2 text-sm font-semibold text-[#1c1c1e]">
              Provenance lineage
            </h4>
            <ProvenancePanel
              collectionId={collectionId}
              mergedRef={selected?.merged_ref ?? null}
            />
          </div>
        </div>
      </div>
    </div>
  );
}

function ConditionsTab({ collectionId }: { collectionId: string }) {
  const [crossOnly, setCrossOnly] = useState(true);
  const [selectedRef, setSelectedRef] = useState<string | null>(null);

  const { data, isLoading } = useQuery({
    queryKey: ["harmonize-conditions", collectionId, crossOnly],
    queryFn: () => api.getHarmonizeConditions(collectionId, crossOnly),
    enabled: !!collectionId,
  });

  const merged: HarmonizeMergedCondition[] = data?.merged ?? [];
  const selected = useMemo(
    () => merged.find((m) => m.merged_ref === selectedRef) ?? merged[0] ?? null,
    [merged, selectedRef],
  );

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-1 gap-3 md:grid-cols-3">
        <MetricCard
          label="Canonical conditions"
          value={data?.total ?? 0}
          detail="Distinct facts after identity resolution"
        />
        <MetricCard
          label="Cross-source merges"
          value={data?.cross_source ?? 0}
          detail="Conditions found in ≥2 sources"
        />
        <MetricCard
          label="Active"
          value={merged.filter((m) => m.is_active).length}
          detail="Status active / recurrent / unknown"
        />
      </div>

      <div className="flex items-center justify-between">
        <label className="flex items-center gap-2 text-sm text-[#667085]">
          <input
            type="checkbox"
            checked={crossOnly}
            onChange={(e) => {
              setCrossOnly(e.target.checked);
              setSelectedRef(null);
            }}
            className="h-4 w-4 rounded border-[#dfe4ea]"
          />
          Show only cross-source merges
        </label>
      </div>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
        <div className="lg:col-span-2 overflow-hidden rounded-2xl bg-white shadow-[rgb(224_226_232)_0px_0px_0px_1px]">
          {isLoading ? (
            <p className="p-6 text-sm text-[#667085]">Loading conditions…</p>
          ) : merged.length === 0 ? (
            <p className="p-6 text-sm text-[#667085]">No conditions to display.</p>
          ) : (
            <div className="max-h-[640px] overflow-y-auto">
              <table className="w-full text-sm">
                <thead className="sticky top-0 bg-[#f7f9fc] text-left text-xs font-semibold uppercase tracking-wider text-[#667085]">
                  <tr>
                    <th className="px-4 py-2">Condition</th>
                    <th className="px-4 py-2">SNOMED</th>
                    <th className="px-4 py-2">ICD-10</th>
                    <th className="px-4 py-2 text-right">Sources</th>
                    <th className="px-4 py-2"></th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-[#eef0f4] bg-white">
                  {merged.map((m) => {
                    const isSelected = selected?.merged_ref === m.merged_ref;
                    return (
                      <tr
                        key={m.merged_ref ?? m.canonical_name}
                        onClick={() => setSelectedRef(m.merged_ref)}
                        className={cls(
                          "cursor-pointer hover:bg-[#f7f9fc]",
                          isSelected && "bg-[#eef2ff]",
                        )}
                      >
                        <td className="px-4 py-2 font-medium text-[#1c1c1e]">
                          {m.canonical_name.length > 60
                            ? m.canonical_name.slice(0, 60) + "…"
                            : m.canonical_name}
                        </td>
                        <td className="px-4 py-2 text-[#667085]">
                          <code className="text-xs">{m.snomed ?? "—"}</code>
                        </td>
                        <td className="px-4 py-2 text-[#667085]">
                          <code className="text-xs">{m.icd10 ?? "—"}</code>
                        </td>
                        <td className="px-4 py-2 text-right tabular-nums text-[#1c1c1e]">
                          {m.source_count}
                        </td>
                        <td className="px-4 py-2 text-center">
                          {m.is_active ? (
                            <span className="text-emerald-600">●</span>
                          ) : (
                            <span className="text-[#dfe4ea]">○</span>
                          )}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}
        </div>

        <div className="space-y-4">
          <div className="rounded-2xl bg-white p-4 shadow-[rgb(224_226_232)_0px_0px_0px_1px]">
            <h4 className="text-sm font-semibold text-[#1c1c1e]">
              {selected?.canonical_name ?? "—"}
            </h4>
            {selected && (
              <p className="mt-1 text-xs text-[#667085]">
                {selected.snomed && (
                  <span>
                    SNOMED <code>{selected.snomed}</code>{" "}
                  </span>
                )}
                {selected.icd10 && (
                  <span>
                    · ICD-10 <code>{selected.icd10}</code>
                  </span>
                )}
                {selected.icd9 && (
                  <span>
                    · ICD-9 <code>{selected.icd9}</code>
                  </span>
                )}
              </p>
            )}
            {selected && (
              <ul className="mt-3 space-y-1 text-sm">
                {selected.sources.map((s, i) => (
                  <li key={i} className="border-b border-[#eef0f4] py-1 last:border-b-0">
                    <div className="flex items-center justify-between">
                      <span className="font-medium text-[#1c1c1e]">{s.source_label}</span>
                      <span className="text-xs text-[#667085]">
                        {s.onset_date ? s.onset_date.slice(0, 10) : "—"}
                      </span>
                    </div>
                    <p className="text-xs text-[#667085]">{s.display}</p>
                  </li>
                ))}
              </ul>
            )}
          </div>
          <div className="rounded-2xl bg-white p-4 shadow-[rgb(224_226_232)_0px_0px_0px_1px]">
            <h4 className="mb-2 text-sm font-semibold text-[#1c1c1e]">
              Provenance lineage
            </h4>
            <ProvenancePanel
              collectionId={collectionId}
              mergedRef={selected?.merged_ref ?? null}
            />
          </div>
        </div>
      </div>
    </div>
  );
}

function MedicationsTab({ collectionId }: { collectionId: string }) {
  const [crossOnly, setCrossOnly] = useState(true);
  const [selectedRef, setSelectedRef] = useState<string | null>(null);

  const { data, isLoading } = useQuery({
    queryKey: ["harmonize-medications", collectionId, crossOnly],
    queryFn: () => api.getHarmonizeMedications(collectionId, crossOnly),
    enabled: !!collectionId,
  });

  const merged: HarmonizeMergedMedication[] = data?.merged ?? [];
  const selected = useMemo(
    () => merged.find((m) => m.merged_ref === selectedRef) ?? merged[0] ?? null,
    [merged, selectedRef],
  );

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-1 gap-3 md:grid-cols-3">
        <MetricCard
          label="Canonical medications"
          value={data?.total ?? 0}
          detail="Distinct meds after identity resolution"
        />
        <MetricCard
          label="Cross-source merges"
          value={data?.cross_source ?? 0}
          detail="Meds found in ≥2 sources"
        />
        <MetricCard
          label="Active"
          value={merged.filter((m) => m.is_active).length}
          detail="Status active / on-hold / unknown"
        />
      </div>

      <div className="flex items-center justify-between">
        <label className="flex items-center gap-2 text-sm text-[#667085]">
          <input
            type="checkbox"
            checked={crossOnly}
            onChange={(e) => {
              setCrossOnly(e.target.checked);
              setSelectedRef(null);
            }}
            className="h-4 w-4 rounded border-[#dfe4ea]"
          />
          Show only cross-source merges
        </label>
      </div>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
        <div className="lg:col-span-2 overflow-hidden rounded-2xl bg-white shadow-[rgb(224_226_232)_0px_0px_0px_1px]">
          {isLoading ? (
            <p className="p-6 text-sm text-[#667085]">Loading medications…</p>
          ) : merged.length === 0 ? (
            <p className="p-6 text-sm text-[#667085]">No medications to display.</p>
          ) : (
            <div className="max-h-[640px] overflow-y-auto">
              <table className="w-full text-sm">
                <thead className="sticky top-0 bg-[#f7f9fc] text-left text-xs font-semibold uppercase tracking-wider text-[#667085]">
                  <tr>
                    <th className="px-4 py-2">Medication</th>
                    <th className="px-4 py-2">RxNorm</th>
                    <th className="px-4 py-2 text-right">Sources</th>
                    <th className="px-4 py-2 text-center">Active</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-[#eef0f4] bg-white">
                  {merged.map((m) => {
                    const isSelected = selected?.merged_ref === m.merged_ref;
                    return (
                      <tr
                        key={m.merged_ref ?? m.canonical_name}
                        onClick={() => setSelectedRef(m.merged_ref)}
                        className={cls(
                          "cursor-pointer hover:bg-[#f7f9fc]",
                          isSelected && "bg-[#eef2ff]",
                        )}
                      >
                        <td className="px-4 py-2 font-medium text-[#1c1c1e]">
                          {m.canonical_name.length > 50
                            ? m.canonical_name.slice(0, 50) + "…"
                            : m.canonical_name}
                        </td>
                        <td className="px-4 py-2 text-[#667085]">
                          <code className="text-xs">
                            {m.rxnorm_codes[0] ?? "—"}
                            {m.rxnorm_codes.length > 1 && ` +${m.rxnorm_codes.length - 1}`}
                          </code>
                        </td>
                        <td className="px-4 py-2 text-right tabular-nums text-[#1c1c1e]">
                          {m.source_count}
                        </td>
                        <td className="px-4 py-2 text-center">
                          {m.is_active ? (
                            <span className="text-emerald-600">●</span>
                          ) : (
                            <span className="text-[#dfe4ea]">○</span>
                          )}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}
        </div>

        <div className="space-y-4">
          <div className="rounded-2xl bg-white p-4 shadow-[rgb(224_226_232)_0px_0px_0px_1px]">
            <h4 className="text-sm font-semibold text-[#1c1c1e]">
              {selected?.canonical_name ?? "—"}
            </h4>
            {selected && selected.rxnorm_codes.length > 0 && (
              <p className="mt-1 text-xs text-[#667085]">
                RxNorm codes:{" "}
                {selected.rxnorm_codes.slice(0, 5).map((c, i) => (
                  <code key={c} className="text-xs">
                    {c}
                    {i < Math.min(selected.rxnorm_codes.length, 5) - 1 ? ", " : ""}
                  </code>
                ))}
                {selected.rxnorm_codes.length > 5 &&
                  ` (+${selected.rxnorm_codes.length - 5} more)`}
              </p>
            )}
            {selected && (
              <ul className="mt-3 space-y-1 text-sm">
                {selected.sources.map((s, i) => (
                  <li key={i} className="border-b border-[#eef0f4] py-1 last:border-b-0">
                    <div className="flex items-center justify-between">
                      <span className="font-medium text-[#1c1c1e]">{s.source_label}</span>
                      <span className="text-xs text-[#667085]">
                        {s.status ?? "—"}
                      </span>
                    </div>
                    <p className="text-xs text-[#667085]">{s.display}</p>
                    {s.authored_on && (
                      <p className="text-[10px] text-[#a5a8b5]">
                        authored {s.authored_on.slice(0, 10)}
                      </p>
                    )}
                  </li>
                ))}
              </ul>
            )}
          </div>
          <div className="rounded-2xl bg-white p-4 shadow-[rgb(224_226_232)_0px_0px_0px_1px]">
            <h4 className="mb-2 text-sm font-semibold text-[#1c1c1e]">
              Provenance lineage
            </h4>
            <ProvenancePanel
              collectionId={collectionId}
              mergedRef={selected?.merged_ref ?? null}
            />
          </div>
        </div>
      </div>
    </div>
  );
}

function AllergiesTab({ collectionId }: { collectionId: string }) {
  const [crossOnly, setCrossOnly] = useState(true);
  const [selectedRef, setSelectedRef] = useState<string | null>(null);

  const { data, isLoading } = useQuery({
    queryKey: ["harmonize-allergies", collectionId, crossOnly],
    queryFn: () => api.getHarmonizeAllergies(collectionId, crossOnly),
    enabled: !!collectionId,
  });

  const merged: HarmonizeMergedAllergy[] = data?.merged ?? [];
  const selected = useMemo(
    () => merged.find((m) => m.merged_ref === selectedRef) ?? merged[0] ?? null,
    [merged, selectedRef],
  );

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-1 gap-3 md:grid-cols-3">
        <MetricCard
          label="Canonical allergies"
          value={data?.total ?? 0}
          detail="Distinct allergies after identity resolution"
        />
        <MetricCard
          label="Cross-source merges"
          value={data?.cross_source ?? 0}
          detail="Allergies in ≥2 sources"
        />
        <MetricCard
          label="High criticality"
          value={merged.filter((m) => m.highest_criticality === "high").length}
          detail="Worst-severity rollup"
        />
      </div>

      <div className="flex items-center justify-between">
        <label className="flex items-center gap-2 text-sm text-[#667085]">
          <input
            type="checkbox"
            checked={crossOnly}
            onChange={(e) => {
              setCrossOnly(e.target.checked);
              setSelectedRef(null);
            }}
            className="h-4 w-4 rounded border-[#dfe4ea]"
          />
          Show only cross-source merges
        </label>
      </div>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
        <div className="lg:col-span-2 overflow-hidden rounded-2xl bg-white shadow-[rgb(224_226_232)_0px_0px_0px_1px]">
          {isLoading ? (
            <p className="p-6 text-sm text-[#667085]">Loading allergies…</p>
          ) : merged.length === 0 ? (
            <p className="p-6 text-sm text-[#667085]">No allergies to display.</p>
          ) : (
            <div className="max-h-[640px] overflow-y-auto">
              <table className="w-full text-sm">
                <thead className="sticky top-0 bg-[#f7f9fc] text-left text-xs font-semibold uppercase tracking-wider text-[#667085]">
                  <tr>
                    <th className="px-4 py-2">Allergy</th>
                    <th className="px-4 py-2">SNOMED</th>
                    <th className="px-4 py-2">Criticality</th>
                    <th className="px-4 py-2 text-right">Sources</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-[#eef0f4] bg-white">
                  {merged.map((m) => {
                    const isSelected = selected?.merged_ref === m.merged_ref;
                    return (
                      <tr
                        key={m.merged_ref ?? m.canonical_name}
                        onClick={() => setSelectedRef(m.merged_ref)}
                        className={cls(
                          "cursor-pointer hover:bg-[#f7f9fc]",
                          isSelected && "bg-[#eef2ff]",
                        )}
                      >
                        <td className="px-4 py-2 font-medium text-[#1c1c1e]">
                          {m.canonical_name.length > 50
                            ? m.canonical_name.slice(0, 50) + "…"
                            : m.canonical_name}
                        </td>
                        <td className="px-4 py-2 text-[#667085]">
                          <code className="text-xs">{m.snomed ?? "—"}</code>
                        </td>
                        <td className="px-4 py-2">
                          {m.highest_criticality === "high" ? (
                            <span className="rounded-full bg-red-100 px-2 py-0.5 text-xs font-medium text-red-700">
                              high
                            </span>
                          ) : m.highest_criticality === "low" ? (
                            <span className="rounded-full bg-amber-100 px-2 py-0.5 text-xs font-medium text-amber-800">
                              low
                            </span>
                          ) : (
                            <span className="text-xs text-[#a5a8b5]">—</span>
                          )}
                        </td>
                        <td className="px-4 py-2 text-right tabular-nums text-[#1c1c1e]">
                          {m.source_count}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}
        </div>

        <div className="space-y-4">
          <div className="rounded-2xl bg-white p-4 shadow-[rgb(224_226_232)_0px_0px_0px_1px]">
            <h4 className="text-sm font-semibold text-[#1c1c1e]">
              {selected?.canonical_name ?? "—"}
            </h4>
            {selected && (
              <p className="mt-1 text-xs text-[#667085]">
                {selected.snomed && <span>SNOMED <code>{selected.snomed}</code></span>}
                {selected.rxnorm && <span> · RxNorm <code>{selected.rxnorm}</code></span>}
              </p>
            )}
            {selected && (
              <ul className="mt-3 space-y-1 text-sm">
                {selected.sources.map((s, i) => (
                  <li key={i} className="border-b border-[#eef0f4] py-1 last:border-b-0">
                    <div className="flex items-center justify-between">
                      <span className="font-medium text-[#1c1c1e]">{s.source_label}</span>
                      <span className="text-xs text-[#667085]">
                        {s.criticality ?? "—"}
                      </span>
                    </div>
                    <p className="text-xs text-[#667085]">{s.display}</p>
                  </li>
                ))}
              </ul>
            )}
          </div>
          <div className="rounded-2xl bg-white p-4 shadow-[rgb(224_226_232)_0px_0px_0px_1px]">
            <h4 className="mb-2 text-sm font-semibold text-[#1c1c1e]">
              Provenance lineage
            </h4>
            <ProvenancePanel
              collectionId={collectionId}
              mergedRef={selected?.merged_ref ?? null}
            />
          </div>
        </div>
      </div>
    </div>
  );
}

function ImmunizationsTab({ collectionId }: { collectionId: string }) {
  const [crossOnly, setCrossOnly] = useState(true);
  const [selectedRef, setSelectedRef] = useState<string | null>(null);

  const { data, isLoading } = useQuery({
    queryKey: ["harmonize-immunizations", collectionId, crossOnly],
    queryFn: () => api.getHarmonizeImmunizations(collectionId, crossOnly),
    enabled: !!collectionId,
  });

  const merged: HarmonizeMergedImmunization[] = data?.merged ?? [];
  const selected = useMemo(
    () => merged.find((m) => m.merged_ref === selectedRef) ?? merged[0] ?? null,
    [merged, selectedRef],
  );

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-1 gap-3 md:grid-cols-3">
        <MetricCard
          label="Immunization events"
          value={data?.total ?? 0}
          detail="Distinct (vaccine, date) events"
        />
        <MetricCard
          label="Cross-source merges"
          value={data?.cross_source ?? 0}
          detail="Events in ≥2 sources"
        />
        <MetricCard
          label="Most recent"
          value={
            merged.length > 0 && merged[merged.length - 1].occurrence_date
              ? merged[merged.length - 1].occurrence_date!.slice(0, 10)
              : "—"
          }
          detail="Latest occurrence date"
        />
      </div>

      <div className="flex items-center justify-between">
        <label className="flex items-center gap-2 text-sm text-[#667085]">
          <input
            type="checkbox"
            checked={crossOnly}
            onChange={(e) => {
              setCrossOnly(e.target.checked);
              setSelectedRef(null);
            }}
            className="h-4 w-4 rounded border-[#dfe4ea]"
          />
          Show only cross-source merges
        </label>
      </div>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
        <div className="lg:col-span-2 overflow-hidden rounded-2xl bg-white shadow-[rgb(224_226_232)_0px_0px_0px_1px]">
          {isLoading ? (
            <p className="p-6 text-sm text-[#667085]">Loading immunizations…</p>
          ) : merged.length === 0 ? (
            <p className="p-6 text-sm text-[#667085]">No immunizations to display.</p>
          ) : (
            <div className="max-h-[640px] overflow-y-auto">
              <table className="w-full text-sm">
                <thead className="sticky top-0 bg-[#f7f9fc] text-left text-xs font-semibold uppercase tracking-wider text-[#667085]">
                  <tr>
                    <th className="px-4 py-2">Date</th>
                    <th className="px-4 py-2">Vaccine</th>
                    <th className="px-4 py-2">CVX</th>
                    <th className="px-4 py-2 text-right">Sources</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-[#eef0f4] bg-white">
                  {merged.map((m) => {
                    const isSelected = selected?.merged_ref === m.merged_ref;
                    return (
                      <tr
                        key={m.merged_ref ?? m.canonical_name}
                        onClick={() => setSelectedRef(m.merged_ref)}
                        className={cls(
                          "cursor-pointer hover:bg-[#f7f9fc]",
                          isSelected && "bg-[#eef2ff]",
                        )}
                      >
                        <td className="px-4 py-2 tabular-nums text-[#667085]">
                          {m.occurrence_date ? m.occurrence_date.slice(0, 10) : "—"}
                        </td>
                        <td className="px-4 py-2 font-medium text-[#1c1c1e]">
                          {m.canonical_name.length > 50
                            ? m.canonical_name.slice(0, 50) + "…"
                            : m.canonical_name}
                        </td>
                        <td className="px-4 py-2 text-[#667085]">
                          <code className="text-xs">{m.cvx ?? "—"}</code>
                        </td>
                        <td className="px-4 py-2 text-right tabular-nums text-[#1c1c1e]">
                          {m.source_count}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}
        </div>

        <div className="space-y-4">
          <div className="rounded-2xl bg-white p-4 shadow-[rgb(224_226_232)_0px_0px_0px_1px]">
            <h4 className="text-sm font-semibold text-[#1c1c1e]">
              {selected?.canonical_name ?? "—"}
            </h4>
            {selected && (
              <p className="mt-1 text-xs text-[#667085]">
                {selected.cvx && <span>CVX <code>{selected.cvx}</code></span>}
                {selected.ndc && <span> · NDC <code>{selected.ndc}</code></span>}
                {selected.occurrence_date && (
                  <span> · {selected.occurrence_date.slice(0, 10)}</span>
                )}
              </p>
            )}
            {selected && (
              <ul className="mt-3 space-y-1 text-sm">
                {selected.sources.map((s, i) => (
                  <li key={i} className="border-b border-[#eef0f4] py-1 last:border-b-0">
                    <div className="flex items-center justify-between">
                      <span className="font-medium text-[#1c1c1e]">{s.source_label}</span>
                      <span className="text-xs text-[#667085]">
                        {s.status ?? "—"}
                      </span>
                    </div>
                    <p className="text-xs text-[#667085]">{s.display}</p>
                  </li>
                ))}
              </ul>
            )}
          </div>
          <div className="rounded-2xl bg-white p-4 shadow-[rgb(224_226_232)_0px_0px_0px_1px]">
            <h4 className="mb-2 text-sm font-semibold text-[#1c1c1e]">
              Provenance lineage
            </h4>
            <ProvenancePanel
              collectionId={collectionId}
              mergedRef={selected?.merged_ref ?? null}
            />
          </div>
        </div>
      </div>
    </div>
  );
}

export function HarmonizeView() {
  const [tab, setTab] = useState<ResourceTab>("labs");
  const queryClient = useQueryClient();
  const [searchParams] = useSearchParams();
  const requestedCollection = searchParams.get("collection");

  const collectionsQuery = useQuery({
    queryKey: ["harmonize-collections"],
    queryFn: () => api.getHarmonizeCollections(),
  });
  const collections = collectionsQuery.data?.collections ?? [];
  const [collectionId, setCollectionId] = useState<string>("");

  // Honor ?collection=<id> on first load — but only if the requested
  // collection actually exists in the registry. Otherwise fall back to
  // the first collection. We track sync via a flag so user picker
  // changes aren't overwritten on every render.
  const [hasSyncedFromUrl, setHasSyncedFromUrl] = useState(false);
  useEffect(() => {
    if (hasSyncedFromUrl || collections.length === 0) return;
    if (requestedCollection && collections.some((c) => c.id === requestedCollection)) {
      setCollectionId(requestedCollection);
    }
    setHasSyncedFromUrl(true);
  }, [collections, requestedCollection, hasSyncedFromUrl]);

  const activeId =
    collectionId || collections[0]?.id || "";
  const activeCollection = collections.find((c) => c.id === activeId) ?? null;
  const isUploadCollection = activeId.startsWith("upload-");

  const extractMutation = useMutation({
    mutationFn: () => api.extractHarmonizeCollection(activeId),
    onSuccess: () => {
      // Bust every harmonize-scoped query so source counts and merged
      // tables reflect the just-extracted PDFs.
      queryClient.invalidateQueries({ queryKey: ["harmonize-sources", activeId] });
      queryClient.invalidateQueries({ queryKey: ["harmonize-observations", activeId] });
      queryClient.invalidateQueries({ queryKey: ["harmonize-conditions", activeId] });
    },
  });

  return (
    <div className="space-y-6">
      <header className="rounded-2xl bg-gradient-to-br from-[#5b76fe] to-[#3651e8] p-6 text-white shadow-[rgb(224_226_232)_0px_0px_0px_1px]">
        <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wider opacity-90">
          <Layers3 size={14} />
          <span>Harmonize · Cross-source merge</span>
        </div>
        <h1 className="mt-2 text-2xl font-semibold">
          Build one canonical record from heterogeneous sources
        </h1>
        <p className="mt-2 max-w-3xl text-sm leading-6 opacity-90">
          The harmonization layer takes per-source FHIR resources from native
          pulls and vision-extracted PDFs, identity-resolves them by code or
          name bridge, and surfaces a longitudinal merged record with FHIR
          Provenance pointing back to every source observation.
        </p>
      </header>

      <div className="rounded-2xl bg-white p-5 shadow-[rgb(224_226_232)_0px_0px_0px_1px]">
        <div className="flex flex-wrap items-center gap-3">
          <label className="text-xs font-semibold uppercase tracking-wider text-[#667085]">
            Collection
          </label>
          <select
            value={activeId}
            onChange={(e) => {
              setCollectionId(e.target.value);
              extractMutation.reset();
            }}
            className="rounded-lg border border-[#dfe4ea] bg-white px-3 py-1.5 text-sm text-[#1c1c1e]"
          >
            {collections.map((c) => (
              <option key={c.id} value={c.id}>
                {c.name}
              </option>
            ))}
          </select>
          {activeCollection && (
            <span className="text-xs text-[#667085]">
              {activeCollection.source_count} sources
            </span>
          )}
          {isUploadCollection && (
            <button
              type="button"
              disabled={extractMutation.isPending}
              onClick={() => extractMutation.mutate()}
              className={cls(
                "ml-auto inline-flex items-center gap-2 rounded-lg px-3 py-1.5 text-sm font-medium transition-colors",
                extractMutation.isPending
                  ? "bg-[#dfe4ea] text-[#667085]"
                  : "bg-[#5b76fe] text-white hover:bg-[#4760e8]",
              )}
            >
              {extractMutation.isPending ? (
                <>
                  <Loader2 size={14} className="animate-spin" /> Extracting…
                </>
              ) : (
                <>
                  <Sparkles size={14} /> Extract uploaded PDFs
                </>
              )}
            </button>
          )}
        </div>
        {activeCollection && (
          <p className="mt-2 text-sm leading-6 text-[#667085]">
            {activeCollection.description}
          </p>
        )}
        {extractMutation.data && (
          <div className="mt-3 rounded-lg border border-[#dfe4ea] bg-[#f7f9fc] p-3 text-sm">
            <p className="font-semibold text-[#1c1c1e]">
              Extracted {extractMutation.data.extracted.length} PDF
              {extractMutation.data.extracted.length === 1 ? "" : "s"}
            </p>
            <ul className="mt-2 space-y-1 text-xs text-[#667085]">
              {extractMutation.data.extracted.map((e) => (
                <li key={e.source_id}>
                  <span className="font-medium text-[#1c1c1e]">{e.label}</span>
                  {": "}
                  {e.entry_count} resources
                  {e.cache_hit ? " (cached)" : ` (${e.elapsed_seconds.toFixed(1)}s)`}
                </li>
              ))}
            </ul>
          </div>
        )}
        {extractMutation.error && (
          <p className="mt-3 text-sm text-red-700">
            Extraction failed:{" "}
            {(extractMutation.error as Error).message ?? "unknown error"}
          </p>
        )}
      </div>

      {activeId && <SourcesPanel collectionId={activeId} />}

      <div className="rounded-2xl bg-white shadow-[rgb(224_226_232)_0px_0px_0px_1px]">
        <div className="flex items-center gap-2 border-b border-[#eef0f4] px-4">
          <button
            type="button"
            onClick={() => setTab("labs")}
            className={cls(
              "flex items-center gap-2 border-b-2 px-3 py-3 text-sm font-medium",
              tab === "labs"
                ? "border-[#5b76fe] text-[#5b76fe]"
                : "border-transparent text-[#667085] hover:text-[#1c1c1e]",
            )}
          >
            <Activity size={14} />
            Labs
          </button>
          <button
            type="button"
            onClick={() => setTab("conditions")}
            className={cls(
              "flex items-center gap-2 border-b-2 px-3 py-3 text-sm font-medium",
              tab === "conditions"
                ? "border-[#5b76fe] text-[#5b76fe]"
                : "border-transparent text-[#667085] hover:text-[#1c1c1e]",
            )}
          >
            <Stethoscope size={14} />
            Conditions
          </button>
          <button
            type="button"
            onClick={() => setTab("medications")}
            className={cls(
              "flex items-center gap-2 border-b-2 px-3 py-3 text-sm font-medium",
              tab === "medications"
                ? "border-[#5b76fe] text-[#5b76fe]"
                : "border-transparent text-[#667085] hover:text-[#1c1c1e]",
            )}
          >
            <Pill size={14} />
            Medications
          </button>
          <button
            type="button"
            onClick={() => setTab("allergies")}
            className={cls(
              "flex items-center gap-2 border-b-2 px-3 py-3 text-sm font-medium",
              tab === "allergies"
                ? "border-[#5b76fe] text-[#5b76fe]"
                : "border-transparent text-[#667085] hover:text-[#1c1c1e]",
            )}
          >
            <ShieldAlert size={14} />
            Allergies
          </button>
          <button
            type="button"
            onClick={() => setTab("immunizations")}
            className={cls(
              "flex items-center gap-2 border-b-2 px-3 py-3 text-sm font-medium",
              tab === "immunizations"
                ? "border-[#5b76fe] text-[#5b76fe]"
                : "border-transparent text-[#667085] hover:text-[#1c1c1e]",
            )}
          >
            <Syringe size={14} />
            Immunizations
          </button>
        </div>
        <div className="p-5">
          {activeId &&
            (tab === "labs" ? (
              <LabsTab collectionId={activeId} />
            ) : tab === "conditions" ? (
              <ConditionsTab collectionId={activeId} />
            ) : tab === "medications" ? (
              <MedicationsTab collectionId={activeId} />
            ) : tab === "allergies" ? (
              <AllergiesTab collectionId={activeId} />
            ) : (
              <ImmunizationsTab collectionId={activeId} />
            ))}
        </div>
      </div>

      <p className="text-xs leading-5 text-[#667085]">
        The Provenance graph is the Atlas wedge: every merged fact retains
        pointers back to its sources via FHIR Provenance entities. Atlas
        Extension URLs (<code>source-label</code>, <code>harmonize-activity</code>)
        carry the lineage that downstream consumers (clinician UI, agent
        assistant) read to render explainability.
      </p>
    </div>
  );
}

import type { ClinicalNoteItem } from "../types";

function fmtDate(value: string | null | undefined): string {
  if (!value) return "Unknown date";
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return value.slice(0, 10);
  return parsed.toLocaleDateString("en-US", { year: "numeric", month: "short", day: "numeric" });
}

function looksLikeSourceName(value: string | null | undefined): boolean {
  if (!value) return false;
  return /\.(json|pdf|csv|xml|txt)$/i.test(value) || /^[a-f0-9]{8,}-/i.test(value);
}

function friendlySourceName(value: string | null | undefined): string {
  if (!value) return "Source unavailable";
  return value.replace(/^[a-f0-9]{8,}-/i, "").replace(/_/g, " ");
}

export function clinicalNoteTitle(note: ClinicalNoteItem): string {
  return note.document_type || note.section_title || note.category || note.resource_type || "Clinical note";
}

export function clinicalNoteActor(note: ClinicalNoteItem): string {
  return (
    note.author ||
    note.organization ||
    note.provider ||
    note.site ||
    (looksLikeSourceName(note.source_label) ? friendlySourceName(note.source_label) : note.source_label) ||
    "Author not captured"
  );
}

function MetadataRow({ label, value, mono = false }: { label: string; value: string | null | undefined; mono?: boolean }) {
  if (!value) return null;
  return (
    <div className="flex gap-3 border-b border-slate-100 py-2 last:border-0">
      <span className="w-28 shrink-0 pt-0.5 text-[11px] font-semibold uppercase tracking-[0.12em] text-slate-400">
        {label}
      </span>
      <span className={mono ? "min-w-0 break-all font-mono text-[11px] text-slate-600" : "min-w-0 text-sm text-slate-700"}>
        {value}
      </span>
    </div>
  );
}

export function ClinicalNoteSummary({
  note,
  onOpen,
}: {
  note: ClinicalNoteItem;
  onOpen?: (note: ClinicalNoteItem) => void;
}) {
  const content = (
    <>
      <div className="flex flex-wrap items-center gap-2">
        <span className="rounded-full bg-slate-100 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-[0.12em] text-slate-500">
          {note.resource_type || "Note"}
        </span>
        <span className="text-xs text-slate-500">{fmtDate(note.date || note.linked_encounter_start)}</span>
      </div>
      <p className="mt-1 text-sm font-semibold leading-5 text-slate-900">{clinicalNoteTitle(note)}</p>
      <p className="mt-1 text-xs leading-5 text-slate-500">
        {clinicalNoteActor(note)}
        {note.linked_encounter_type ? ` - ${note.linked_encounter_type}` : ""}
      </p>
      <p className="mt-2 line-clamp-3 text-sm leading-6 text-slate-700">{note.preview || note.text || "No note text captured."}</p>
    </>
  );

  if (!onOpen) {
    return <div className="rounded-lg border border-slate-200 bg-slate-50 p-3">{content}</div>;
  }

  return (
    <button
      type="button"
      onClick={() => onOpen(note)}
      className="block w-full rounded-lg border border-slate-200 bg-white p-3 text-left transition-colors hover:border-[#5b76fe] hover:bg-[#f8faff]"
    >
      {content}
      <span className="mt-2 inline-flex text-xs font-semibold text-[#5b76fe]">Open note</span>
    </button>
  );
}

export function ClinicalNoteReader({ note }: { note: ClinicalNoteItem }) {
  return (
    <div className="space-y-4">
      <section className="rounded-xl border border-slate-200 bg-white p-4">
        <p className="text-xs font-semibold uppercase tracking-[0.14em] text-[#5b76fe]">Clinical note</p>
        <h3 className="mt-2 text-lg font-semibold text-slate-950">{clinicalNoteTitle(note)}</h3>
        <p className="mt-1 text-sm text-slate-600">{clinicalNoteActor(note)}</p>
      </section>

      <section className="rounded-xl border border-slate-200 bg-slate-50 p-4">
        <p className="text-xs font-semibold uppercase tracking-[0.14em] text-slate-500">Metadata</p>
        <div className="mt-2">
          <MetadataRow label="Date" value={fmtDate(note.date || note.linked_encounter_start)} />
          <MetadataRow label="Type" value={note.document_type || note.resource_type} />
          <MetadataRow label="Category" value={note.section_title || note.category} />
          <MetadataRow label="Encounter" value={note.linked_encounter_type || undefined} />
          <MetadataRow label="Provider" value={note.provider || note.author} />
          <MetadataRow label="Site" value={note.site || note.organization} />
          <MetadataRow label="Source" value={friendlySourceName(note.source_label)} />
        </div>
      </section>

      <section className="rounded-xl border border-slate-200 bg-white p-4">
        <p className="text-xs font-semibold uppercase tracking-[0.14em] text-slate-500">Note text</p>
        <p className="mt-3 max-h-[52vh] overflow-y-auto whitespace-pre-wrap text-sm leading-6 text-slate-700">
          {note.text || note.preview || "No note text captured."}
        </p>
      </section>

      <details className="rounded-xl border border-slate-200 bg-white p-4">
        <summary className="cursor-pointer text-sm font-semibold text-slate-700">Technical provenance</summary>
        <div className="mt-3">
          <MetadataRow label="Source ID" value={note.source_id} mono />
          <MetadataRow label="Resource" value={`${note.resource_type}/${note.resource_id}`} mono />
          <MetadataRow label="Note index" value={String(note.note_index)} mono />
          <MetadataRow label="Encounter ID" value={note.linked_encounter_id || note.encounter_id || undefined} mono />
          <MetadataRow label="MIME" value={note.attachment_content_type || undefined} mono />
        </div>
      </details>
    </div>
  );
}

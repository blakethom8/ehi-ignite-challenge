import { useMemo, useState } from "react";
import {
  BookMarked,
  Pin,
  Save,
  Sparkles,
  X,
} from "lucide-react";
import type { LucideIcon } from "lucide-react";
import type {
  Citation,
  SaveDestination,
  SaveRequest,
} from "../../../../types/skills";

interface SaveDestinationDrawerProps {
  open: boolean;
  onClose: () => void;
  onSave: (payload: SaveRequest) => Promise<void>;
  isSaving: boolean;
  citations: Citation[];
  defaultPackageName?: string;
}

const DESTINATIONS: Array<{
  key: SaveDestination;
  icon: LucideIcon;
  label: string;
  body: string;
}> = [
  {
    key: "run",
    icon: Save,
    label: "Annotate this run",
    body:
      "Edits live in this run only. Future runs do not see them. Closes the audit trail with your notes attached.",
  },
  {
    key: "patient",
    icon: Pin,
    label: "Pin to patient memory",
    body:
      "Promote selected facts to /_memory/pinned.md. Every future skill run for this patient sees them at session start.",
  },
  {
    key: "package",
    icon: BookMarked,
    label: "Save as patient context package",
    body:
      "Materialize a reusable named bundle. Other skills can declare it in `context_packages:` to inherit it.",
  },
];

/**
 * The three save destinations from `SELF-MODIFYING-WORKSPACE.md`. The drawer
 * branches on the chosen destination — different inputs are required for
 * each. The runtime contract is the same; only the payload shape differs.
 */
export function SaveDestinationDrawer({
  open,
  onClose,
  onSave,
  isSaving,
  citations,
  defaultPackageName,
}: SaveDestinationDrawerProps) {
  const [destination, setDestination] = useState<SaveDestination>("run");
  const [editsMarkdown, setEditsMarkdown] = useState("");
  const [packageName, setPackageName] = useState(defaultPackageName ?? "");
  const [packageContent, setPackageContent] = useState("");
  const [pinnedTexts, setPinnedTexts] = useState<Record<string, string>>({});
  const [pinnedSelected, setPinnedSelected] = useState<Set<string>>(new Set());

  const fhirCitations = useMemo(
    () =>
      citations.filter(
        (c) =>
          c.source_kind === "fhir_resource" || c.source_kind === "external_url"
      ),
    [citations]
  );

  if (!open) return null;

  const togglePinned = (id: string) => {
    setPinnedSelected((prev) => {
      const next = new Set(prev);
      if (next.has(id)) {
        next.delete(id);
      } else {
        next.add(id);
        setPinnedTexts((textPrev) => {
          if (textPrev[id]) return textPrev;
          const seeded = citations.find((c) => c.citation_id === id)?.claim ?? "";
          return { ...textPrev, [id]: seeded };
        });
      }
      return next;
    });
  };

  const submit = async () => {
    if (destination === "run") {
      if (!editsMarkdown.trim()) return;
      await onSave({ destination, edits_markdown: editsMarkdown.trim() });
      return;
    }
    if (destination === "patient") {
      const facts = Array.from(pinnedSelected)
        .map((id) => ({
          text: (pinnedTexts[id] ?? "").trim(),
          citation_id: id,
        }))
        .filter((f) => f.text.length > 0);
      if (!facts.length) return;
      await onSave({ destination, facts });
      return;
    }
    if (!packageName.trim() || !packageContent.trim()) return;
    await onSave({
      destination,
      package_name: packageName.trim(),
      package_content: packageContent.trim(),
    });
  };

  return (
    <div className="fixed inset-0 z-40 flex items-stretch justify-end bg-black/30">
      <aside
        className="flex h-full w-full max-w-xl flex-col overflow-hidden bg-white shadow-2xl"
        onClick={(e) => e.stopPropagation()}
      >
        <header className="flex items-center justify-between border-b border-[#e9eaef] px-6 py-4">
          <div>
            <p className="text-[10px] font-semibold uppercase tracking-wider text-[#5b76fe]">
              Save destination
            </p>
            <h2 className="mt-1 text-lg font-semibold text-[#1c1c1e]">
              Where should this go?
            </h2>
          </div>
          <button
            onClick={onClose}
            type="button"
            className="rounded-full p-1.5 text-[#555a6a] hover:bg-[#f5f6f8]"
            aria-label="Close drawer"
          >
            <X size={18} />
          </button>
        </header>

        <div className="grid grid-cols-3 gap-2 border-b border-[#e9eaef] px-6 py-4">
          {DESTINATIONS.map((d) => {
            const Icon = d.icon;
            const active = d.key === destination;
            return (
              <button
                key={d.key}
                type="button"
                onClick={() => setDestination(d.key)}
                className={`flex flex-col items-start gap-2 rounded-xl border p-3 text-left transition ${
                  active
                    ? "border-[#5b76fe] bg-[#eef1ff]"
                    : "border-[#e9eaef] bg-white hover:bg-[#fafafb]"
                }`}
              >
                <Icon size={16} className={active ? "text-[#5b76fe]" : "text-[#555a6a]"} />
                <span
                  className={`text-xs font-semibold ${
                    active ? "text-[#3a4ca8]" : "text-[#1c1c1e]"
                  }`}
                >
                  {d.label}
                </span>
              </button>
            );
          })}
        </div>

        <div className="flex-1 overflow-y-auto px-6 py-5">
          <p className="text-xs leading-5 text-[#555a6a]">
            {DESTINATIONS.find((d) => d.key === destination)?.body}
          </p>

          {destination === "run" ? (
            <label className="mt-4 block text-xs font-semibold text-[#1c1c1e]">
              Your annotations
              <textarea
                value={editsMarkdown}
                onChange={(e) => setEditsMarkdown(e.target.value)}
                rows={12}
                placeholder="What did you change, add, or want recorded against this run?"
                className="mt-2 w-full rounded-lg border border-[#e9eaef] bg-white px-3 py-2 font-mono text-[12px] text-[#1c1c1e] focus:border-[#5b76fe] focus:outline-none"
              />
            </label>
          ) : null}

          {destination === "patient" ? (
            <div className="mt-4 space-y-3">
              {fhirCitations.length === 0 ? (
                <p className="rounded-xl border border-dashed border-[#e9eaef] p-4 text-xs text-[#a5a8b5]">
                  No citation-grounded facts in this run yet.
                </p>
              ) : (
                <div className="space-y-2">
                  {fhirCitations.map((c) => {
                    const checked = pinnedSelected.has(c.citation_id);
                    return (
                      <div
                        key={c.citation_id}
                        className={`rounded-xl border p-3 ${
                          checked ? "border-[#5b76fe] bg-[#eef1ff]" : "border-[#e9eaef] bg-white"
                        }`}
                      >
                        <label className="flex items-start gap-3">
                          <input
                            type="checkbox"
                            checked={checked}
                            onChange={() => togglePinned(c.citation_id)}
                            className="mt-1"
                          />
                          <div className="min-w-0 flex-1">
                            <p className="font-mono text-[10px] text-[#5b76fe]">
                              {c.citation_id} · {c.evidence_tier} · {c.source_kind}
                            </p>
                            <p className="mt-1 text-sm font-medium text-[#1c1c1e]">
                              {c.claim}
                            </p>
                            {checked ? (
                              <textarea
                                value={pinnedTexts[c.citation_id] ?? ""}
                                onChange={(e) =>
                                  setPinnedTexts((prev) => ({
                                    ...prev,
                                    [c.citation_id]: e.target.value,
                                  }))
                                }
                                rows={2}
                                placeholder="Refine the text the next agent will see…"
                                className="mt-2 w-full rounded-lg border border-[#e9eaef] bg-white px-2 py-1.5 text-[12px] text-[#1c1c1e] focus:border-[#5b76fe] focus:outline-none"
                              />
                            ) : null}
                          </div>
                        </label>
                      </div>
                    );
                  })}
                </div>
              )}
              <p className="rounded-xl bg-[#f5f6f8] p-3 text-[11px] text-[#555a6a]">
                <Sparkles size={12} className="mr-1 inline" /> Pinned facts
                carry their citation chip — the next agent that reads patient
                memory sees the original source.
              </p>
            </div>
          ) : null}

          {destination === "package" ? (
            <div className="mt-4 space-y-3">
              <label className="block text-xs font-semibold text-[#1c1c1e]">
                Package name
                <input
                  value={packageName}
                  onChange={(e) => setPackageName(e.target.value)}
                  placeholder="patient-trial-prefs"
                  className="mt-1 w-full rounded-lg border border-[#e9eaef] bg-white px-3 py-2 font-mono text-[12px] text-[#1c1c1e] focus:border-[#5b76fe] focus:outline-none"
                />
              </label>
              <label className="block text-xs font-semibold text-[#1c1c1e]">
                Markdown content
                <textarea
                  value={packageContent}
                  onChange={(e) => setPackageContent(e.target.value)}
                  rows={10}
                  placeholder="## Patient preferences&#10;&#10;- Geography: West Coast only&#10;- Will not enroll in placebo arms"
                  className="mt-2 w-full rounded-lg border border-[#e9eaef] bg-white px-3 py-2 font-mono text-[12px] text-[#1c1c1e] focus:border-[#5b76fe] focus:outline-none"
                />
              </label>
              <p className="rounded-xl bg-[#f5f6f8] p-3 text-[11px] text-[#555a6a]">
                Other skills can reference this package by name in their
                <code className="mx-1 rounded bg-white px-1 font-mono">context_packages:</code>
                frontmatter. The runner mounts it into their session-start
                context automatically.
              </p>
            </div>
          ) : null}
        </div>

        <footer className="flex items-center justify-end gap-2 border-t border-[#e9eaef] px-6 py-3">
          <button
            type="button"
            onClick={onClose}
            className="rounded-lg border border-[#c7cad5] bg-white px-3 py-2 text-xs font-semibold text-[#1c1c1e] hover:bg-[#fafafb]"
          >
            Cancel
          </button>
          <button
            type="button"
            onClick={submit}
            disabled={isSaving}
            className="inline-flex items-center gap-2 rounded-lg bg-[#5b76fe] px-4 py-2 text-xs font-semibold text-white shadow-sm disabled:cursor-not-allowed disabled:opacity-60"
            style={{ letterSpacing: 0.175 }}
          >
            <Save size={14} />
            {isSaving ? "Saving…" : "Save"}
          </button>
        </footer>
      </aside>
    </div>
  );
}

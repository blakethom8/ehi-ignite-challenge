import { FileText, Quote } from "lucide-react";

export type CitationChipProps = {
  /** Citation id (e.g. "c_1042") or filename (e.g. "pre-op-packet-v2.md"). */
  id: string;
  active?: boolean;
  onClick?: (id: string) => void;
  /** Override the auto-detected kind. */
  kind?: "citation" | "file";
};

/**
 * Inline reference chip used in chat bodies, dense tables, and artifact
 * preview docs. Clicking pushes the chip's id to the inspector store
 * (the parent decides what that means).
 */
export function CitationChip({ id, active = false, onClick, kind }: CitationChipProps) {
  const resolvedKind = kind ?? (id.startsWith("c_") ? "citation" : "file");
  return (
    <span
      onClick={() => onClick?.(id)}
      className="mx-0.5 inline-flex cursor-pointer items-center gap-1 rounded-[4px] border px-1.5 align-baseline text-[11px] leading-[1.4] transition-colors hover:border-[var(--action-line)] hover:bg-[var(--action-tint)]"
      style={{
        background: active ? "var(--action-tint-2)" : "var(--surface-0)",
        borderColor: active ? "var(--action)" : "var(--line-1)",
        color: "var(--action)",
        fontFamily: "var(--font-mono)",
      }}
    >
      {resolvedKind === "citation" ? (
        <Quote className="h-2 w-2" strokeWidth={1.5} />
      ) : (
        <FileText className="h-2 w-2" strokeWidth={1.5} />
      )}
      {id}
    </span>
  );
}

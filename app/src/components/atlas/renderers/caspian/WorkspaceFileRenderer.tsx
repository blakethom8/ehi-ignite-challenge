import { useEffect, useState } from "react";
import { Edit3, RotateCcw, Save } from "lucide-react";
import type { RendererProps } from "../types";
import type { CaspianFileBlob } from "../../useCaspianFiles";

/**
 * WorkspaceFileRenderer
 *
 * Renders a `CaspianFileBlob` from canvas[tabId]. Markdown gets a light
 * formatter; JSON gets pretty-printed; everything else falls back to plain
 * monospaced text. If `blob.editable` is true and `canvas.__files.saveFile`
 * is wired, the renderer offers an Edit toggle that flips into a textarea
 * with Save / Cancel.
 */
export function WorkspaceFileRenderer({ canvas, tabId }: RendererProps) {
  const blob = canvas[tabId] as CaspianFileBlob | undefined;
  const filesApi = canvas.__files as
    | {
        openFile: (path: string) => Promise<CaspianFileBlob | null>;
        saveFile: (path: string, content: string) => Promise<unknown>;
        refreshFile: (path: string) => Promise<CaspianFileBlob | null>;
      }
    | undefined;

  const [draft, setDraft] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // If the blob isn't in the canvas yet, trigger a load. The hook's
  // openFile() is referentially stable so this effect only re-runs on tabId
  // changes; the in-flight ref de-dupes concurrent calls.
  useEffect(() => {
    if (!blob && filesApi?.openFile) {
      void filesApi.openFile(tabId);
    }
  }, [blob, tabId, filesApi]);

  useEffect(() => {
    setDraft(null);
    setError(null);
  }, [blob?.path]);

  if (!blob) {
    return (
      <div className="px-10 py-8 text-[13px]" style={{ color: "var(--ink-4)" }}>
        Loading file…
      </div>
    );
  }

  const editing = draft !== null;
  const editable = blob.editable && Boolean(filesApi);

  const onEdit = () => {
    setDraft(blob.content);
    setError(null);
  };
  const onCancel = () => {
    setDraft(null);
    setError(null);
  };
  const onSave = async () => {
    if (draft === null || !filesApi) return;
    setSaving(true);
    setError(null);
    try {
      await filesApi.saveFile(blob.path, draft);
      setDraft(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setSaving(false);
    }
  };

  const body = editing ? draft! : blob.content;
  const isEmptyUserInstructions =
    !editing && blob.path === "user-instructions.md" && body.trim().length === 0;

  return (
    <div className="mx-auto max-w-[860px] px-10 pb-16 pt-8" style={{ fontFamily: "var(--font-sans)" }}>
      <div className="mb-5 flex items-baseline justify-between">
        <div>
          <h1
            className="text-[22px] font-semibold tracking-tight"
            style={{ fontFamily: "var(--font-serif)", color: "var(--ink-1)" }}
          >
            {blob.path}
          </h1>
          <div className="mt-1 flex items-center gap-3 text-[11.5px]" style={{ color: "var(--ink-4)" }}>
            <span style={{ fontFamily: "var(--font-mono)" }}>{blob.kind}</span>
            {blob.mtime && (
              <span style={{ fontFamily: "var(--font-mono)" }}>{formatMtime(blob.mtime)}</span>
            )}
            {!blob.editable && (
              <span
                className="rounded-full px-1.5 py-px text-[10px] uppercase tracking-wider"
                style={{ background: "var(--surface-2)", color: "var(--ink-3)" }}
              >
                read only
              </span>
            )}
          </div>
        </div>
        {editable && (
          <div className="flex items-center gap-1.5">
            {editing ? (
              <>
                <button
                  onClick={onCancel}
                  disabled={saving}
                  className="inline-flex h-[26px] items-center gap-1 rounded-md border px-2.5 text-[11.5px] font-medium hover:bg-[var(--surface-2)]"
                  style={{ borderColor: "var(--line-1)", color: "var(--ink-2)" }}
                >
                  <RotateCcw className="h-3 w-3" strokeWidth={1.5} /> Cancel
                </button>
                <button
                  onClick={onSave}
                  disabled={saving}
                  className="inline-flex h-[26px] items-center gap-1 rounded-md px-2.5 text-[11.5px] font-semibold text-white"
                  style={{ background: "var(--action)" }}
                >
                  <Save className="h-3 w-3" strokeWidth={1.5} />
                  {saving ? "Saving…" : "Save"}
                </button>
              </>
            ) : (
              <button
                onClick={onEdit}
                className="inline-flex h-[26px] items-center gap-1 rounded-md border px-2.5 text-[11.5px] font-medium hover:bg-[var(--surface-2)]"
                style={{ borderColor: "var(--line-1)", color: "var(--ink-2)" }}
              >
                <Edit3 className="h-3 w-3" strokeWidth={1.5} /> Edit
              </button>
            )}
          </div>
        )}
      </div>

      {error && (
        <div
          className="mb-4 rounded-md border px-3 py-2 text-[12px]"
          style={{
            background: "var(--critical-tint, rgba(185,28,28,0.08))",
            borderColor: "var(--critical-line, rgba(185,28,28,0.35))",
            color: "var(--critical, #b91c1c)",
          }}
        >
          {error}
        </div>
      )}

      {editing ? (
        <textarea
          value={body}
          onChange={(e) => setDraft(e.target.value)}
          className="block min-h-[420px] w-full rounded-md border bg-transparent p-3 text-[13px] outline-none"
          style={{
            background: "var(--surface-0)",
            borderColor: "var(--line-1)",
            color: "var(--ink-1)",
            fontFamily: "var(--font-mono)",
            lineHeight: 1.55,
          }}
        />
      ) : isEmptyUserInstructions ? (
        <div
          className="rounded-md border border-dashed p-4 text-[13px]"
          style={{
            borderColor: "var(--line-2)",
            color: "var(--ink-3)",
            background: "var(--surface-1)",
          }}
        >
          <p className="mb-2 font-medium" style={{ color: "var(--ink-1)" }}>
            Teach Caspian about this workspace.
          </p>
          <p className="leading-[1.6]">
            Anything you write here is appended to Caspian's system prompt on every
            chat turn for this patient. Examples: "Always prefer SI units", "Refer
            to the patient as 'they' in summaries", "Treat NSAIDs as contraindicated".
          </p>
          {editable && (
            <button
              onClick={onEdit}
              className="mt-3 inline-flex h-[26px] items-center gap-1 rounded-md px-2.5 text-[11.5px] font-semibold text-white"
              style={{ background: "var(--action)" }}
            >
              <Edit3 className="h-3 w-3" strokeWidth={1.5} /> Start writing
            </button>
          )}
        </div>
      ) : (
        renderBody(blob.kind, body)
      )}
    </div>
  );
}

function renderBody(kind: CaspianFileBlob["kind"], body: string) {
  if (kind === "json") {
    return (
      <pre
        className="overflow-x-auto rounded-md border p-3 text-[12.5px] leading-[1.6]"
        style={{
          background: "var(--surface-1)",
          borderColor: "var(--line-1)",
          color: "var(--ink-1)",
          fontFamily: "var(--font-mono)",
        }}
      >
        {tryPrettyJson(body)}
      </pre>
    );
  }
  if (kind === "markdown") {
    return <MarkdownBody body={body} />;
  }
  return (
    <pre
      className="overflow-x-auto whitespace-pre-wrap rounded-md border p-3 text-[12.5px] leading-[1.7]"
      style={{
        background: "var(--surface-1)",
        borderColor: "var(--line-1)",
        color: "var(--ink-1)",
        fontFamily: "var(--font-mono)",
      }}
    >
      {body}
    </pre>
  );
}

function tryPrettyJson(body: string): string {
  try {
    return JSON.stringify(JSON.parse(body), null, 2);
  } catch {
    return body;
  }
}

/**
 * Minimal markdown body renderer — same lightweight formatting the
 * MarkdownDocRenderer uses, with table support added so workflow-run
 * artifacts render their banner / fact-rail / section tables.
 */
function MarkdownBody({ body }: { body: string }) {
  const blocks: React.ReactNode[] = [];
  const lines = body.split("\n");
  let i = 0;
  while (i < lines.length) {
    const line = lines[i];
    // Table: header line | cell | cell | …  followed by  | --- | --- |
    if (line.includes("|") && i + 1 < lines.length && /^\s*\|?\s*[-:]{3,}/.test(lines[i + 1])) {
      const headerCells = splitRow(line);
      const tableRows: string[][] = [];
      let j = i + 2;
      while (j < lines.length && lines[j].includes("|")) {
        const row = splitRow(lines[j]);
        if (row.length === 0) break;
        tableRows.push(row);
        j += 1;
      }
      blocks.push(
        <table
          key={`t-${i}`}
          className="mb-3 w-full border-collapse text-[12.5px]"
          style={{ tableLayout: "auto" }}
        >
          <thead>
            <tr style={{ borderBottom: "1px solid var(--line-1)" }}>
              {headerCells.map((c, idx) => (
                <th
                  key={idx}
                  className="px-2.5 py-1.5 text-left text-[10.5px] font-semibold uppercase tracking-wider"
                  style={{ color: "var(--ink-4)" }}
                >
                  {c}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {tableRows.map((row, ri) => (
              <tr key={ri} style={{ borderBottom: "1px solid var(--line-1)" }}>
                {row.map((cell, ci) => (
                  <td
                    key={ci}
                    className="px-2.5 py-1.5 align-top"
                    style={{ color: "var(--ink-2)" }}
                  >
                    {cell}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>,
      );
      i = j;
      continue;
    }
    if (line.startsWith("# ")) {
      blocks.push(
        <h1
          key={i}
          className="mb-2 mt-3 text-[24px] font-semibold tracking-tight"
          style={{ fontFamily: "var(--font-serif)", color: "var(--ink-1)" }}
        >
          {line.slice(2)}
        </h1>,
      );
    } else if (line.startsWith("## ")) {
      blocks.push(
        <h2
          key={i}
          className="mb-2 mt-5 text-[17px] font-semibold tracking-tight"
          style={{ fontFamily: "var(--font-serif)", color: "var(--ink-1)" }}
        >
          {line.slice(3)}
        </h2>,
      );
    } else if (line.startsWith("### ")) {
      blocks.push(
        <h3
          key={i}
          className="mb-1 mt-3 text-[13px] font-semibold uppercase tracking-wider"
          style={{ color: "var(--ink-2)" }}
        >
          {line.slice(4)}
        </h3>,
      );
    } else if (line.startsWith("> ")) {
      blocks.push(
        <blockquote
          key={i}
          className="my-2 border-l-2 pl-3 text-[14px] italic leading-[1.65]"
          style={{ borderColor: "var(--action)", color: "var(--ink-2)" }}
        >
          {line.slice(2)}
        </blockquote>,
      );
    } else if (line.startsWith("- ")) {
      blocks.push(
        <div
          key={i}
          className="ml-4 text-[13.5px] leading-[1.65]"
          style={{ color: "var(--ink-2)" }}
        >
          • {renderInlineMarkdown(line.slice(2))}
        </div>,
      );
    } else if (line.startsWith("```")) {
      const close = lines.indexOf("```", i + 1);
      const codeEnd = close === -1 ? lines.length : close;
      const code = lines.slice(i + 1, codeEnd).join("\n");
      blocks.push(
        <pre
          key={i}
          className="my-3 overflow-x-auto rounded-md border p-3 text-[12px] leading-[1.6]"
          style={{
            background: "var(--surface-1)",
            borderColor: "var(--line-1)",
            color: "var(--ink-1)",
            fontFamily: "var(--font-mono)",
          }}
        >
          {code}
        </pre>,
      );
      i = codeEnd + 1;
      continue;
    } else if (!line.trim()) {
      blocks.push(<div key={i} className="h-3" />);
    } else {
      blocks.push(
        <p
          key={i}
          className="my-1.5 text-[14px] leading-[1.65]"
          style={{ color: "var(--ink-2)" }}
        >
          {renderInlineMarkdown(line)}
        </p>,
      );
    }
    i += 1;
  }
  return <>{blocks}</>;
}

function splitRow(line: string): string[] {
  const trimmed = line.trim();
  const inside = trimmed.replace(/^\|/, "").replace(/\|$/, "");
  return inside
    .split("|")
    .map((cell) => cell.trim())
    .filter((cell, idx, arr) => !(idx === arr.length - 1 && cell === ""));
}

function renderInlineMarkdown(text: string): React.ReactNode {
  // Render **bold** spans only; keep everything else plain.
  const parts: React.ReactNode[] = [];
  const regex = /\*\*([^*]+)\*\*/g;
  let last = 0;
  let m: RegExpExecArray | null;
  while ((m = regex.exec(text)) !== null) {
    if (m.index > last) parts.push(text.slice(last, m.index));
    parts.push(
      <strong key={`b-${m.index}`} style={{ color: "var(--ink-1)", fontWeight: 600 }}>
        {m[1]}
      </strong>,
    );
    last = m.index + m[0].length;
  }
  if (last < text.length) parts.push(text.slice(last));
  return parts.length === 0 ? text : parts;
}

function formatMtime(value: string): string {
  try {
    const dt = new Date(value);
    if (Number.isNaN(dt.getTime())) return value;
    return dt.toLocaleString("en-US", {
      month: "short",
      day: "2-digit",
      year: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    });
  } catch {
    return value;
  }
}

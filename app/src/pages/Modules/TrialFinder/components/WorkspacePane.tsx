import { Fragment, type ReactNode } from "react";
import type { Citation } from "../../../../types/skills";
import { CitationChip } from "./CitationChip";

interface WorkspacePaneProps {
  markdown: string;
  citations: Citation[];
}

/**
 * Renders the workspace.md stream with citation chips substituted for
 * `[cite:c_NNNN]` markers. We deliberately ship a small inline parser
 * instead of pulling in react-markdown — workspace.md is structured
 * enough (headings, paragraphs, lists, bold) that ~80 lines covers it,
 * and we get to control how citation chips slot in without a remark
 * plugin.
 */
export function WorkspacePane({ markdown, citations }: WorkspacePaneProps) {
  const byId = new Map<string, Citation>(
    citations.map((c) => [c.citation_id, c] as const)
  );
  const blocks = parseBlocks(markdown);

  return (
    <article className="space-y-4 text-[15px] leading-7 text-[#1c1c1e]">
      {blocks.map((block, idx) => (
        <BlockRenderer key={idx} block={block} citationsById={byId} />
      ))}
    </article>
  );
}

// ── Block parsing ──────────────────────────────────────────────────────────

type Block =
  | { kind: "h1" | "h2" | "h3" | "h4"; text: string }
  | { kind: "paragraph"; text: string }
  | { kind: "ul"; items: string[] }
  | { kind: "hr" }
  | { kind: "html-comment"; text: string };

function parseBlocks(markdown: string): Block[] {
  // Strip HTML comments so anchor markers don't leak into the rendered view.
  const cleaned = markdown.replace(/<!--[\s\S]*?-->/g, "");
  const rawBlocks = cleaned.split(/\n{2,}/);
  const blocks: Block[] = [];

  for (const raw of rawBlocks) {
    const block = raw.trim();
    if (!block) continue;

    if (block === "---") {
      blocks.push({ kind: "hr" });
      continue;
    }

    const lines = block.split("\n");
    const looksLikeList = lines.every((l) => /^(\s*[-*•]\s+)/.test(l));
    if (looksLikeList) {
      blocks.push({
        kind: "ul",
        items: lines.map((l) => l.replace(/^\s*[-*•]\s+/, "")),
      });
      continue;
    }

    const headingMatch = block.match(/^(#{1,4})\s+(.*)$/);
    if (headingMatch && lines.length === 1) {
      const level = headingMatch[1].length as 1 | 2 | 3 | 4;
      const kind = (`h${level}` as Block["kind"]);
      blocks.push({ kind, text: headingMatch[2] } as Block);
      continue;
    }

    blocks.push({ kind: "paragraph", text: block });
  }

  return blocks;
}

// ── Inline renderer ────────────────────────────────────────────────────────

function BlockRenderer({
  block,
  citationsById,
}: {
  block: Block;
  citationsById: Map<string, Citation>;
}) {
  switch (block.kind) {
    case "h1":
      return (
        <h1 className="text-2xl font-semibold tracking-tight text-[#1c1c1e]">
          {renderInline(block.text, citationsById)}
        </h1>
      );
    case "h2":
      return (
        <h2 className="mt-2 text-xl font-semibold tracking-tight text-[#1c1c1e]">
          {renderInline(block.text, citationsById)}
        </h2>
      );
    case "h3":
      return (
        <h3 className="mt-2 text-base font-semibold text-[#1c1c1e]">
          {renderInline(block.text, citationsById)}
        </h3>
      );
    case "h4":
      return (
        <h4 className="text-sm font-semibold uppercase tracking-wide text-[#555a6a]">
          {renderInline(block.text, citationsById)}
        </h4>
      );
    case "ul":
      return (
        <ul className="ml-5 list-disc space-y-1.5">
          {block.items.map((item, idx) => (
            <li key={idx}>{renderInline(item, citationsById)}</li>
          ))}
        </ul>
      );
    case "hr":
      return <hr className="border-[#e9eaef]" />;
    case "html-comment":
      return <Fragment />;
    case "paragraph":
    default:
      return (
        <p className="text-[15px] leading-7 text-[#1c1c1e]">
          {renderInline((block as { text: string }).text, citationsById)}
        </p>
      );
  }
}

function renderInline(
  text: string,
  citationsById: Map<string, Citation>
): ReactNode {
  // Tokens we care about: [cite:c_NNNN] and **bold** and _italic_ and `code`.
  const out: ReactNode[] = [];
  const pattern = /(\[cite:c_\d{4}\])|(\*\*[^*]+\*\*)|(_[^_]+_)|(`[^`]+`)/g;
  let lastIndex = 0;
  let match: RegExpExecArray | null;
  let key = 0;

  while ((match = pattern.exec(text)) !== null) {
    if (match.index > lastIndex) {
      out.push(text.slice(lastIndex, match.index));
    }
    const token = match[0];
    if (token.startsWith("[cite:")) {
      const id = token.slice(6, -1);
      const citation = citationsById.get(id);
      if (citation) {
        out.push(<CitationChip key={`c${key++}`} citation={citation} />);
      } else {
        // Unresolved citation — render as muted placeholder rather than
        // dropping it silently, so the audit trail is visible in the UI.
        out.push(
          <span
            key={`u${key++}`}
            className="inline-flex items-center rounded border border-dashed border-[#c7cad5] px-1.5 text-[10px] font-mono text-[#a5a8b5]"
          >
            {id} · unresolved
          </span>
        );
      }
    } else if (token.startsWith("**")) {
      out.push(
        <strong key={`b${key++}`} className="font-semibold text-[#1c1c1e]">
          {token.slice(2, -2)}
        </strong>
      );
    } else if (token.startsWith("_")) {
      out.push(
        <em key={`i${key++}`} className="italic text-[#555a6a]">
          {token.slice(1, -1)}
        </em>
      );
    } else if (token.startsWith("`")) {
      out.push(
        <code
          key={`m${key++}`}
          className="rounded bg-[#f5f6f8] px-1 py-0.5 font-mono text-[12px] text-[#555a6a]"
        >
          {token.slice(1, -1)}
        </code>
      );
    }
    lastIndex = match.index + token.length;
  }
  if (lastIndex < text.length) {
    out.push(text.slice(lastIndex));
  }
  return out;
}

import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { X, Search, ChevronDown, ChevronRight, Copy, Check } from "lucide-react";
import { api } from "../api/client";

const LOADING_BAR_WIDTHS = [72, 58, 86, 64, 78, 52, 91, 69, 83, 47, 76, 61, 88, 55, 80, 66, 93, 50, 74, 59];

interface FhirViewerProps {
  patientId: string;
  patientName: string;
  onClose: () => void;
}

/** Collapsible JSON tree node */
function JsonNode({ keyName, value, depth = 0 }: { keyName?: string; value: unknown; depth?: number }) {
  const [expanded, setExpanded] = useState(depth < 2);

  if (value === null) {
    return (
      <div className="flex gap-1" style={{ paddingLeft: depth * 16 }}>
        {keyName && <span className="text-[#5b76fe]">"{keyName}"</span>}
        {keyName && <span className="text-[#555a6a]">: </span>}
        <span className="text-[#a5a8b5] italic">null</span>
      </div>
    );
  }

  if (typeof value === "string") {
    return (
      <div className="flex gap-1" style={{ paddingLeft: depth * 16 }}>
        {keyName && <span className="text-[#5b76fe]">"{keyName}"</span>}
        {keyName && <span className="text-[#555a6a]">: </span>}
        <span className="text-[#187574]">"{value}"</span>
      </div>
    );
  }

  if (typeof value === "number" || typeof value === "boolean") {
    return (
      <div className="flex gap-1" style={{ paddingLeft: depth * 16 }}>
        {keyName && <span className="text-[#5b76fe]">"{keyName}"</span>}
        {keyName && <span className="text-[#555a6a]">: </span>}
        <span className="text-[#744000]">{String(value)}</span>
      </div>
    );
  }

  const isArray = Array.isArray(value);
  const entries = isArray
    ? (value as unknown[]).map((v, i) => [String(i), v] as [string, unknown])
    : Object.entries(value as Record<string, unknown>);
  const bracket = isArray ? ["[", "]"] : ["{", "}"];
  const preview = isArray ? `Array(${entries.length})` : `{${entries.length} keys}`;

  return (
    <div style={{ paddingLeft: depth * 16 }}>
      <button
        onClick={() => setExpanded(!expanded)}
        className="flex items-center gap-1 hover:bg-[#f5f6f8] rounded px-0.5 -ml-0.5"
      >
        {expanded ? <ChevronDown size={12} className="text-[#a5a8b5]" /> : <ChevronRight size={12} className="text-[#a5a8b5]" />}
        {keyName && <span className="text-[#5b76fe]">"{keyName}"</span>}
        {keyName && <span className="text-[#555a6a]">: </span>}
        {!expanded && <span className="text-[#a5a8b5] text-xs">{preview}</span>}
        {expanded && <span className="text-[#555a6a]">{bracket[0]}</span>}
      </button>
      {expanded && (
        <>
          {entries.map(([k, v]) => (
            <JsonNode key={k} keyName={isArray ? undefined : k} value={v} depth={depth + 1} />
          ))}
          <div style={{ paddingLeft: 0 }}>
            <span className="text-[#555a6a]">{bracket[1]}</span>
          </div>
        </>
      )}
    </div>
  );
}

export function FhirViewer({ patientId, patientName, onClose }: FhirViewerProps) {
  const [searchTerm, setSearchTerm] = useState("");
  const [copied, setCopied] = useState(false);
  const [viewMode, setViewMode] = useState<"tree" | "raw">("tree");

  const { data: bundle, isLoading } = useQuery({
    queryKey: ["fhir-raw", patientId],
    queryFn: () => api.getRawFhir(patientId),
  });

  const rawJson = bundle ? JSON.stringify(bundle, null, 2) : "";

  const filteredRaw = searchTerm
    ? rawJson.split("\n").filter((line) => line.toLowerCase().includes(searchTerm.toLowerCase())).join("\n")
    : rawJson;

  const handleCopy = () => {
    navigator.clipboard.writeText(rawJson);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const resourceCount = bundle && Array.isArray((bundle as Record<string, unknown>).entry)
    ? ((bundle as Record<string, unknown>).entry as unknown[]).length
    : 0;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40" onClick={onClose}>
      <div
        className="flex h-[85vh] w-[90vw] max-w-5xl flex-col overflow-hidden rounded-2xl border border-[#e9eaef] bg-white shadow-xl"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="flex shrink-0 items-center justify-between border-b border-[#e9eaef] px-6 py-4">
          <div>
            <h2 className="text-base font-semibold text-[#1c1c1e]">
              Raw FHIR Bundle
            </h2>
            <p className="text-xs text-[#a5a8b5]">
              {patientName} — {resourceCount} resources · FHIR R4 Bundle
            </p>
          </div>
          <button
            onClick={onClose}
            className="flex h-8 w-8 items-center justify-center rounded-lg text-[#a5a8b5] transition-colors hover:bg-[#f5f6f8] hover:text-[#1c1c1e]"
          >
            <X size={18} />
          </button>
        </div>

        {/* Toolbar */}
        <div className="flex shrink-0 items-center gap-3 border-b border-[#e9eaef] px-6 py-2">
          <div className="flex items-center gap-1 rounded-lg border border-[#e9eaef] bg-[#f5f6f8] px-2">
            <Search size={14} className="text-[#a5a8b5]" />
            <input
              type="text"
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              placeholder="Search FHIR data..."
              className="w-48 bg-transparent py-1.5 text-sm text-[#1c1c1e] outline-none placeholder:text-[#a5a8b5]"
            />
          </div>
          <div className="flex gap-1">
            {(["tree", "raw"] as const).map((mode) => (
              <button
                key={mode}
                onClick={() => setViewMode(mode)}
                className={`rounded-full px-3 py-1 text-xs transition-colors ${
                  viewMode === mode ? "bg-[#eef1ff] font-medium text-[#5b76fe]" : "text-[#a5a8b5] hover:text-[#555a6a]"
                }`}
              >
                {mode === "tree" ? "Tree" : "Raw JSON"}
              </button>
            ))}
          </div>
          <button
            onClick={handleCopy}
            className="ml-auto flex items-center gap-1 rounded-lg border border-[#e9eaef] px-3 py-1.5 text-xs text-[#555a6a] transition-colors hover:bg-[#f5f6f8]"
          >
            {copied ? <Check size={12} className="text-[#00b473]" /> : <Copy size={12} />}
            {copied ? "Copied" : "Copy JSON"}
          </button>
        </div>

        {/* Content */}
        <div className="flex-1 overflow-auto bg-[#fafbfc] p-6">
          {isLoading ? (
            <div className="space-y-2">
              {Array.from({ length: 20 }).map((_, i) => (
                <div key={i} className="h-4 animate-pulse rounded bg-[#e9eaef]" style={{ width: `${LOADING_BAR_WIDTHS[i]}%` }} />
              ))}
            </div>
          ) : viewMode === "tree" && bundle ? (
            <div className="font-mono text-xs leading-relaxed">
              <JsonNode value={bundle} />
            </div>
          ) : (
            <pre className="whitespace-pre-wrap font-mono text-xs leading-relaxed text-[#555a6a]">
              {filteredRaw}
            </pre>
          )}
        </div>

        {/* Footer */}
        <div className="shrink-0 border-t border-[#e9eaef] px-6 py-3">
          <p className="text-xs text-[#a5a8b5]">
            This is the raw FHIR R4 Bundle exported from the EHR. The clinical views above are derived from this data.
          </p>
        </div>
      </div>
    </div>
  );
}

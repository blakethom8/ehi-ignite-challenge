import { useSearchParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import axios from "axios";

// ---------------------------------------------------------------------------
// Inline types — will be moved to types/index.ts after merge with BUILD-009
// ---------------------------------------------------------------------------

interface ProcedureItem {
  procedure_id: string;
  display: string;
  status: string;
  performed_start: string | null;
  performed_end: string | null;
  reason_display: string;
  body_site: string;
}

interface ProceduresResponse {
  patient_id: string;
  name: string;
  total_count: number;
  procedures: ProcedureItem[];
}

// ---------------------------------------------------------------------------
// API call
// ---------------------------------------------------------------------------

const fetchProcedures = (patientId: string): Promise<ProceduresResponse> =>
  axios.get(`/api/patients/${patientId}/procedures`).then((r) => r.data);

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

const STATUS_BADGE: Record<
  string,
  { label: string; bg: string; text: string }
> = {
  completed: { label: "Completed", bg: "#d1fae5", text: "#065f46" },
  stopped: { label: "Stopped", bg: "#fef3c7", text: "#92400e" },
  "entered-in-error": { label: "Error", bg: "#fee2e2", text: "#991b1b" },
};

function StatusBadge({ status }: { status: string }) {
  const cfg = STATUS_BADGE[status] ?? {
    label: status,
    bg: "#f3f4f6",
    text: "#374151",
  };
  return (
    <span
      style={{
        backgroundColor: cfg.bg,
        color: cfg.text,
        fontSize: "0.72rem",
        fontWeight: 600,
        padding: "2px 8px",
        borderRadius: 4,
        letterSpacing: "0.02em",
        whiteSpace: "nowrap",
      }}
    >
      {cfg.label}
    </span>
  );
}

function formatDate(iso: string | null): string {
  if (!iso) return "—";
  const d = new Date(iso);
  return d.toLocaleDateString("en-US", {
    year: "numeric",
    month: "short",
    day: "numeric",
  });
}

function procedureYear(p: ProcedureItem): string {
  if (!p.performed_start) return "Unknown";
  return String(new Date(p.performed_start).getFullYear());
}

// Group procedures by year, preserving sort order (already desc from API)
function groupByYear(
  procedures: ProcedureItem[]
): Array<{ year: string; items: ProcedureItem[] }> {
  const map = new Map<string, ProcedureItem[]>();
  for (const p of procedures) {
    const yr = procedureYear(p);
    if (!map.has(yr)) map.set(yr, []);
    map.get(yr)!.push(p);
  }
  return Array.from(map.entries()).map(([year, items]) => ({ year, items }));
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export function ExplorerProcedures() {
  const [searchParams] = useSearchParams();
  const patientId = searchParams.get("patient") ?? undefined;

  const { data, isLoading, isError } = useQuery<ProceduresResponse>({
    queryKey: ["procedures", patientId],
    queryFn: () => fetchProcedures(patientId!),
    enabled: !!patientId,
  });

  // ── No patient selected ──────────────────────────────────────────────────
  if (!patientId) {
    return (
      <div
        style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          height: "60vh",
          color: "#a5a8b5",
          fontSize: "0.95rem",
        }}
      >
        Select a patient to view their procedure history.
      </div>
    );
  }

  // ── Loading ───────────────────────────────────────────────────────────────
  if (isLoading) {
    return (
      <div style={{ padding: "2rem", color: "#555a6a", fontSize: "0.95rem" }}>
        Loading procedures…
      </div>
    );
  }

  // ── Error ─────────────────────────────────────────────────────────────────
  if (isError || !data) {
    return (
      <div style={{ padding: "2rem", color: "#991b1b", fontSize: "0.95rem" }}>
        Failed to load procedures.
      </div>
    );
  }

  const groups = groupByYear(data.procedures);

  return (
    <div style={{ padding: "2rem 2.5rem", maxWidth: 900 }}>
      {/* ── Header ─────────────────────────────────────────────────────── */}
      <div style={{ marginBottom: "1.75rem" }}>
        <h1
          style={{
            fontSize: "1.5rem",
            fontWeight: 700,
            color: "#1c1c1e",
            margin: 0,
          }}
        >
          {data.name} — Procedure History
        </h1>
        <p
          style={{
            margin: "0.35rem 0 0",
            color: "#a5a8b5",
            fontSize: "0.875rem",
          }}
        >
          {data.total_count} procedure{data.total_count !== 1 ? "s" : ""}{" "}
          recorded
        </p>
      </div>

      {/* ── Empty state ─────────────────────────────────────────────────── */}
      {data.total_count === 0 && (
        <div
          style={{
            textAlign: "center",
            color: "#a5a8b5",
            marginTop: "4rem",
            fontSize: "0.95rem",
          }}
        >
          No procedure records found.
        </div>
      )}

      {/* ── Year groups ─────────────────────────────────────────────────── */}
      {groups.map(({ year, items }) => (
        <div key={year} style={{ marginBottom: "2rem" }}>
          {/* Year divider */}
          <div
            style={{
              display: "flex",
              alignItems: "center",
              gap: "0.75rem",
              marginBottom: "0.75rem",
            }}
          >
            <span
              style={{
                fontSize: "0.8rem",
                fontWeight: 700,
                color: "#5b76fe",
                letterSpacing: "0.05em",
                textTransform: "uppercase",
                whiteSpace: "nowrap",
              }}
            >
              {year}
            </span>
            <div
              style={{ flex: 1, height: 1, backgroundColor: "#e9eaef" }}
            />
            <span
              style={{
                fontSize: "0.75rem",
                color: "#a5a8b5",
                whiteSpace: "nowrap",
              }}
            >
              {items.length} procedure{items.length !== 1 ? "s" : ""}
            </span>
          </div>

          {/* Procedure rows */}
          <div
            style={{
              border: "1px solid #e9eaef",
              borderRadius: 8,
              overflow: "hidden",
            }}
          >
            {items.map((proc, idx) => (
              <div
                key={proc.procedure_id}
                style={{
                  display: "grid",
                  gridTemplateColumns: "9rem 1fr",
                  gap: "0.75rem",
                  padding: "0.85rem 1rem",
                  backgroundColor: "#fff",
                  borderBottom:
                    idx < items.length - 1 ? "1px solid #e9eaef" : "none",
                  alignItems: "start",
                }}
              >
                {/* Date column */}
                <div
                  style={{
                    color: "#a5a8b5",
                    fontSize: "0.8rem",
                    paddingTop: "0.1rem",
                    whiteSpace: "nowrap",
                  }}
                >
                  {formatDate(proc.performed_start)}
                </div>

                {/* Content column */}
                <div>
                  <div
                    style={{
                      display: "flex",
                      alignItems: "center",
                      gap: "0.5rem",
                      flexWrap: "wrap",
                    }}
                  >
                    <span
                      style={{
                        fontWeight: 600,
                        fontSize: "0.9rem",
                        color: "#1c1c1e",
                      }}
                    >
                      {proc.display}
                    </span>
                    <StatusBadge status={proc.status} />
                  </div>

                  {proc.reason_display && (
                    <div
                      style={{
                        marginTop: "0.2rem",
                        fontSize: "0.8rem",
                        color: "#555a6a",
                      }}
                    >
                      {proc.reason_display}
                    </div>
                  )}
                </div>
              </div>
            ))}
          </div>
        </div>
      ))}
    </div>
  );
}

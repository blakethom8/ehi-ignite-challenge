import { useState } from "react";

type TimelineEntry = {
  kind: "event" | "trace" | "provenance";
  source: string;
  ts: string;
  user_id: string;
  session_id: string;
  workspace_kind: string;
  event_type: string;
  target_id: string;
  summary: string;
  payload: Record<string, unknown>;
};

type TimelineResponse = {
  user_id: string;
  since: string;
  until: string;
  count: number;
  workspace_kind_filter: string | null;
  timeline: TimelineEntry[];
};

const KIND_BADGE: Record<string, string> = {
  caspian: "bg-blue-100 text-blue-800",
  skill: "bg-purple-100 text-purple-800",
  plugin: "bg-amber-100 text-amber-800",
};

const SOURCE_BADGE: Record<string, string> = {
  "events.db": "bg-emerald-50 text-emerald-700 border-emerald-200",
  "traces.db": "bg-sky-50 text-sky-700 border-sky-200",
  "provenance.db": "bg-rose-50 text-rose-700 border-rose-200",
};

function formatTs(ts: string): string {
  try {
    return new Date(ts).toLocaleString();
  } catch {
    return ts;
  }
}

export function InternalToolsAudit() {
  const [userId, setUserId] = useState("");
  const [token, setToken] = useState("");
  const [hours, setHours] = useState(1);
  const [workspaceKind, setWorkspaceKind] = useState<string>("");
  const [data, setData] = useState<TimelineResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  async function fetchTimeline() {
    setLoading(true);
    setError(null);
    setData(null);
    try {
      const now = new Date();
      const since = new Date(now.getTime() - hours * 3600 * 1000).toISOString();
      const params = new URLSearchParams({ since });
      if (workspaceKind) params.set("workspace_kind", workspaceKind);
      const res = await fetch(
        `/api/audit/users/${encodeURIComponent(userId)}?${params.toString()}`,
        {
          headers: token ? { Authorization: `Bearer ${token}` } : undefined,
        },
      );
      if (!res.ok) {
        const text = await res.text();
        setError(`${res.status} ${res.statusText} — ${text.slice(0, 200)}`);
        return;
      }
      const body = (await res.json()) as TimelineResponse;
      setData(body);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setLoading(false);
    }
  }

  return (
    <main className="mx-auto max-w-6xl px-6 py-8">
      <header className="mb-6">
        <h1 className="text-2xl font-semibold text-[#0f172a]">
          Per-User Audit Timeline
        </h1>
        <p className="mt-1 text-sm text-[#64748b]">
          Joins events, LLM traces, and signed plugin provenance into one
          chronological view per user. Bearer-token gated; required in
          production. Backed by{" "}
          <code className="rounded bg-slate-100 px-1.5 py-0.5 font-mono text-xs">
            GET /api/audit/users/{"{user_id}"}
          </code>
          .
        </p>
      </header>

      <section className="mb-6 grid grid-cols-1 gap-3 rounded-xl border border-slate-200 bg-white p-4 md:grid-cols-5">
        <div>
          <label className="block text-xs font-medium text-[#475569]">
            User ID
          </label>
          <input
            value={userId}
            onChange={(e) => setUserId(e.target.value)}
            placeholder="u_clinician_42"
            className="mt-1 w-full rounded border border-slate-300 px-2 py-1.5 text-sm"
          />
        </div>
        <div>
          <label className="block text-xs font-medium text-[#475569]">
            Audit token
          </label>
          <input
            value={token}
            onChange={(e) => setToken(e.target.value)}
            placeholder="AUDIT_API_TOKEN"
            type="password"
            className="mt-1 w-full rounded border border-slate-300 px-2 py-1.5 text-sm"
          />
        </div>
        <div>
          <label className="block text-xs font-medium text-[#475569]">
            Window (hours)
          </label>
          <input
            type="number"
            min={1}
            max={168}
            value={hours}
            onChange={(e) => setHours(Number(e.target.value) || 1)}
            className="mt-1 w-full rounded border border-slate-300 px-2 py-1.5 text-sm"
          />
        </div>
        <div>
          <label className="block text-xs font-medium text-[#475569]">
            Workspace kind
          </label>
          <select
            value={workspaceKind}
            onChange={(e) => setWorkspaceKind(e.target.value)}
            className="mt-1 w-full rounded border border-slate-300 px-2 py-1.5 text-sm"
          >
            <option value="">all</option>
            <option value="caspian">caspian</option>
            <option value="skill">skill</option>
            <option value="plugin">plugin</option>
          </select>
        </div>
        <div className="flex items-end">
          <button
            type="button"
            onClick={fetchTimeline}
            disabled={!userId || loading}
            className="w-full rounded bg-[#1d4ed8] px-3 py-1.5 text-sm font-medium text-white disabled:opacity-50"
          >
            {loading ? "Loading…" : "Fetch timeline"}
          </button>
        </div>
      </section>

      {error && (
        <div className="mb-4 rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-800">
          {error}
        </div>
      )}

      {data && (
        <section>
          <header className="mb-3 flex items-baseline justify-between">
            <h2 className="text-sm font-semibold text-[#0f172a]">
              {data.count} entr{data.count === 1 ? "y" : "ies"} for{" "}
              <span className="font-mono">{data.user_id}</span>
            </h2>
            <p className="text-xs text-[#64748b]">
              {formatTs(data.since)} → {formatTs(data.until)}
            </p>
          </header>

          {data.timeline.length === 0 ? (
            <p className="rounded border border-dashed border-slate-300 px-4 py-6 text-center text-sm text-[#64748b]">
              No activity in this window.
            </p>
          ) : (
            <ol className="space-y-2">
              {data.timeline.map((entry, idx) => (
                <li
                  key={`${entry.kind}-${idx}-${entry.ts}`}
                  className="rounded-lg border border-slate-200 bg-white px-4 py-3"
                >
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="font-mono text-xs text-[#475569]">
                      {formatTs(entry.ts)}
                    </span>
                    <span
                      className={`rounded px-2 py-0.5 text-xs font-medium ${
                        KIND_BADGE[entry.workspace_kind] ?? "bg-slate-100"
                      }`}
                    >
                      {entry.workspace_kind}
                    </span>
                    <span className="rounded bg-slate-100 px-2 py-0.5 font-mono text-xs">
                      {entry.event_type}
                    </span>
                    <span
                      className={`rounded border px-2 py-0.5 text-[10px] uppercase tracking-wide ${
                        SOURCE_BADGE[entry.source] ??
                        "border-slate-200 bg-slate-50 text-slate-600"
                      }`}
                    >
                      {entry.source}
                    </span>
                    {entry.target_id && (
                      <span className="font-mono text-xs text-[#64748b]">
                        → {entry.target_id}
                      </span>
                    )}
                  </div>
                  {entry.summary && (
                    <p className="mt-1 text-sm text-[#0f172a]">
                      {entry.summary}
                    </p>
                  )}
                  {Object.keys(entry.payload).length > 0 && (
                    <details className="mt-1">
                      <summary className="cursor-pointer text-xs text-[#475569]">
                        payload
                      </summary>
                      <pre className="mt-1 overflow-x-auto rounded bg-slate-50 p-2 text-xs">
                        {JSON.stringify(entry.payload, null, 2)}
                      </pre>
                    </details>
                  )}
                </li>
              ))}
            </ol>
          )}
        </section>
      )}
    </main>
  );
}

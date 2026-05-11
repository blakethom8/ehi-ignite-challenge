import type { RendererProps } from "../types";

type Row = { label: string; status: string; reference?: string };

export function NetworkStatusBoardRenderer({ canvas }: RendererProps) {
  const rows: Row[] = [];

  const referralRoute = canvas["referral.route"] as
    | { referenceId?: string; summary?: string; channel?: string }
    | undefined;
  if (referralRoute) {
    rows.push({
      label: referralRoute.channel ?? "consulting-network",
      status: referralRoute.summary ?? "queued",
      reference: referralRoute.referenceId,
    });
  }

  const referralFetch = canvas["referral.fetch_response"] as
    | { responseSummary?: string; status?: number }
    | undefined;
  if (referralFetch) {
    rows.push({
      label: "specialist response",
      status: referralFetch.responseSummary ?? `HTTP ${referralFetch.status}`,
    });
  }

  const paSubmit = canvas["pa.submit"] as
    | { submissionId?: string; summary?: string; status?: number }
    | undefined;
  if (paSubmit) {
    rows.push({
      label: "payer · PA",
      status: paSubmit.summary ?? `submitted`,
      reference: paSubmit.submissionId,
    });
  }

  const papEnroll = canvas["pap.enroll"] as
    | { enrollmentId?: string; summary?: string; status?: number }
    | undefined;
  if (papEnroll) {
    rows.push({
      label: "manufacturer · PAP",
      status: papEnroll.summary ?? `enrolled`,
      reference: papEnroll.enrollmentId,
    });
  }

  if (rows.length === 0) {
    return (
      <div className="mx-auto max-w-[820px] px-8 py-10 text-[13.5px]" style={{ color: "var(--ink-3)" }}>
        No outbound activity yet. Submissions and acknowledgments appear here as they flow.
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-[820px] px-8 py-7">
      <h2 className="mb-3 text-[16.5px] font-semibold" style={{ color: "var(--ink-1)" }}>
        Network status
      </h2>
      <div className="overflow-hidden rounded-md border" style={{ borderColor: "var(--line-1)" }}>
        <table className="w-full text-left text-[12.5px]">
          <thead>
            <tr style={{ background: "var(--bg-chrome)", color: "var(--ink-3)" }}>
              <th className="px-3 py-2 text-[10px] font-semibold uppercase tracking-wider">Channel</th>
              <th className="px-3 py-2 text-[10px] font-semibold uppercase tracking-wider">Status</th>
              <th className="px-3 py-2 text-[10px] font-semibold uppercase tracking-wider">Reference</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((r, i) => (
              <tr
                key={i}
                style={{
                  background: i % 2 === 0 ? "var(--surface-0)" : "var(--surface-1)",
                  color: "var(--ink-1)",
                }}
              >
                <td className="px-3 py-2 font-medium">{r.label}</td>
                <td className="px-3 py-2" style={{ color: "var(--ink-2)" }}>{r.status}</td>
                <td className="px-3 py-2" style={{ color: "var(--ink-3)", fontFamily: "var(--font-mono)" }}>
                  {r.reference ?? "—"}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

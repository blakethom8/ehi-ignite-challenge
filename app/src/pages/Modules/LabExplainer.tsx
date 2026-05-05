import { useMemo } from "react";
import { useSearchParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import {
  AlertOctagon,
  AlertTriangle,
  CheckCircle,
  FlaskConical,
  Minus,
  TestTubeDiagonal,
  TrendingDown,
  TrendingUp,
} from "lucide-react";
import { api } from "../../api/client";
import { EmptyState } from "../../components/EmptyState";
import type { LabAlertFlag, LabHistoryPoint, LabValue } from "../../types";

type AlertVerdict = "CRITICAL" | "REVIEW" | "STABLE";

function verdictForFlags(flags: LabAlertFlag[]): AlertVerdict {
  if (flags.some((f) => f.severity === "critical")) return "CRITICAL";
  if (flags.length > 0) return "REVIEW";
  return "STABLE";
}

function VerdictHero({
  patientName,
  flags,
}: {
  patientName: string;
  flags: LabAlertFlag[];
}) {
  const verdict = verdictForFlags(flags);
  const criticalCount = flags.filter((f) => f.severity === "critical").length;
  const warningCount = flags.filter((f) => f.severity === "warning").length;

  const config = {
    CRITICAL: {
      bg: "#fef2f2",
      border: "#ef4444",
      text: "#991b1b",
      message: "Critical lab finding — review now",
      Icon: AlertOctagon,
    },
    REVIEW: {
      bg: "#fffbeb",
      border: "#f59e0b",
      text: "#92400e",
      message: "Recent labs need review",
      Icon: AlertTriangle,
    },
    STABLE: {
      bg: "#f0fdf4",
      border: "#22c55e",
      text: "#166534",
      message: "No alert thresholds tripped in the last 30 days",
      Icon: CheckCircle,
    },
  }[verdict];

  return (
    <section
      className="rounded-2xl border p-6"
      style={{ backgroundColor: config.bg, borderColor: config.border }}
    >
      <div className="flex flex-col gap-5 sm:flex-row sm:items-center sm:justify-between">
        <div className="flex items-start gap-4">
          <div
            className="flex h-11 w-11 shrink-0 items-center justify-center rounded-2xl"
            style={{ backgroundColor: "rgba(255,255,255,0.72)", color: config.text }}
          >
            <config.Icon size={22} />
          </div>
          <div>
            <p className="text-sm font-semibold" style={{ color: config.text }}>
              {config.message}
            </p>
            <h2 className="mt-1 text-xl font-semibold text-[#1c1c1e]">{patientName}</h2>
            <p className="mt-1 text-sm" style={{ color: config.text, opacity: 0.78 }}>
              {flags.length === 0
                ? "Reviewed against deterministic alert thresholds and 3-reading trend rules."
                : `${criticalCount} critical · ${warningCount} review · scanned the last 30 days of observations.`}
            </p>
          </div>
        </div>

        <div className="min-w-[180px]">
          <div className="flex items-end justify-between gap-4">
            <div>
              <p className="text-xs font-semibold uppercase tracking-[0.12em] text-[#6b7280]">
                Active flags
              </p>
              <p className="mt-1 text-4xl font-semibold text-[#111827]">
                {flags.length}
              </p>
            </div>
            <FlaskConical size={24} style={{ color: config.text }} />
          </div>
        </div>
      </div>
    </section>
  );
}

function severityChip(severity: "critical" | "warning") {
  if (severity === "critical") {
    return {
      bg: "#fef2f2",
      text: "#991b1b",
      border: "#ef4444",
      label: "CRITICAL",
      Icon: AlertOctagon,
    };
  }
  return {
    bg: "#fffbeb",
    text: "#92400e",
    border: "#f59e0b",
    label: "REVIEW",
    Icon: AlertTriangle,
  };
}

function directionLabel(direction: LabAlertFlag["direction"]): string {
  switch (direction) {
    case "high":
      return "Above normal range";
    case "low":
      return "Below normal range";
    case "trending_up":
      return "Trending upward over last 3 readings";
    case "trending_down":
      return "Trending downward over last 3 readings";
  }
}

function DirectionIcon({ direction }: { direction: LabAlertFlag["direction"] }) {
  if (direction === "trending_up" || direction === "high") {
    return <TrendingUp size={14} />;
  }
  if (direction === "trending_down" || direction === "low") {
    return <TrendingDown size={14} />;
  }
  return <Minus size={14} />;
}

function Sparkline({ history }: { history: LabHistoryPoint[] }) {
  const points = history.filter((p) => p.value !== null).slice(-6);
  if (points.length < 2) return null;

  const values = points.map((p) => p.value as number);
  const min = Math.min(...values);
  const max = Math.max(...values);
  const range = max - min || 1;
  const W = 96;
  const H = 28;

  const path = points
    .map((p, i) => {
      const x = (i / (points.length - 1)) * W;
      const y = H - ((p.value as number - min) / range) * H;
      return `${i === 0 ? "M" : "L"} ${x.toFixed(1)} ${y.toFixed(1)}`;
    })
    .join(" ");

  const last = points[points.length - 1];
  const lastX = W;
  const lastY = H - ((last.value as number - min) / range) * H;

  return (
    <svg width={W} height={H} className="overflow-visible">
      <path d={path} fill="none" stroke="#5b76fe" strokeWidth={1.5} />
      <circle cx={lastX} cy={lastY} r={2.5} fill="#5b76fe" />
    </svg>
  );
}

function FlagCard({
  flag,
  history,
}: {
  flag: LabAlertFlag;
  history: LabHistoryPoint[];
}) {
  const chip = severityChip(flag.severity);
  return (
    <article
      className="rounded-2xl border border-[#e9eaef] bg-white p-5 shadow-sm"
      style={{ borderLeftWidth: 4, borderLeftColor: chip.border }}
    >
      <div className="flex items-start justify-between gap-4">
        <div>
          <h3 className="text-base font-semibold text-[#1c1c1e]">{flag.lab_name}</h3>
          <p className="mt-1 text-xs font-mono text-[#8d92a3]">LOINC {flag.loinc_code}</p>
        </div>
        <span
          className="inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-xs font-semibold"
          style={{ backgroundColor: chip.bg, color: chip.text, borderColor: chip.border }}
        >
          <chip.Icon size={12} />
          {chip.label}
        </span>
      </div>

      <div className="mt-4 flex items-end justify-between gap-4">
        <div>
          <p className="text-3xl font-semibold text-[#111827]">
            {flag.value}
            <span className="ml-1 text-base font-medium text-[#6b7280]">{flag.unit}</span>
          </p>
          <p
            className="mt-1 inline-flex items-center gap-1 text-xs font-semibold"
            style={{ color: chip.text }}
          >
            <DirectionIcon direction={flag.direction} />
            {directionLabel(flag.direction)}
          </p>
          <p className="mt-1 text-xs text-[#6b7280]">
            Drawn {flag.days_ago === 0 ? "today" : `${flag.days_ago}d ago`}
          </p>
        </div>
        <Sparkline history={history} />
      </div>

      <p className="mt-4 rounded-lg bg-[#f7f8fc] px-3 py-2 text-sm leading-6 text-[#1f2937]">
        {flag.message}
      </p>
    </article>
  );
}

function MonitoredPanelRow({ panel, labs }: { panel: string; labs: LabValue[] }) {
  return (
    <div className="border-b border-[#eef0f4] py-3 last:border-0">
      <div className="flex items-center justify-between gap-4">
        <p className="text-sm font-semibold text-[#1c1c1e]">{panel}</p>
        <p className="text-xs text-[#6b7280]">{labs.length} tracked</p>
      </div>
      <div className="mt-2 flex flex-wrap gap-1.5">
        {labs.map((lab) => {
          const trendChip =
            lab.trend === "up"
              ? { bg: "#fffbeb", text: "#92400e", Icon: TrendingUp }
              : lab.trend === "down"
                ? { bg: "#eff6ff", text: "#1e40af", Icon: TrendingDown }
                : { bg: "#f3f4f6", text: "#374151", Icon: Minus };
          return (
            <span
              key={lab.loinc_code}
              className="inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-xs font-semibold"
              style={{ backgroundColor: trendChip.bg, color: trendChip.text }}
            >
              <trendChip.Icon size={11} />
              {lab.display}
              {lab.value !== null && (
                <span className="font-normal opacity-70">
                  {lab.value}
                  {lab.unit ? ` ${lab.unit}` : ""}
                </span>
              )}
            </span>
          );
        })}
      </div>
    </div>
  );
}

export function LabExplainer() {
  const [searchParams] = useSearchParams();
  const patientId = searchParams.get("patient");

  const labsQ = useQuery({
    queryKey: ["keyLabs", patientId],
    queryFn: () => api.getKeyLabs(patientId!),
    enabled: !!patientId,
  });
  const overviewQ = useQuery({
    queryKey: ["overview", patientId],
    queryFn: () => api.getOverview(patientId!),
    enabled: !!patientId,
  });

  const historyByLoinc = useMemo(() => {
    if (!labsQ.data) return new Map<string, LabHistoryPoint[]>();
    const map = new Map<string, LabHistoryPoint[]>();
    Object.values(labsQ.data.panels).forEach((panel) => {
      panel.forEach((lab) => map.set(lab.loinc_code, lab.history));
    });
    return map;
  }, [labsQ.data]);

  if (!patientId) {
    return (
      <EmptyState
        icon={TestTubeDiagonal}
        title="No patient selected"
        bullets={[
          "Select a patient from the top bar",
          "Lab Explainer surfaces critical and trending alert thresholds across CBC, BMP, coagulation, and cardiac panels",
          "Each flag links to the most recent value, recent trend, and a plain-language read",
        ]}
      />
    );
  }

  if (labsQ.isLoading || overviewQ.isLoading) {
    return (
      <div className="mx-auto max-w-5xl space-y-4 p-8">
        <div className="h-40 animate-pulse rounded-2xl bg-[#e9eaef]" />
        <div className="grid gap-4 md:grid-cols-2">
          <div className="h-48 animate-pulse rounded-2xl bg-[#e9eaef]" />
          <div className="h-48 animate-pulse rounded-2xl bg-[#e9eaef]" />
        </div>
      </div>
    );
  }

  if (labsQ.isError || !labsQ.data || overviewQ.isError || !overviewQ.data) {
    return (
      <div className="p-8">
        <p className="text-sm text-[#991b1b]">Failed to load lab explainer data.</p>
      </div>
    );
  }

  const { alert_flags } = labsQ.data;
  const panels = labsQ.data.panels;
  const overview = overviewQ.data;
  const criticalFlags = alert_flags.filter((f) => f.severity === "critical");
  const warningFlags = alert_flags.filter((f) => f.severity === "warning");

  return (
    <div className="mx-auto max-w-5xl space-y-5 p-6 lg:p-8">
      <div>
        <p className="inline-flex items-center gap-2 rounded-full bg-[#eef1ff] px-3 py-1 text-xs font-semibold uppercase tracking-wider text-[#5b76fe]">
          <TestTubeDiagonal size={13} />
          Clinical Insight Module
        </p>
        <h1 className="mt-3 text-2xl font-semibold tracking-tight text-[#1c1c1e]">
          Lab Result Explainer
        </h1>
        <p className="mt-2 max-w-2xl text-sm leading-6 text-[#667085]">
          Recent abnormal results, trending values, and the deterministic thresholds that flagged them.
        </p>
      </div>

      <VerdictHero patientName={overview.name} flags={alert_flags} />

      {criticalFlags.length > 0 && (
        <section>
          <h2 className="text-base font-semibold text-[#1c1c1e]">Critical findings</h2>
          <p className="mt-1 text-sm text-[#667085]">
            Outside hard alert thresholds — clinically significant in the absence of mitigating context.
          </p>
          <div className="mt-3 grid gap-4 md:grid-cols-2">
            {criticalFlags.map((flag) => (
              <FlagCard
                key={`${flag.loinc_code}-${flag.days_ago}`}
                flag={flag}
                history={historyByLoinc.get(flag.loinc_code) ?? []}
              />
            ))}
          </div>
        </section>
      )}

      {warningFlags.length > 0 && (
        <section>
          <h2 className="text-base font-semibold text-[#1c1c1e]">Review-level findings</h2>
          <p className="mt-1 text-sm text-[#667085]">
            Outside warning bands or trending consistently across the last 3 readings.
          </p>
          <div className="mt-3 grid gap-4 md:grid-cols-2">
            {warningFlags.map((flag) => (
              <FlagCard
                key={`${flag.loinc_code}-${flag.days_ago}`}
                flag={flag}
                history={historyByLoinc.get(flag.loinc_code) ?? []}
              />
            ))}
          </div>
        </section>
      )}

      {alert_flags.length === 0 && (
        <section className="rounded-2xl border border-[#dfe4ea] bg-white p-6 text-center">
          <CheckCircle size={28} className="mx-auto text-[#22c55e]" />
          <h2 className="mt-3 text-base font-semibold text-[#1c1c1e]">
            No alert thresholds tripped in the last 30 days
          </h2>
          <p className="mt-2 text-sm text-[#6b7280]">
            Tracked panels are listed below. Older readings are not scored here — open History for the full record.
          </p>
        </section>
      )}

      <section className="rounded-2xl border border-[#dfe4ea] bg-white p-5">
        <div className="flex items-start justify-between gap-3">
          <div>
            <h2 className="text-base font-semibold text-[#1c1c1e]">Tracked panels</h2>
            <p className="mt-1 text-sm text-[#667085]">
              Most-recent values and trends across the panels Lab Explainer monitors. A trend chip means a 3-reading
              direction; the full history is in the patient timeline.
            </p>
          </div>
        </div>
        <div className="mt-4">
          {Object.entries(panels).map(([panel, labs]) => (
            <MonitoredPanelRow key={panel} panel={panel} labs={labs} />
          ))}
        </div>
      </section>

      <section className="rounded-2xl border border-[#d8f3ec] bg-[#f3fffb] p-5">
        <h2 className="text-base font-semibold text-[#087d75]">Methodology</h2>
        <p className="mt-1 text-sm text-[#3f635f]">
          Deterministic alert engine over Synthea R4 observations.
        </p>
        <ul className="mt-3 grid gap-2 md:grid-cols-2">
          {[
            "Hard thresholds for critical low/high — bypass any trend rule.",
            "Warning bands flag values outside the normal reference but inside the critical range.",
            "Trending up/down requires three consecutive readings each shifting >5%.",
            "Only observations with a quantity value and an effective date in the last 30 days are scored.",
          ].map((note) => (
            <li key={note} className="flex items-start gap-2 text-sm leading-6 text-[#1f4f4b]">
              <span className="mt-2 h-1.5 w-1.5 shrink-0 rounded-full bg-[#087d75]" />
              <span>{note}</span>
            </li>
          ))}
        </ul>
      </section>
    </div>
  );
}

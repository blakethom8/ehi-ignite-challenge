import { Database, Lock, Pin, UserRound } from "lucide-react";

export type PatientIdentity = {
  name: string;
  mrn: string;
  ageSex: string;
  tier?: string;
  fhirCount?: string;
  encounters?: number;
};

export type PatientHeaderProps = {
  patient: PatientIdentity;
  pinned?: boolean;
  boundary?: string;
};

/**
 * Reusable patient identity strip — the same chrome used by the Caspian
 * context strip, but available as a standalone primitive for any page that
 * needs to show "you are looking at this patient".
 */
export function PatientHeader({
  patient,
  pinned = true,
  boundary = "Private patient boundary",
}: PatientHeaderProps) {
  return (
    <div
      className="flex h-10 items-center gap-2 overflow-hidden whitespace-nowrap border-b px-3.5 text-[12px]"
      style={{
        background: "var(--bg-chrome)",
        color: "var(--ink-2)",
        borderColor: "var(--line-1)",
      }}
    >
      <div
        className="grid h-[22px] w-[22px] place-items-center rounded-md"
        style={{ background: "var(--action-tint)", color: "var(--action)" }}
      >
        <UserRound className="h-3.5 w-3.5" strokeWidth={1.5} />
      </div>
      <div className="text-[13px] font-semibold tracking-tight" style={{ color: "var(--ink-1)" }}>
        {patient.name}
      </div>
      <Sep />
      <Mono>{patient.mrn}</Mono>
      <Sep />
      <Meta>{patient.ageSex}</Meta>
      {patient.tier && (
        <>
          <Sep />
          <span
            className="inline-flex items-center gap-1.5 font-medium"
            style={{ color: "var(--ink-2)" }}
          >
            <span className="h-1.5 w-1.5 rounded-full" style={{ background: "#b45309" }} />
            {patient.tier}
          </span>
        </>
      )}
      {patient.fhirCount && (
        <>
          <Sep />
          <Meta>
            <Database className="h-2.5 w-2.5" strokeWidth={1.5} />
            {patient.fhirCount}
          </Meta>
        </>
      )}
      {patient.encounters != null && (
        <>
          <Sep />
          <Meta>{patient.encounters} encounters</Meta>
        </>
      )}
      <div className="flex-1" />
      {pinned && (
        <Pill>
          <Pin className="h-2.5 w-2.5" strokeWidth={1.5} />
          Pinned to session
        </Pill>
      )}
      <Pill tone="green">
        <Lock className="h-2.5 w-2.5" strokeWidth={1.5} />
        {boundary}
      </Pill>
    </div>
  );
}

function Sep() {
  return <span style={{ color: "var(--ink-4)" }}>·</span>;
}

function Mono({ children }: { children: React.ReactNode }) {
  return (
    <span
      className="text-[11px]"
      style={{ fontFamily: "var(--font-mono)", color: "var(--ink-3)" }}
    >
      {children}
    </span>
  );
}

function Meta({ children }: { children: React.ReactNode }) {
  return (
    <span
      className="inline-flex items-center gap-1 text-[12px]"
      style={{ color: "var(--ink-3)" }}
    >
      {children}
    </span>
  );
}

function Pill({
  children,
  tone,
}: {
  children: React.ReactNode;
  tone?: "green" | "warn";
}) {
  let style: React.CSSProperties = {
    background: "var(--surface-2)",
    color: "var(--ink-2)",
    borderColor: "var(--line-1)",
  };
  if (tone === "green") {
    style = {
      background: "rgba(4,120,87,0.08)",
      color: "var(--clear)",
      borderColor: "rgba(4,120,87,0.18)",
    };
  } else if (tone === "warn") {
    style = {
      background: "rgba(180,83,9,0.08)",
      color: "#b45309",
      borderColor: "rgba(180,83,9,0.22)",
    };
  }
  return (
    <span
      className="inline-flex items-center gap-1.5 rounded-full border px-2 py-0.5 text-[11px] font-medium"
      style={style}
    >
      {children}
    </span>
  );
}

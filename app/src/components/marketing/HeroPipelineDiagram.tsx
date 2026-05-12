import {
  ArrowDown,
  Boxes,
  Database,
  FileJson,
  FileText,
  Files,
  GitMerge,
  Package,
  ShieldCheck,
  type LucideIcon,
} from "lucide-react";

type FlowCardConfig = {
  label: string;
  detail: string;
  icon: LucideIcon;
};

type FlowPathConfig = {
  id: string;
  d: string;
  duration: string;
  delay: string;
  tone: string;
};

const sourceCards: FlowCardConfig[] = [
  { label: "FHIR bundle", detail: "Structured clinical export", icon: FileJson },
  { label: "C-CDA", detail: "Standards-based document", icon: FileText },
  { label: "PDF", detail: "Scanned and portal records", icon: Files },
  { label: "Portal export", detail: "Downloaded patient data", icon: Files },
];

const outputCards: FlowCardConfig[] = [
  { label: "FHIR Charts", detail: "Chart views", icon: Database },
  { label: "Caspian", detail: "Guided review", icon: ShieldCheck },
  { label: "Plugins", detail: "Scoped tools", icon: Boxes },
  { label: "Export package", detail: "Portable bundle", icon: Package },
];

const inboundPaths: FlowPathConfig[] = [
  {
    id: "source-fhir",
    d: "M150 118 C150 166 286 156 600 156",
    duration: "7.6s",
    delay: "0s",
    tone: "#4d68ff",
  },
  {
    id: "source-ccda",
    d: "M450 118 C450 152 506 156 600 156",
    duration: "6.4s",
    delay: "-1.8s",
    tone: "#6f7dff",
  },
  {
    id: "source-pdf",
    d: "M750 118 C750 152 694 156 600 156",
    duration: "6.8s",
    delay: "-0.9s",
    tone: "#4d68ff",
  },
  {
    id: "source-portal",
    d: "M1050 118 C1050 166 914 156 600 156",
    duration: "7.9s",
    delay: "-2.6s",
    tone: "#6f7dff",
  },
];

const outboundPaths: FlowPathConfig[] = [
  {
    id: "output-charts",
    d: "M600 366 C520 370 260 372 150 410",
    duration: "7.1s",
    delay: "-0.6s",
    tone: "#3f7cff",
  },
  {
    id: "output-caspian",
    d: "M600 366 C560 372 500 382 450 410",
    duration: "6.2s",
    delay: "-2.1s",
    tone: "#3ecf8e",
  },
  {
    id: "output-plugins",
    d: "M600 366 C640 372 700 382 750 410",
    duration: "6.6s",
    delay: "-1.2s",
    tone: "#8a6dff",
  },
  {
    id: "output-export",
    d: "M600 366 C680 370 940 372 1050 410",
    duration: "7.4s",
    delay: "-3.1s",
    tone: "#57b7ff",
  },
];

function FlowCard({
  icon: Icon,
  label,
  detail,
}: {
  icon: LucideIcon;
  label: string;
  detail: string;
}) {
  return (
    <div className="w-full rounded-[20px] border border-[rgba(77,104,255,0.10)] bg-white/80 p-4 text-center shadow-[0_10px_28px_rgba(32,52,89,0.05)] lg:min-h-[124px]">
      <div className="mx-auto flex h-10 w-10 items-center justify-center rounded-[14px] bg-[#eef2ff] text-[#4d68ff]">
        <Icon size={18} />
      </div>
      <p className="mt-3 text-sm font-semibold text-[#1d2433]">{label}</p>
      <p className="mt-1 text-xs leading-5 text-[#70809a]">{detail}</p>
    </div>
  );
}

function FlowPacket({
  d,
  tone,
  duration,
  delay,
}: {
  d: string;
  tone: string;
  duration: string;
  delay: string;
}) {
  return (
    <g className="motion-reduce:hidden">
      <circle fill="url(#atlas-flow-pulse)" r="11">
        <animateMotion begin={delay} dur={duration} path={d} repeatCount="indefinite" />
      </circle>
      <circle fill={tone} r="4.5">
        <animateMotion begin={delay} dur={duration} path={d} repeatCount="indefinite" />
      </circle>
      <circle fill="rgba(255,255,255,0.92)" r="1.8">
        <animateMotion begin={delay} dur={duration} path={d} repeatCount="indefinite" />
      </circle>
    </g>
  );
}

function DesktopSignalLayer() {
  const flowPaths = [...inboundPaths, ...outboundPaths];

  return (
    <svg
      aria-hidden="true"
      className="pointer-events-none absolute inset-0 h-full w-full"
      preserveAspectRatio="none"
      viewBox="0 0 1200 520"
    >
      <defs>
        <linearGradient id="atlas-flow-line" x1="0%" x2="100%" y1="0%" y2="0%">
          <stop offset="0%" stopColor="rgba(120,138,186,0.06)" />
          <stop offset="18%" stopColor="rgba(99,122,184,0.22)" />
          <stop offset="50%" stopColor="rgba(77,104,255,0.32)" />
          <stop offset="82%" stopColor="rgba(99,122,184,0.22)" />
          <stop offset="100%" stopColor="rgba(120,138,186,0.06)" />
        </linearGradient>
        <radialGradient id="atlas-flow-pulse" cx="50%" cy="50%" r="50%">
          <stop offset="0%" stopColor="rgba(77,104,255,0.30)" />
          <stop offset="100%" stopColor="rgba(77,104,255,0)" />
        </radialGradient>
      </defs>

      {flowPaths.map((flow) => (
        <g key={flow.id}>
          <path
            d={flow.d}
            fill="none"
            opacity="0.95"
            stroke="url(#atlas-flow-line)"
            strokeLinecap="round"
            strokeWidth="2.4"
          />
          <path
            d={flow.d}
            fill="none"
            opacity="0.32"
            stroke={flow.tone}
            strokeDasharray="3 13"
            strokeLinecap="round"
            strokeWidth="1.3"
          >
            <animate
              attributeName="stroke-dashoffset"
              dur={flow.duration}
              from="0"
              repeatCount="indefinite"
              to="-180"
            />
          </path>
          <FlowPacket d={flow.d} delay={flow.delay} duration={flow.duration} tone={flow.tone} />
        </g>
      ))}

      <g opacity="0.95">
        <circle cx="600" cy="156" fill="#ffffff" r="8.5" stroke="rgba(77,104,255,0.28)" strokeWidth="2" />
        <circle className="motion-reduce:hidden" cx="600" cy="156" fill="rgba(77,104,255,0.14)" r="13">
          <animate attributeName="r" dur="3.6s" repeatCount="indefinite" values="13;18;13" />
          <animate attributeName="opacity" dur="3.6s" repeatCount="indefinite" values="0.45;0.10;0.45" />
        </circle>

        <circle cx="600" cy="366" fill="#ffffff" r="8.5" stroke="rgba(77,104,255,0.22)" strokeWidth="2" />
        <circle className="motion-reduce:hidden" cx="600" cy="366" fill="rgba(77,104,255,0.12)" r="13">
          <animate attributeName="r" dur="4.1s" repeatCount="indefinite" values="13;18;13" />
          <animate attributeName="opacity" dur="4.1s" repeatCount="indefinite" values="0.4;0.08;0.4" />
        </circle>
      </g>
    </svg>
  );
}

function HarmonizeCard({ compact = false }: { compact?: boolean }) {
  return (
    <div
      className={`rounded-[30px] border border-[#cad6ff] bg-[linear-gradient(180deg,#f3f6ff,#ffffff)] p-5 shadow-[0_18px_50px_rgba(77,104,255,0.12)] ${compact ? "" : "relative lg:min-h-[220px]"}`}
    >
      {!compact ? (
        <>
          <div className="pointer-events-none absolute left-1/2 top-0 h-3.5 w-3.5 -translate-x-1/2 -translate-y-1/2 rounded-full border border-[rgba(77,104,255,0.24)] bg-white shadow-[0_0_0_6px_rgba(77,104,255,0.07)]" />
          <div className="pointer-events-none absolute left-1/2 bottom-0 h-3.5 w-3.5 -translate-x-1/2 translate-y-1/2 rounded-full border border-[rgba(77,104,255,0.20)] bg-white shadow-[0_0_0_6px_rgba(77,104,255,0.05)]" />
        </>
      ) : null}

      <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-[16px] bg-[#4d68ff] text-white shadow-[0_12px_24px_rgba(77,104,255,0.28)]">
        <GitMerge size={22} />
      </div>
      <p className="mt-4 text-center text-lg font-semibold text-[#18202b]">
        Harmonize + prepare
      </p>
      <p className="mt-2 text-center text-sm leading-6 text-[#5a6a84]">
        Normalize formats, merge provenance, and produce a patient record optimized for
        LLM-powered review.
      </p>
      <div className="mt-4 flex flex-wrap justify-center gap-2">
        <span className="rounded-full bg-[#eef2ff] px-3 py-1 text-[11px] font-semibold uppercase tracking-[0.14em] text-[#4d68ff]">
          Canonical facts
        </span>
        <span className="rounded-full bg-[#eef8f3] px-3 py-1 text-[11px] font-semibold uppercase tracking-[0.14em] text-[#2f7a59]">
          Portable bundle
        </span>
      </div>
    </div>
  );
}

export function HeroPipelineDiagram() {
  return (
    <div className="relative overflow-hidden rounded-[34px] bg-[radial-gradient(circle_at_top,rgba(77,104,255,0.12),rgba(77,104,255,0)_34%),linear-gradient(180deg,rgba(255,255,255,0.72),rgba(245,248,255,0.52))] p-4 shadow-[0_28px_90px_rgba(77,104,255,0.08)]">
      <div className="absolute inset-x-12 top-0 h-20 bg-[radial-gradient(circle,rgba(77,104,255,0.10),rgba(77,104,255,0))]" />
      <div className="absolute right-0 top-12 h-36 w-36 rounded-full bg-[radial-gradient(circle,rgba(101,198,255,0.10),rgba(101,198,255,0))]" />

      <div className="relative">
        <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-[#4d68ff]">
          Atlas data flow
        </p>

        <div className="mt-4 hidden lg:block">
          <div className="space-y-5">
            <div className="relative">
              <DesktopSignalLayer />

              <div className="relative z-10 space-y-5">
                <div className="grid gap-4 lg:grid-cols-4">
                  {sourceCards.map((item) => (
                    <FlowCard
                      key={item.label}
                      detail={item.detail}
                      icon={item.icon}
                      label={item.label}
                    />
                  ))}
                </div>

                <div className="mx-auto max-w-[560px]">
                  <HarmonizeCard />
                </div>

                <div className="grid gap-4 lg:grid-cols-4">
                  {outputCards.map((item) => (
                    <FlowCard
                      key={item.label}
                      detail={item.detail}
                      icon={item.icon}
                      label={item.label}
                    />
                  ))}
                </div>
              </div>
            </div>
          </div>
        </div>

        <div className="mt-4 flex flex-col items-center lg:hidden">
          <div className="grid w-full gap-3 sm:grid-cols-2">
            {sourceCards.map((item) => (
              <FlowCard
                key={item.label}
                detail={item.detail}
                icon={item.icon}
                label={item.label}
              />
            ))}
          </div>

          <div className="mt-4 flex h-10 w-10 items-center justify-center rounded-full border border-[rgba(77,104,255,0.12)] bg-white/80 text-[#8fa0bc]">
            <ArrowDown size={18} />
          </div>

          <div className="w-full max-w-[560px]">
            <HarmonizeCard compact />
          </div>

          <div className="mt-4 flex h-10 w-10 items-center justify-center rounded-full border border-[rgba(77,104,255,0.12)] bg-white/80 text-[#8fa0bc]">
            <ArrowDown size={18} />
          </div>

          <div className="mt-4 grid w-full gap-3 sm:grid-cols-2">
            {outputCards.map((item) => (
              <FlowCard
                key={item.label}
                detail={item.detail}
                icon={item.icon}
                label={item.label}
              />
            ))}
          </div>
        </div>

        <div className="mt-5 rounded-[20px] bg-white/66 px-4 py-3 text-center shadow-[0_10px_28px_rgba(32,52,89,0.04)]">
          <p className="text-sm font-semibold text-[#1d2433]">
            One patient record. Multiple downstream environments.
          </p>
          <p className="mx-auto mt-1 max-w-3xl text-sm leading-6 text-[#62728d]">
            The patient record becomes the shared layer for chart review, guided workflows,
            plugins, and portable export.
          </p>
        </div>
      </div>
    </div>
  );
}

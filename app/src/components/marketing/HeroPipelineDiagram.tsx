import { ArrowDown, Boxes, Database, FileJson, FileText, Files, GitMerge, Package, ShieldCheck } from "lucide-react";

const sourceCards = [
  { label: "FHIR bundle", detail: "Structured clinical export", icon: FileJson },
  { label: "C-CDA", detail: "Standards-based document", icon: FileText },
  { label: "PDF", detail: "Scanned and portal records", icon: Files },
  { label: "Portal export", detail: "Downloaded patient data", icon: Files },
];

const outputCards = [
  { label: "FHIR Charts", detail: "Chart views", icon: Database },
  { label: "Caspian", detail: "Guided review", icon: ShieldCheck },
  { label: "Plugins", detail: "Scoped tools", icon: Boxes },
  { label: "Export package", detail: "Portable bundle", icon: Package },
];

function FlowCard({
  icon: Icon,
  label,
  detail,
}: {
  icon: typeof FileJson;
  label: string;
  detail: string;
}) {
  return (
    <div className="w-full rounded-[20px] border border-[rgba(77,104,255,0.10)] bg-white/80 p-4 text-center shadow-[0_10px_28px_rgba(32,52,89,0.05)]">
      <div className="mx-auto flex h-10 w-10 items-center justify-center rounded-[14px] bg-[#eef2ff] text-[#4d68ff]">
        <Icon size={18} />
      </div>
      <p className="mt-3 text-sm font-semibold text-[#1d2433]">{label}</p>
      <p className="mt-1 text-xs leading-5 text-[#70809a]">{detail}</p>
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
            <div className="grid gap-4 lg:grid-cols-4">
              {sourceCards.map((item) => (
                <FlowCard
                  key={item.label}
                  icon={item.icon}
                  label={item.label}
                  detail={item.detail}
                />
              ))}
            </div>

            <div className="mx-auto max-w-[560px]">
              <div className="rounded-[30px] border border-[#cad6ff] bg-[linear-gradient(180deg,#f3f6ff,#ffffff)] p-5 shadow-[0_18px_50px_rgba(77,104,255,0.12)]">
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
            </div>

            <div className="grid gap-4 lg:grid-cols-4">
              {outputCards.map((item) => (
                <FlowCard
                  key={item.label}
                  icon={item.icon}
                  label={item.label}
                  detail={item.detail}
                />
              ))}
            </div>
          </div>
        </div>

        <div className="mt-4 flex flex-col items-center lg:hidden">
          <div className="grid w-full gap-3 sm:grid-cols-2">
            {sourceCards.map((item) => (
              <FlowCard
                key={item.label}
                icon={item.icon}
                label={item.label}
                detail={item.detail}
              />
            ))}
          </div>

          <div className="mt-4 flex h-10 w-10 items-center justify-center rounded-full border border-[rgba(77,104,255,0.12)] bg-white/80 text-[#8fa0bc]">
            <ArrowDown size={18} />
          </div>

          <div className="w-full max-w-[560px] rounded-[30px] border border-[#cad6ff] bg-[linear-gradient(180deg,#f3f6ff,#ffffff)] p-5 shadow-[0_18px_50px_rgba(77,104,255,0.12)]">
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

          <div className="mt-4 flex h-10 w-10 items-center justify-center rounded-full border border-[rgba(77,104,255,0.12)] bg-white/80 text-[#8fa0bc]">
            <ArrowDown size={18} />
          </div>

          <div className="mt-4 grid w-full gap-3 sm:grid-cols-2">
            {outputCards.map((item) => (
              <FlowCard
                key={item.label}
                icon={item.icon}
                label={item.label}
                detail={item.detail}
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

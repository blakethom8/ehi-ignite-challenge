import { UserRound } from "lucide-react";
import type { RendererProps } from "../types";

type Specialist = {
  id: string;
  name: string;
  institution: string;
  specialty: string;
  available: boolean;
  responseSlaDays: number;
};

export function SpecialtyPickerRenderer({ canvas }: RendererProps) {
  const fetched = canvas["referral.fetch_specialists"] as
    | { specialists?: Specialist[] }
    | undefined;
  // Fall back to fixture-shaped storage from referral.fetch_response if specialists weren't fetched yet.
  const specialists = fetched?.specialists ?? [];
  if (specialists.length === 0) {
    return (
      <div className="mx-auto max-w-[820px] px-8 py-10 text-[13.5px]" style={{ color: "var(--ink-3)" }}>
        No specialists loaded yet. Browse the ConferMD network to populate.
      </div>
    );
  }
  return (
    <div className="mx-auto max-w-[820px] px-8 py-7">
      <h2 className="mb-3 text-[16.5px] font-semibold" style={{ color: "var(--ink-1)" }}>
        Pick a specialist
      </h2>
      <div className="grid grid-cols-1 gap-2">
        {specialists.map((s) => (
          <div
            key={s.id}
            className="flex items-center gap-3 rounded-md border p-3"
            style={{ background: "var(--surface-1)", borderColor: "var(--line-1)" }}
          >
            <UserRound className="h-4 w-4" strokeWidth={1.5} />
            <div className="flex-1">
              <div className="text-[13.5px] font-semibold" style={{ color: "var(--ink-1)" }}>
                {s.name} · {s.institution}
              </div>
              <div className="text-[12px]" style={{ color: "var(--ink-3)" }}>
                {s.specialty} · SLA {s.responseSlaDays}d
              </div>
            </div>
            <span
              className="rounded px-1.5 py-0.5 text-[11px]"
              style={{
                background: s.available ? "var(--ok-tint, rgba(34,197,94,0.1))" : "rgba(0,0,0,0.05)",
                color: s.available ? "var(--ok)" : "var(--ink-3)",
              }}
            >
              {s.available ? "available" : "unavailable"}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}

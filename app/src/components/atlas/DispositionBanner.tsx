import { AlertOctagon, AlertTriangle, CheckCircle2, Info, type LucideIcon } from "lucide-react";

export type DispositionState = "HOLD" | "REVIEW" | "CLEAR" | "CRITICAL";

export type DispositionBannerProps = {
  state: DispositionState;
  message: string;
  action?: { label: string; onClick: () => void };
  flag?: string;
};

const ICON: Record<DispositionState, LucideIcon> = {
  HOLD: AlertTriangle,
  REVIEW: AlertTriangle,
  CRITICAL: AlertOctagon,
  CLEAR: CheckCircle2,
};

const TONE: Record<DispositionState, { bg: string; line: string; ink: string }> = {
  HOLD: { bg: "var(--caution-tint)", line: "var(--caution-line)", ink: "var(--caution)" },
  REVIEW: { bg: "var(--caution-tint)", line: "var(--caution-line)", ink: "var(--caution)" },
  CRITICAL: { bg: "var(--critical-tint)", line: "var(--critical-line)", ink: "var(--critical)" },
  CLEAR: { bg: "var(--clear-tint)", line: "var(--clear-line)", ink: "var(--clear)" },
};

/**
 * The signature banner at the top of a Caspian briefing. 36-1fr-auto grid:
 * icon · flag + one-line rationale · action button. 4px left bar.
 */
export function DispositionBanner({ state, message, action, flag }: DispositionBannerProps) {
  const Icon = ICON[state] ?? Info;
  const tone = TONE[state];
  return (
    <div
      className="relative mb-6 grid grid-cols-[36px_1fr_auto] items-center gap-3 overflow-hidden rounded-[10px] border p-4"
      style={{ background: tone.bg, borderColor: tone.line }}
    >
      <span
        className="absolute left-0 top-0 h-full w-1"
        style={{ background: tone.ink }}
      />
      <Icon className="h-5 w-5" strokeWidth={1.5} style={{ color: tone.ink }} />
      <div>
        <span
          className="block text-[11px] font-bold tracking-wider"
          style={{ color: tone.ink }}
        >
          {flag ?? state}
        </span>
        <div
          className="mt-0.5 text-[13.5px] font-medium"
          style={{ color: "var(--ink-1)" }}
        >
          {message}
        </div>
      </div>
      {action && (
        <button
          onClick={action.onClick}
          className="h-[28px] rounded-md px-3 text-[12px] font-semibold text-white"
          style={{ background: "var(--ink-1)" }}
        >
          {action.label}
        </button>
      )}
    </div>
  );
}

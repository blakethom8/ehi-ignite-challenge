import type { LucideIcon } from "lucide-react";
import { ArrowRight } from "lucide-react";
import type { ReactNode } from "react";

type StartStateCardProps = {
  icon: LucideIcon;
  eyebrow: string;
  title: string;
  body: string;
  bullets?: string[];
  actions?: Array<{
    label: string;
    onClick?: () => void;
    href?: string;
    tone?: "primary" | "secondary";
  }>;
  aside?: ReactNode;
};

export function StartStateCard({
  icon: Icon,
  eyebrow,
  title,
  body,
  bullets = [],
  actions = [],
  aside,
}: StartStateCardProps) {
  return (
    <div className="mx-auto flex w-full max-w-6xl flex-1 items-center px-6 py-8 lg:px-10">
      <div className="grid w-full gap-5 rounded-[28px] border border-[#dfe4ea] bg-white p-6 shadow-[0_16px_40px_rgba(32,52,89,0.06)] lg:grid-cols-[1.1fr_0.9fr] lg:p-8">
        <div>
          <div className="inline-flex items-center gap-2 rounded-full bg-[#eef2ff] px-3 py-1 text-[11px] font-semibold uppercase tracking-[0.18em] text-[#4d68ff]">
            <Icon size={14} />
            {eyebrow}
          </div>
          <h1 className="mt-4 text-3xl font-semibold tracking-[-0.04em] text-[#171b24] lg:text-4xl">
            {title}
          </h1>
          <p className="mt-3 max-w-3xl text-sm leading-7 text-[#5f6f89] lg:text-base">
            {body}
          </p>
          {bullets.length > 0 && (
            <ul className="mt-5 space-y-2.5 text-sm text-[#475467]">
              {bullets.map((bullet) => (
                <li key={bullet} className="flex items-start gap-2">
                  <span className="mt-2 h-1.5 w-1.5 shrink-0 rounded-full bg-[#4d68ff]" />
                  <span>{bullet}</span>
                </li>
              ))}
            </ul>
          )}
          {actions.length > 0 && (
            <div className="mt-6 flex flex-wrap gap-3">
              {actions.map((action) => {
                const className =
                  action.tone === "secondary"
                    ? "inline-flex items-center gap-2 rounded-2xl border border-[#d5deea] bg-white px-4 py-2.5 text-sm font-semibold text-[#33415b] transition-colors hover:border-[#4d68ff] hover:text-[#3657ff]"
                    : "inline-flex items-center gap-2 rounded-2xl bg-[#4d68ff] px-4 py-2.5 text-sm font-semibold text-white transition-colors hover:bg-[#3c57ef]";
                if (action.href) {
                  return (
                    <a key={action.label} href={action.href} className={className}>
                      {action.label}
                      <ArrowRight size={15} />
                    </a>
                  );
                }
                return (
                  <button key={action.label} onClick={action.onClick} className={className}>
                    {action.label}
                    <ArrowRight size={15} />
                  </button>
                );
              })}
            </div>
          )}
        </div>
        <div className="rounded-[22px] border border-[#e7edf5] bg-[linear-gradient(180deg,#fbfdff_0%,#f4f7fb_100%)] p-5">
          {aside}
        </div>
      </div>
    </div>
  );
}

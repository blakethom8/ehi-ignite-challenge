import { Link } from "react-router-dom";

type PlaceholderProps = {
  eyebrow: string;
  title: string;
  body: string;
  ctaLabel?: string;
  ctaHref?: string;
};

export function PlaceholderShell({ eyebrow, title, body, ctaLabel, ctaHref }: PlaceholderProps) {
  return (
    <div
      className="flex min-h-0 flex-1 items-center justify-center px-10 py-16"
      style={{ background: "var(--bg-app)" }}
    >
      <div
        className="max-w-[640px] rounded-[10px] border p-10"
        style={{
          background: "var(--surface-0)",
          borderColor: "var(--line-1)",
          boxShadow: "var(--shadow-1)",
        }}
      >
        <div
          className="text-[10.5px] font-bold uppercase tracking-[0.12em]"
          style={{ color: "var(--ink-3)" }}
        >
          {eyebrow}
        </div>
        <h1
          className="mt-2 text-[26px] font-semibold leading-[1.1] tracking-tight"
          style={{ color: "var(--ink-1)" }}
        >
          {title}
        </h1>
        <p
          className="mt-3.5 text-[13.5px] leading-[1.55]"
          style={{ color: "var(--ink-2)" }}
        >
          {body}
        </p>
        {ctaLabel && ctaHref && (
          <Link
            to={ctaHref}
            className="mt-5 inline-flex items-center gap-1.5 rounded-md px-4 py-2 text-[12.5px] font-medium text-white"
            style={{ background: "var(--action)" }}
          >
            {ctaLabel}
          </Link>
        )}
      </div>
    </div>
  );
}

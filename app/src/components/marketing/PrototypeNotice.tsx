import type { ReactNode } from "react";
import { AlertTriangle, Clock3, Server } from "lucide-react";

type PrototypeNoticeProps = {
  badge?: string;
  title: string;
  summary: string;
  storageDetail: string;
  retentionDetail: string;
  cautionDetail: string;
  className?: string;
};

export function PrototypeNotice({
  badge = "Prototype notice",
  title,
  summary,
  storageDetail,
  retentionDetail,
  cautionDetail,
  className = "",
}: PrototypeNoticeProps) {
  return (
    <section className={`rounded-2xl border border-[#f0d7bf] bg-[#fff8f1] p-5 shadow-[0_18px_50px_rgba(24,32,43,0.04)] ${className}`}>
      <div className="flex flex-col gap-4">
        <div>
          <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-[#9a5a16]">
            DISCLAIMER · {badge}
          </p>
          <h2 className="mt-2 text-xl font-semibold tracking-[-0.02em] text-[#1c1c1e]">
            {title}
          </h2>
          <p className="mt-2 max-w-3xl text-sm leading-6 text-[#5f6f89]">
            {summary}
          </p>
        </div>

        <div className="grid gap-3 md:grid-cols-3">
          <NoticeItem
            icon={<Server size={16} className="text-[#9a5a16]" />}
            label="Storage"
            body={storageDetail}
          />
          <NoticeItem
            icon={<Clock3 size={16} className="text-[#9a5a16]" />}
            label="Retention"
            body={retentionDetail}
          />
          <NoticeItem
            icon={<AlertTriangle size={16} className="text-[#9a5a16]" />}
            label="Use carefully"
            body={cautionDetail}
          />
        </div>
      </div>
    </section>
  );
}

function NoticeItem({
  icon,
  label,
  body,
}: {
  icon: ReactNode;
  label: string;
  body: string;
}) {
  return (
    <div className="rounded-xl border border-[#f2dfcb] bg-white/70 p-4">
      <div className="flex items-center gap-2">
        {icon}
        <p className="text-xs font-semibold uppercase tracking-[0.14em] text-[#9a5a16]">
          {label}
        </p>
      </div>
      <p className="mt-2 text-sm leading-6 text-[#5f6f89]">
        {body}
      </p>
    </div>
  );
}

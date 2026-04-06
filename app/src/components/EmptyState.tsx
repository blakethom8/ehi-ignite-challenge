import type { LucideIcon } from "lucide-react";

interface EmptyStateProps {
  icon: LucideIcon;
  title: string;
  bullets?: string[];
  stat?: string;
  iconBg?: string;
  iconColor?: string;
}

export function EmptyState({
  icon: Icon,
  title,
  bullets,
  stat,
  iconBg = "#eef1ff",
  iconColor = "#5b76fe",
}: EmptyStateProps) {
  return (
    <div className="flex flex-col items-center justify-center h-full text-center p-8">
      <div
        className="w-16 h-16 rounded-2xl flex items-center justify-center mb-4"
        style={{ backgroundColor: iconBg }}
      >
        <Icon size={28} style={{ color: iconColor }} />
      </div>

      <h2 className="text-lg font-semibold text-[#1c1c1e] mb-2">{title}</h2>

      {bullets && bullets.length > 0 && (
        <ul className="text-sm text-[#555a6a] max-w-xs space-y-1.5 text-left list-none">
          {bullets.map((b) => (
            <li key={b} className="flex items-start gap-2">
              <span className="mt-0.5 w-1.5 h-1.5 rounded-full bg-[#5b76fe] shrink-0 inline-block" />
              <span>{b}</span>
            </li>
          ))}
        </ul>
      )}

      {stat && (
        <div className="mt-5 px-4 py-2 rounded-full bg-[#f5f6f8] border border-[#e9eaef]">
          <span className="text-xs text-[#a5a8b5]">{stat}</span>
        </div>
      )}
    </div>
  );
}

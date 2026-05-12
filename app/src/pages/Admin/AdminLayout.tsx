import type { ReactNode } from "react";
import { Link, Navigate, useLocation } from "react-router-dom";
import { ArrowLeft, Users, Activity } from "lucide-react";
import { useAccessContext } from "../../context/AccessContext";

type AdminLayoutProps = {
  children: ReactNode;
  title: string;
  subtitle?: string;
};

const NAV_ITEMS = [
  { to: "/admin/users", label: "Users", icon: Users },
  { to: "/admin/sessions", label: "Sessions", icon: Activity },
];

/**
 * Hard route guard for /admin/*: redirects anyone who is not an authenticated
 * admin back to `/`. Renders nothing while session is still loading.
 */
export function AdminLayout({ children, title, subtitle }: AdminLayoutProps) {
  const { isLoading, isUnlocked, user } = useAccessContext();
  const location = useLocation();

  if (isLoading) {
    return (
      <div className="grid min-h-screen place-items-center bg-[var(--bg-app)]">
        <div className="h-10 w-10 animate-spin rounded-full border-4 border-[var(--line-1)] border-t-[var(--action)]" />
      </div>
    );
  }

  if (!isUnlocked || !user || user.role !== "admin") {
    return <Navigate to="/" replace />;
  }

  return (
    <div className="min-h-screen bg-[#eef2f6] px-6 py-8 text-[#18202b]">
      <div className="mx-auto max-w-6xl">
        <header className="flex items-center justify-between gap-4">
          <Link
            to="/"
            className="inline-flex items-center gap-2 text-sm font-semibold text-[#52627f] transition-colors hover:text-[#3657ff]"
          >
            <ArrowLeft size={16} />
            Back to Atlas
          </Link>
          <div className="text-xs text-[#62728d]">
            Signed in as {user.display_name} <span className="ml-1 rounded-full bg-[#dbeafe] px-2 py-[1px] text-[10px] font-semibold uppercase tracking-[0.08em] text-[#1d4ed8]">admin</span>
          </div>
        </header>

        <div className="mt-8 grid gap-6 lg:grid-cols-[200px_1fr]">
          <aside className="rounded-2xl border border-[#d8e0eb] bg-white p-3 shadow-sm">
            <p className="px-2 pb-2 text-[11px] font-semibold uppercase tracking-[0.16em] text-[#62728d]">
              Admin
            </p>
            <nav className="flex flex-col gap-1">
              {NAV_ITEMS.map((item) => {
                const Icon = item.icon;
                const active = location.pathname.startsWith(item.to);
                return (
                  <Link
                    key={item.to}
                    to={item.to}
                    className={`inline-flex items-center gap-2 rounded-xl px-3 py-2 text-sm transition-colors ${
                      active
                        ? "bg-[#4d68ff] text-white"
                        : "text-[#33415b] hover:bg-[#f2f5fa]"
                    }`}
                  >
                    <Icon size={16} />
                    {item.label}
                  </Link>
                );
              })}
            </nav>
          </aside>

          <section>
            <div className="mb-6">
              <h1 className="text-3xl font-semibold tracking-[-0.03em] text-[#171b24]">{title}</h1>
              {subtitle && (
                <p className="mt-1 text-sm text-[#62728d]">{subtitle}</p>
              )}
            </div>
            {children}
          </section>
        </div>
      </div>
    </div>
  );
}

export function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  if (bytes < 1024 * 1024 * 1024) return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  return `${(bytes / (1024 * 1024 * 1024)).toFixed(2)} GB`;
}

export function formatRelative(value: string | null): string {
  if (!value) return "Never";
  try {
    const date = new Date(value);
    const diff = Date.now() - date.getTime();
    if (diff < 60_000) return "Just now";
    if (diff < 3_600_000) return `${Math.floor(diff / 60_000)}m ago`;
    if (diff < 86_400_000) return `${Math.floor(diff / 3_600_000)}h ago`;
    if (diff < 7 * 86_400_000) return `${Math.floor(diff / 86_400_000)}d ago`;
    return date.toLocaleDateString();
  } catch {
    return value;
  }
}

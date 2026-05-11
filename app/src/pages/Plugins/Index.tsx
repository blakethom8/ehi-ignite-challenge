import { Link } from "react-router-dom";
import { Boxes, Pill, Send, Stethoscope, Telescope, UserRound } from "lucide-react";
import { useInstalledManifests } from "../../components/atlas/manifests";

const PLUGIN_ICONS: Record<string, typeof Telescope> = {
  Telescope,
  Pill,
  Send,
  Boxes,
  Stethoscope,
  UserRound,
};

export function PluginsIndex() {
  const { data: manifests, isLoading } = useInstalledManifests();

  return (
    <div className="mx-auto w-full max-w-[1100px] flex-1 px-10 py-9" style={{ background: "var(--bg-app)" }}>
      <div className="border-b pb-7" style={{ borderColor: "var(--line-1)" }}>
        <div className="flex items-center gap-2 text-[10.5px] font-bold uppercase tracking-[0.12em]" style={{ color: "var(--ink-3)" }}>
          <Boxes className="h-3.5 w-3.5" strokeWidth={1.5} />
          Plugin marketplace
        </div>
        <h1 className="mt-2 text-[26px] font-semibold leading-[1.1] tracking-tight" style={{ color: "var(--ink-1)" }}>
          Installable plugins
        </h1>
        <p className="mt-3 max-w-[70ch] text-[13.5px] leading-[1.55]" style={{ color: "var(--ink-2)" }}>
          Plugins run inside the same shell as Caspian, but with their own context strip, permissions ledger, and approval gates. Each plugin operates against a consented patient anchor. Outbound actions never leave the workspace without an explicit clinician approval.
        </p>
      </div>

      <div className="mt-7 grid grid-cols-1 gap-3 md:grid-cols-2">
        {isLoading && (
          <div className="text-[13px]" style={{ color: "var(--ink-3)" }}>Loading installed plugins…</div>
        )}
        {!isLoading && (manifests ?? []).length === 0 && (
          <div className="text-[13px]" style={{ color: "var(--ink-3)" }}>
            No plugins installed. Run `uv run python scripts/build_example_plugins.py` to seed the three examples.
          </div>
        )}
        {(manifests ?? []).map((m) => {
          const Icon = PLUGIN_ICONS[m.icon] ?? Boxes;
          return (
            <Link
              key={m.id}
              to={`/workspaces/${m.id}`}
              className="group flex flex-col gap-2 rounded-md border p-4 transition-colors hover:border-[var(--action-line)]"
              style={{ background: "var(--surface-1)", borderColor: "var(--line-1)" }}
            >
              <div className="flex items-center gap-2.5">
                <div
                  className="grid h-9 w-9 place-items-center rounded-md"
                  style={{ background: tint(m.color, 0.1), color: m.color }}
                >
                  <Icon className="h-4 w-4" strokeWidth={1.5} />
                </div>
                <div className="min-w-0 flex-1">
                  <div className="flex items-baseline gap-2">
                    <div className="text-[13.5px] font-semibold" style={{ color: "var(--ink-1)" }}>
                      {m.displayName}
                    </div>
                    <div
                      className="rounded-[3px] px-1.5 py-px text-[11px] font-medium"
                      style={{ background: tint(m.color, 0.08), color: m.color, fontFamily: "var(--font-mono)" }}
                    >
                      @{m.version}
                    </div>
                  </div>
                  <div className="text-[11.5px]" style={{ color: "var(--ink-3)" }}>by {m.vendor.name}</div>
                </div>
              </div>
              <p className="text-[12.5px] leading-[1.55]" style={{ color: "var(--ink-2)" }}>
                {m.description}
              </p>
              <div className="mt-1 flex items-center justify-between border-t pt-2.5 text-[11px]" style={{ borderColor: "var(--line-1)", color: "var(--ink-3)" }}>
                <span>Boundary: {m.trust.boundaryLabel}</span>
                <span className="font-medium transition-colors group-hover:text-[var(--action)]" style={{ color: "var(--ink-3)" }}>
                  Open plugin home →
                </span>
              </div>
            </Link>
          );
        })}
      </div>
    </div>
  );
}

function tint(color: string, alpha: number): string {
  if (!color.startsWith("#") || color.length !== 7) return `rgba(67,56,202,${alpha})`;
  const r = parseInt(color.slice(1, 3), 16);
  const g = parseInt(color.slice(3, 5), 16);
  const b = parseInt(color.slice(5, 7), 16);
  return `rgba(${r},${g},${b},${alpha})`;
}

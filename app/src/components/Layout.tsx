import { useEffect, useState } from "react";
import { NavLink, useSearchParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { Activity, Star, Database, Heart, CalendarDays, BarChart3, ShieldAlert, Syringe, Scissors, ClipboardCheck, Stethoscope } from "lucide-react";
import { api } from "../api/client";
import { useFavorites } from "../hooks/useFavorites";
import { CommandPalette } from "./CommandPalette";
import type { PatientListItem } from "../types";

interface LayoutProps {
  children: React.ReactNode;
}

// ── Patient list with favorites ─────────────────────────────────────────────

function PatientList({
  selectedId,
  onSelect,
}: {
  selectedId: string | null;
  onSelect: (id: string) => void;
}) {
  const { data: patients = [], isLoading } = useQuery({
    queryKey: ["patients"],
    queryFn: api.listPatients,
    staleTime: Infinity,
  });

  const { isFavorite, toggleFavorite } = useFavorites();

  const favorites = patients.filter((p) => isFavorite(p.id));
  const others = patients.filter((p) => !isFavorite(p.id));

  function renderRow(p: PatientListItem) {
    const active = p.id === selectedId;
    const faved = isFavorite(p.id);
    return (
      <div
        key={p.id}
        className={`group flex items-center gap-1 pr-1 rounded-lg transition-colors ${
          active ? "bg-[#eef1ff]" : "hover:bg-[#f5f6f8]"
        }`}
      >
        <button
          onClick={() => onSelect(p.id)}
          className={`flex-1 text-left px-3 py-2 text-sm truncate ${
            active ? "text-[#5b76fe] font-medium" : "text-[#1c1c1e]"
          }`}
        >
          {p.name}
        </button>
        <button
          onClick={(e) => {
            e.stopPropagation();
            toggleFavorite(p.id);
          }}
          title={faved ? "Remove from favorites" : "Add to favorites"}
          className={`shrink-0 p-1 rounded transition-colors ${
            faved
              ? "text-[#5b76fe]"
              : "text-transparent group-hover:text-[#c7cad5] hover:!text-[#5b76fe]"
          }`}
        >
          <Star
            size={13}
            fill={faved ? "currentColor" : "none"}
            strokeWidth={faved ? 0 : 1.5}
          />
        </button>
      </div>
    );
  }

  if (isLoading) {
    return (
      <div className="space-y-1 px-1">
        {[1, 2, 3, 4].map((i) => (
          <div key={i} className="h-8 bg-[#f5f6f8] rounded-lg animate-pulse" />
        ))}
      </div>
    );
  }

  return (
    <div className="flex-1 overflow-y-auto px-2 py-2">
      {favorites.length > 0 && (
        <>
          <p className="px-2 mb-1 text-[10px] font-semibold text-[#a5a8b5] uppercase tracking-wider">
            Favorites
          </p>
          <div className="space-y-0.5 mb-3">{favorites.map(renderRow)}</div>
          <div className="border-t border-[#e9eaef] mb-3" />
          <p className="px-2 mb-1 text-[10px] font-semibold text-[#a5a8b5] uppercase tracking-wider">
            All Patients
          </p>
        </>
      )}
      {favorites.length === 0 && (
        <p className="px-2 mb-1 text-[10px] font-semibold text-[#a5a8b5] uppercase tracking-wider">
          All Patients
        </p>
      )}
      <div className="space-y-0.5">{others.map(renderRow)}</div>
      {patients.length === 0 && !isLoading && (
        <p className="px-3 py-4 text-sm text-[#a5a8b5] text-center">
          No patients available
        </p>
      )}
    </div>
  );
}

// ── Nav links ───────────────────────────────────────────────────────────────

const NAV_LINKS = [
  { to: "/explorer", label: "Overview", icon: Database, description: "Patient summary" },
  { to: "/explorer/timeline", label: "Timeline", icon: CalendarDays, description: "Encounter history" },
  { to: "/explorer/safety", label: "Safety", icon: ShieldAlert, description: "Pre-op risk flags" },
  { to: "/explorer/conditions", label: "Conditions", icon: Activity, description: "Surgical risk ranking" },
  { to: "/explorer/procedures", label: "Procedures", icon: Scissors, description: "Procedure history" },
  { to: "/explorer/immunizations", label: "Immunizations", icon: Syringe, description: "Vaccination history" },
  { to: "/explorer/clearance", label: "Clearance", icon: ClipboardCheck, description: "Pre-op readiness check" },
  { to: "/explorer/anesthesia", label: "Anesthesia", icon: Stethoscope, description: "Anesthesia handoff card" },
  { to: "/explorer/corpus", label: "Corpus", icon: BarChart3, description: "Population statistics" },
  { to: "/journey", label: "Patient Journey", icon: Heart, description: "Clinical briefing" },
];

// ── Layout ──────────────────────────────────────────────────────────────────

export function Layout({ children }: LayoutProps) {
  const [searchParams, setSearchParams] = useSearchParams();
  const patientId = searchParams.get("patient");
  const [paletteOpen, setPaletteOpen] = useState(false);

  const handleSelectPatient = (id: string) => {
    setSearchParams({ patient: id });
  };

  // Cmd+K / Ctrl+K global shortcut
  useEffect(() => {
    function onKeyDown(e: KeyboardEvent) {
      if ((e.metaKey || e.ctrlKey) && e.key === "k") {
        e.preventDefault();
        setPaletteOpen((o) => !o);
      }
    }
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, []);

  return (
    <>
      <CommandPalette
        open={paletteOpen}
        onClose={() => setPaletteOpen(false)}
      />

      <div className="flex h-screen overflow-hidden">
        {/* Sidebar */}
        <aside className="w-64 shrink-0 flex flex-col bg-white border-r border-[#e9eaef] overflow-hidden">
          {/* Brand */}
          <div className="px-4 pt-5 pb-4 border-b border-[#e9eaef] shrink-0">
            <div className="flex items-center gap-2 mb-1">
              <Activity size={18} className="text-[#5b76fe]" />
              <span className="font-semibold text-[#1c1c1e] text-sm tracking-tight">
                EHI Ignite
              </span>
            </div>
            <p className="text-xs text-[#a5a8b5]">Clinical Intelligence Platform</p>
          </div>

          {/* Cmd+K search trigger */}
          <div className="px-4 py-3 border-b border-[#e9eaef] shrink-0">
            <button
              onClick={() => setPaletteOpen(true)}
              className="w-full flex items-center gap-2 px-3 py-2 rounded-lg border border-[#e9eaef] bg-[#f5f6f8] text-sm text-[#a5a8b5] hover:border-[#5b76fe] hover:text-[#555a6a] transition-colors"
            >
              <span className="flex-1 text-left">Search patients…</span>
              <kbd className="text-[10px] font-mono bg-white border border-[#e9eaef] rounded px-1 py-0.5 shrink-0">
                ⌘K
              </kbd>
            </button>
          </div>

          {/* Patient list */}
          <PatientList
            selectedId={patientId}
            onSelect={handleSelectPatient}
          />

          {/* Navigation */}
          <nav className="shrink-0 px-3 py-4 border-t border-[#e9eaef] space-y-0.5">
            <p className="px-2 mb-2 text-xs font-medium text-[#a5a8b5] uppercase tracking-wider">
              Views
            </p>
            {NAV_LINKS.map(({ to, label, icon: Icon, description }) => (
              <NavLink
                key={to}
                to={`${to}${patientId ? `?patient=${patientId}` : ""}`}
                className={({ isActive }) =>
                  `flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm transition-colors ${
                    isActive
                      ? "bg-[#eef1ff] text-[#5b76fe] font-medium"
                      : "text-[#555a6a] hover:bg-[#f5f6f8] hover:text-[#1c1c1e]"
                  }`
                }
              >
                <Icon size={16} />
                <div>
                  <div>{label}</div>
                  <div className="text-xs opacity-60 font-normal">{description}</div>
                </div>
              </NavLink>
            ))}
          </nav>

          {/* Footer */}
          <div className="px-4 py-3 border-t border-[#e9eaef] shrink-0">
            <p className="text-xs text-[#a5a8b5]">EHI Ignite Challenge · Phase 1</p>
          </div>
        </aside>

        {/* Main content */}
        <main className="flex-1 overflow-y-auto bg-[#f5f6f8]">
          {children}
        </main>
      </div>
    </>
  );
}

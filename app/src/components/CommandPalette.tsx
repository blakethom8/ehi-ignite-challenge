import { useEffect, useRef, useState, useCallback } from "react";
import { useNavigate } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { Search, X } from "lucide-react";
import { api } from "../api/client";
import type { PatientListItem } from "../types";

const TIER_LABEL: Record<string, string> = {
  simple: "S",
  moderate: "M",
  complex: "C",
  highly_complex: "HC",
};

const TIER_STYLE: Record<string, string> = {
  simple: "bg-[#c3faf5] text-[#187574]",
  moderate: "bg-[#ffe6cd] text-[#744000]",
  complex: "bg-[#ffc6c6] text-[#600000]",
  highly_complex: "bg-[#ffc6c6] text-[#600000]",
};

interface CommandPaletteProps {
  open: boolean;
  onClose: () => void;
}

export function CommandPalette({ open, onClose }: CommandPaletteProps) {
  const [query, setQuery] = useState("");
  const [activeIndex, setActiveIndex] = useState(0);
  const inputRef = useRef<HTMLInputElement>(null);
  const listRef = useRef<HTMLDivElement>(null);
  const navigate = useNavigate();

  const { data: patients = [] } = useQuery({
    queryKey: ["patients"],
    queryFn: api.listPatients,
    staleTime: Infinity,
  });

  const filtered: PatientListItem[] = query.trim()
    ? patients
        .filter((p) =>
          p.name.toLowerCase().includes(query.toLowerCase())
        )
        .slice(0, 8)
    : patients.slice(0, 8);

  // Reset state when opening
  useEffect(() => {
    if (open) {
      setQuery("");
      setActiveIndex(0);
      setTimeout(() => inputRef.current?.focus(), 0);
    }
  }, [open]);

  // Keep activeIndex in bounds when filtered list changes
  useEffect(() => {
    setActiveIndex(0);
  }, [query]);

  const selectPatient = useCallback(
    (patient: PatientListItem) => {
      navigate(`/explorer?patient=${patient.id}`);
      onClose();
    },
    [navigate, onClose]
  );

  // Scroll active item into view
  useEffect(() => {
    if (!listRef.current) return;
    const active = listRef.current.querySelector<HTMLButtonElement>(
      `[data-idx="${activeIndex}"]`
    );
    active?.scrollIntoView({ block: "nearest" });
  }, [activeIndex]);

  function handleKeyDown(e: React.KeyboardEvent) {
    if (e.key === "ArrowDown") {
      e.preventDefault();
      setActiveIndex((i) => Math.min(i + 1, filtered.length - 1));
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      setActiveIndex((i) => Math.max(i - 1, 0));
    } else if (e.key === "Enter") {
      e.preventDefault();
      const patient = filtered[activeIndex];
      if (patient) selectPatient(patient);
    } else if (e.key === "Escape") {
      onClose();
    }
  }

  if (!open) return null;

  return (
    <div
      className="fixed inset-0 z-[100] flex items-start justify-center pt-[15vh]"
      style={{ backgroundColor: "rgba(0,0,0,0.45)" }}
      onClick={(e) => {
        if (e.target === e.currentTarget) onClose();
      }}
    >
      <div
        className="w-full max-w-lg bg-white rounded-2xl shadow-2xl overflow-hidden"
        style={{ border: "1px solid #e9eaef" }}
      >
        {/* Search input */}
        <div className="flex items-center gap-3 px-4 py-3.5 border-b border-[#e9eaef]">
          <Search size={16} className="text-[#a5a8b5] shrink-0" />
          <input
            ref={inputRef}
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Search patients by name…"
            className="flex-1 text-sm text-[#1c1c1e] outline-none placeholder:text-[#a5a8b5] bg-transparent"
          />
          {query && (
            <button
              onClick={() => setQuery("")}
              className="text-[#a5a8b5] hover:text-[#555a6a] transition-colors"
            >
              <X size={14} />
            </button>
          )}
          <kbd className="hidden sm:inline-flex items-center px-1.5 py-0.5 rounded text-[10px] font-mono text-[#a5a8b5] bg-[#f5f6f8] border border-[#e9eaef]">
            ESC
          </kbd>
        </div>

        {/* Results */}
        <div ref={listRef} className="max-h-80 overflow-y-auto py-1">
          {filtered.length === 0 ? (
            <p className="text-sm text-[#a5a8b5] text-center py-6">
              No patients match &ldquo;{query}&rdquo;
            </p>
          ) : (
            filtered.map((p, i) => {
              const isActive = i === activeIndex;
              const tierKey = p.complexity_tier ?? "simple";
              return (
                <button
                  key={p.id}
                  data-idx={i}
                  onClick={() => selectPatient(p)}
                  onMouseEnter={() => setActiveIndex(i)}
                  className={`w-full flex items-center gap-3 px-4 py-2.5 text-left transition-colors ${
                    isActive ? "bg-[#eef1ff]" : "hover:bg-[#f5f6f8]"
                  }`}
                >
                  {/* Name */}
                  <span
                    className={`flex-1 text-sm font-medium truncate ${
                      isActive ? "text-[#5b76fe]" : "text-[#1c1c1e]"
                    }`}
                  >
                    {p.name}
                  </span>

                  {/* Age + gender */}
                  <span className="text-xs text-[#a5a8b5] shrink-0">
                    {p.age_years != null ? `${Math.round(p.age_years)}y` : ""}{" "}
                    {p.gender ? p.gender.charAt(0).toUpperCase() : ""}
                  </span>

                  {/* Complexity tier badge */}
                  <span
                    className={`text-[10px] font-semibold px-1.5 py-0.5 rounded-full shrink-0 ${
                      TIER_STYLE[tierKey] ?? "bg-[#f5f6f8] text-[#555a6a]"
                    }`}
                  >
                    {TIER_LABEL[tierKey] ?? tierKey}
                  </span>
                </button>
              );
            })
          )}
        </div>

        {/* Footer hint */}
        <div className="px-4 py-2 border-t border-[#e9eaef] flex items-center gap-4">
          <span className="text-[10px] text-[#a5a8b5]">
            <kbd className="font-mono">↑↓</kbd> navigate
          </span>
          <span className="text-[10px] text-[#a5a8b5]">
            <kbd className="font-mono">↵</kbd> select
          </span>
          <span className="text-[10px] text-[#a5a8b5]">
            <kbd className="font-mono">esc</kbd> close
          </span>
          {patients.length > 0 && (
            <span className="ml-auto text-[10px] text-[#a5a8b5]">
              {patients.length.toLocaleString()} patients
            </span>
          )}
        </div>
      </div>
    </div>
  );
}

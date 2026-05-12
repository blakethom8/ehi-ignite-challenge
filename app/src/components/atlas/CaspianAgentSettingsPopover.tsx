import { useEffect, useRef, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { ChevronDown, Settings2 } from "lucide-react";
import { api } from "../../api/client";
import { AgentSettingsPanel } from "../AgentSettingsPanel";
import type { AgentSettings } from "../../context/ChatContext";

type Props = {
  settings: AgentSettings;
  onUpdate: (next: AgentSettings) => void;
};

/**
 * Caspian-scoped popover wrapper around AgentSettingsPanel.
 *
 * Shows a compact pill (mode | model) in the chat pane header. On click,
 * opens an absolute-positioned panel with the full mode/model/max-tokens
 * controls. Independent from the legacy ChatContext settings used by the
 * FHIR Charts assistant — Caspian persists its own settings per principal.
 */
export function CaspianAgentSettingsPopover({ settings, onUpdate }: Props) {
  const [open, setOpen] = useState(false);
  const containerRef = useRef<HTMLDivElement | null>(null);

  const { data: config } = useQuery({
    queryKey: ["assistant-settings"],
    queryFn: api.getAssistantSettings,
    staleTime: 60_000,
  });

  const activeModel = settings.model || config?.current.model || "claude-sonnet-4-5";
  const activeMode = settings.mode || config?.current.mode || "anthropic";
  const activeModelLabel =
    config?.available_models.find((m) => m.id === activeModel)?.label || activeModel;
  const activeModeLabel =
    config?.available_modes.find((m) => m.id === activeMode)?.label || activeMode;

  useEffect(() => {
    if (!open) return;
    function handlePointerDown(event: MouseEvent) {
      if (!containerRef.current) return;
      if (event.target instanceof Node && containerRef.current.contains(event.target)) return;
      setOpen(false);
    }
    function handleKey(event: KeyboardEvent) {
      if (event.key === "Escape") setOpen(false);
    }
    window.addEventListener("mousedown", handlePointerDown);
    window.addEventListener("keydown", handleKey);
    return () => {
      window.removeEventListener("mousedown", handlePointerDown);
      window.removeEventListener("keydown", handleKey);
    };
  }, [open]);

  return (
    <div ref={containerRef} className="relative">
      <button
        type="button"
        onClick={() => setOpen((prev) => !prev)}
        className="inline-flex items-center gap-1 rounded border px-2.5 py-1 text-[11px] font-medium hover:bg-[var(--surface-2)]"
        style={{
          background: "var(--surface-1)",
          borderColor: "var(--line-2)",
          color: "var(--ink-1)",
        }}
        aria-expanded={open}
        aria-haspopup="dialog"
        title="Caspian agent settings"
      >
        <Settings2 className="h-2.5 w-2.5" strokeWidth={1.5} />
        <span>{activeModeLabel}</span>
        <span style={{ color: "var(--ink-4)" }}>·</span>
        <span>{activeModelLabel}</span>
        <ChevronDown className="h-2.5 w-2.5" strokeWidth={1.5} />
      </button>
      {open && (
        <div
          role="dialog"
          aria-label="Caspian agent settings"
          className="absolute right-0 top-[calc(100%+6px)] z-30 w-[340px]"
        >
          <AgentSettingsPanel settings={settings} onUpdate={onUpdate} defaultOpen lockOpen />
        </div>
      )}
    </div>
  );
}

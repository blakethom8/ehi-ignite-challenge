import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { ChevronDown, Settings2, Zap, Brain, Cpu, Gauge } from "lucide-react";
import { api } from "../api/client";
import type { AgentSettings } from "../context/ChatContext";

const SPEED_ICONS: Record<string, React.ReactNode> = {
  fast: <Zap size={12} className="text-green-500" />,
  medium: <Gauge size={12} className="text-amber-500" />,
  slow: <Brain size={12} className="text-purple-500" />,
};

const MODE_ICONS: Record<string, React.ReactNode> = {
  deterministic: <Cpu size={12} className="text-slate-500" />,
  context: <Zap size={12} className="text-blue-500" />,
  anthropic: <Brain size={12} className="text-purple-500" />,
};

export function AgentSettingsPanel({
  settings,
  onUpdate,
}: {
  settings: AgentSettings;
  onUpdate: (next: AgentSettings) => void;
}) {
  const [open, setOpen] = useState(false);

  const { data: config } = useQuery({
    queryKey: ["assistant-settings"],
    queryFn: api.getAssistantSettings,
    staleTime: 60_000,
  });

  const activeModel = settings.model || config?.current.model || "claude-sonnet-4-5";
  const activeMode = settings.mode || config?.current.mode || "context";
  const activeModelLabel = config?.available_models.find((m) => m.id === activeModel)?.label || activeModel;
  const activeModeLabel = config?.available_modes.find((m) => m.id === activeMode)?.label || activeMode;

  if (!open) {
    return (
      <button
        onClick={() => setOpen(true)}
        className="inline-flex items-center gap-1.5 rounded-lg border border-slate-200 bg-white px-2.5 py-1.5 text-[11px] text-slate-600 hover:border-blue-300 hover:text-blue-700 transition-colors"
        title="Agent settings"
      >
        <Settings2 size={12} />
        <span className="font-medium">{activeModelLabel}</span>
        <span className="text-slate-300">|</span>
        <span>{activeModeLabel}</span>
        <ChevronDown size={10} />
      </button>
    );
  }

  return (
    <div className="rounded-xl border border-slate-200 bg-white shadow-lg p-4 space-y-4 w-[340px]">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Settings2 size={14} className="text-slate-500" />
          <span className="text-[13px] font-semibold text-[#1c1c1e]">Agent Settings</span>
        </div>
        <button
          onClick={() => setOpen(false)}
          className="text-[11px] text-blue-600 hover:text-blue-800 font-medium"
        >
          Done
        </button>
      </div>

      {/* Model selector */}
      <div>
        <label className="block text-[10px] font-semibold uppercase tracking-wider text-slate-500 mb-1.5">
          Model
        </label>
        <div className="space-y-1">
          {(config?.available_models ?? []).map((model) => (
            <button
              key={model.id}
              onClick={() => onUpdate({ ...settings, model: model.id })}
              className={`flex items-center gap-2.5 w-full rounded-lg px-3 py-2 text-left transition-colors ${
                activeModel === model.id
                  ? "bg-blue-50 ring-1 ring-blue-200"
                  : "hover:bg-slate-50"
              }`}
            >
              {SPEED_ICONS[model.speed] || <Gauge size={12} />}
              <div className="flex-1 min-w-0">
                <div className={`text-[12px] font-medium ${activeModel === model.id ? "text-blue-700" : "text-[#1c1c1e]"}`}>
                  {model.label}
                </div>
                <div className="text-[10px] text-slate-500">{model.description}</div>
              </div>
              {activeModel === model.id && (
                <span className="text-[9px] font-semibold uppercase text-blue-600">Active</span>
              )}
            </button>
          ))}
        </div>
      </div>

      {/* Mode selector */}
      <div>
        <label className="block text-[10px] font-semibold uppercase tracking-wider text-slate-500 mb-1.5">
          Mode
        </label>
        <div className="space-y-1">
          {(config?.available_modes ?? []).map((mode) => (
            <button
              key={mode.id}
              onClick={() => onUpdate({ ...settings, mode: mode.id })}
              className={`flex items-center gap-2.5 w-full rounded-lg px-3 py-2 text-left transition-colors ${
                activeMode === mode.id
                  ? "bg-blue-50 ring-1 ring-blue-200"
                  : "hover:bg-slate-50"
              }`}
            >
              {MODE_ICONS[mode.id] || <Cpu size={12} />}
              <div className="flex-1 min-w-0">
                <div className={`text-[12px] font-medium ${activeMode === mode.id ? "text-blue-700" : "text-[#1c1c1e]"}`}>
                  {mode.label}
                </div>
                <div className="text-[10px] text-slate-500">{mode.description}</div>
              </div>
              {activeMode === mode.id && (
                <span className="text-[9px] font-semibold uppercase text-blue-600">Active</span>
              )}
            </button>
          ))}
        </div>
      </div>

      {/* Max tokens slider */}
      <div>
        <label className="block text-[10px] font-semibold uppercase tracking-wider text-slate-500 mb-1.5">
          Max Response Length
        </label>
        <div className="flex items-center gap-3">
          <input
            type="range"
            min={300}
            max={4000}
            step={100}
            value={settings.maxTokens}
            onChange={(e) => onUpdate({ ...settings, maxTokens: Number(e.target.value) })}
            className="flex-1 h-1.5 rounded-full appearance-none bg-slate-200 accent-blue-500"
          />
          <span className="text-[11px] font-medium text-slate-700 w-16 text-right">
            {settings.maxTokens} tok
          </span>
        </div>
        <div className="flex justify-between mt-1 text-[9px] text-slate-400">
          <span>Concise</span>
          <span>Detailed</span>
        </div>
      </div>

      {/* Reset */}
      <button
        onClick={() => onUpdate({ model: "", mode: "", maxTokens: 1500 })}
        className="w-full rounded-lg border border-slate-200 py-1.5 text-[11px] text-slate-500 hover:bg-slate-50 hover:text-slate-700 transition-colors"
      >
        Reset to server defaults
      </button>
    </div>
  );
}

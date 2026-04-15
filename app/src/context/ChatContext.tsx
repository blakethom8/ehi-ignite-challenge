import { createContext, useCallback, useContext, useMemo, useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { api } from "../api/client";
import type {
  ProviderAssistantCitation,
  ProviderAssistantResponse,
  ProviderAssistantTurn,
  TraceDetail,
} from "../types";

// ── Types ────────────────────────────────────────────────────────────────────

export type ChatMessage =
  | { id: string; role: "user"; content: string }
  | {
      id: string;
      role: "assistant";
      content: string;
      confidence: ProviderAssistantResponse["confidence"];
      engine: ProviderAssistantResponse["engine"];
      citations: ProviderAssistantCitation[];
      followUps: string[];
      trace: TraceDetail | null;
    };

export interface AgentSettings {
  model: string;
  mode: string;
  maxTokens: number;
}

const DEFAULT_SETTINGS: AgentSettings = {
  model: "",       // empty = use server default
  mode: "",        // empty = use server default
  maxTokens: 1500,
};

interface ChatContextInner {
  messagesByPatient: Record<string, ChatMessage[]>;
  stance: "opinionated" | "balanced";
  setStance: (s: "opinionated" | "balanced") => void;
  agentSettings: AgentSettings;
  setAgentSettings: (s: AgentSettings) => void;
  submitQuestion: (patientId: string, question: string) => void;
  isPending: boolean;
  isError: boolean;
  error: unknown;
}

/** Public per-patient API returned by useChatForPatient */
export interface PatientChatHandle {
  messages: ChatMessage[];
  stance: "opinionated" | "balanced";
  setStance: (s: "opinionated" | "balanced") => void;
  agentSettings: AgentSettings;
  setAgentSettings: (s: AgentSettings) => void;
  submitQuestion: (question: string) => void;
  isPending: boolean;
  isError: boolean;
  error: unknown;
}

const ChatContext = createContext<ChatContextInner | null>(null);

// ── Provider ─────────────────────────────────────────────────────────────────

export function ChatProvider({ children }: { children: React.ReactNode }) {
  const [stance, setStance] = useState<"opinionated" | "balanced">("opinionated");
  const [agentSettings, setAgentSettings] = useState<AgentSettings>(() => {
    try {
      const saved = localStorage.getItem("ehi-agent-settings");
      if (saved) return { ...DEFAULT_SETTINGS, ...JSON.parse(saved) };
    } catch { /* noop */ }
    return DEFAULT_SETTINGS;
  });
  const [messagesByPatient, setMessagesByPatient] = useState<Record<string, ChatMessage[]>>({});

  const updateSettings = useCallback((next: AgentSettings) => {
    setAgentSettings(next);
    try { localStorage.setItem("ehi-agent-settings", JSON.stringify(next)); } catch { /* noop */ }
  }, []);

  const mutation = useMutation({
    mutationFn: async (payload: {
      patientId: string;
      question: string;
      history: ProviderAssistantTurn[];
      stance: "opinionated" | "balanced";
      model?: string;
      mode?: string;
      max_tokens?: number;
    }) => {
      return api.chatProviderAssistant({
        patient_id: payload.patientId,
        question: payload.question,
        history: payload.history,
        stance: payload.stance,
        model: payload.model || undefined,
        mode: payload.mode || undefined,
        max_tokens: payload.max_tokens || undefined,
      });
    },
    onSuccess: (data, variables) => {
      setMessagesByPatient((prev) => {
        const current = prev[variables.patientId] ?? [];
        return {
          ...prev,
          [variables.patientId]: [
            ...current,
            {
              id: crypto.randomUUID(),
              role: "assistant",
              content: data.answer,
              confidence: data.confidence,
              engine: data.engine,
              citations: data.citations,
              followUps: data.follow_ups,
              trace: data.trace,
            },
          ],
        };
      });
    },
  });

  const submitQuestion = useCallback(
    (patientId: string, question: string) => {
      const trimmed = question.trim();
      if (!trimmed || mutation.isPending) return;

      const currentMessages = messagesByPatient[patientId] ?? [];
      const history: ProviderAssistantTurn[] = currentMessages.map((m) => ({
        role: m.role,
        content: m.content,
      }));

      setMessagesByPatient((prev) => ({
        ...prev,
        [patientId]: [
          ...(prev[patientId] ?? []),
          { id: crypto.randomUUID(), role: "user", content: trimmed },
        ],
      }));

      mutation.mutate({
        patientId,
        question: trimmed,
        history,
        stance,
        model: agentSettings.model || undefined,
        mode: agentSettings.mode || undefined,
        max_tokens: agentSettings.maxTokens || undefined,
      });
    },
    [messagesByPatient, mutation, stance, agentSettings],
  );

  const value = useMemo<ChatContextInner>(
    () => ({
      messagesByPatient,
      stance,
      setStance,
      agentSettings,
      setAgentSettings: updateSettings,
      submitQuestion,
      isPending: mutation.isPending,
      isError: mutation.isError,
      error: mutation.error,
    }),
    [messagesByPatient, stance, agentSettings, updateSettings, submitQuestion, mutation.isPending, mutation.isError, mutation.error],
  );

  return <ChatContext.Provider value={value}>{children}</ChatContext.Provider>;
}

// ── Hook: per-patient handle ─────────────────────────────────────────────────

export function useChatForPatient(patientId: string | null): PatientChatHandle {
  const ctx = useContext(ChatContext);
  if (!ctx) throw new Error("useChatForPatient must be used within a ChatProvider");

  const messages = useMemo(
    () => (patientId ? ctx.messagesByPatient[patientId] ?? [] : []),
    [ctx.messagesByPatient, patientId],
  );

  const submit = useCallback(
    (question: string) => {
      if (patientId) ctx.submitQuestion(patientId, question);
    },
    [ctx.submitQuestion, patientId],
  );

  return {
    messages,
    stance: ctx.stance,
    setStance: ctx.setStance,
    agentSettings: ctx.agentSettings,
    setAgentSettings: ctx.setAgentSettings,
    submitQuestion: submit,
    isPending: ctx.isPending,
    isError: ctx.isError,
    error: ctx.error,
  };
}

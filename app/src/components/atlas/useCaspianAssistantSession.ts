import { useCallback, useEffect, useMemo, useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { api } from "../../api/client";
import type { ProviderAssistantCitation, ProviderAssistantTurn, TraceDetail } from "../../types";
import type { Citation } from "./data";

const STORAGE_PREFIX = "atlas:caspian:assistant";

type CaspianCitation = ProviderAssistantCitation & {
  id: string;
};

export type CaspianAssistantMessage =
  | {
      id: string;
      role: "user";
      content: string;
      createdAt: string;
    }
  | {
      id: string;
      role: "assistant";
      content: string;
      confidence: "high" | "medium" | "low";
      engine: string;
      citations: CaspianCitation[];
      followUps: string[];
      trace: TraceDetail | null;
      createdAt: string;
    };

export type CaspianInspectorData = {
  citations: Record<string, Citation>;
  traceByCitationId: Record<string, TraceDetail | null>;
  latestTrace: TraceDetail | null;
  contextItems: Array<{ label: string; value: string }>;
};

type ChatResponse = Awaited<ReturnType<typeof api.chatProviderAssistant>>;

function messageId(prefix: "u" | "a"): string {
  return `${prefix}_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`;
}

function storageKey(patientId: string | null, sessionId: string | null): string | null {
  if (!patientId || !sessionId) return null;
  return `${STORAGE_PREFIX}:${patientId}:${sessionId}`;
}

function readMessages(key: string | null): CaspianAssistantMessage[] {
  if (!key) return [];
  try {
    const raw = window.localStorage.getItem(key);
    if (!raw) return [];
    const parsed = JSON.parse(raw);
    return Array.isArray(parsed) ? (parsed as CaspianAssistantMessage[]) : [];
  } catch {
    return [];
  }
}

function countCitations(messages: CaspianAssistantMessage[]): number {
  return messages.reduce(
    (total, message) => total + (message.role === "assistant" ? message.citations.length : 0),
    0,
  );
}

function buildAssistantMessage(
  data: ChatResponse,
  existingMessages: CaspianAssistantMessage[],
): Extract<CaspianAssistantMessage, { role: "assistant" }> {
  const start = countCitations(existingMessages) + 1;
  const citations = data.citations.map((citation, index) => ({
    ...citation,
    id: `e_${start + index}`,
  }));
  return {
    id: messageId("a"),
    role: "assistant",
    content: data.answer,
    confidence: data.confidence,
    engine: data.engine,
    citations,
    followUps: data.follow_ups,
    trace: data.trace,
    createdAt: new Date().toISOString(),
  };
}

export function buildCaspianInspectorData(
  messages: CaspianAssistantMessage[],
  patientId: string | null,
  sessionId: string | null,
): CaspianInspectorData {
  const citations: Record<string, Citation> = {};
  const traceByCitationId: Record<string, TraceDetail | null> = {};
  let latestTrace: TraceDetail | null = null;
  let latestEngine = "—";

  for (const message of messages) {
    if (message.role !== "assistant") continue;
    latestTrace = message.trace;
    latestEngine = message.engine;
    for (const citation of message.citations) {
      citations[citation.id] = {
        id: citation.id,
        type: citation.source_type,
        title: citation.label,
        snippet: citation.detail,
        source: citation.resource_id,
        encounter: citation.event_date ? `Observed ${citation.event_date}` : "—",
        author: citation.source_type,
        date: citation.event_date ?? "—",
        related: message.citations
          .filter((candidate) => candidate.id !== citation.id)
          .slice(0, 3)
          .map((candidate) => ({
            id: candidate.id,
            text: candidate.label,
          })),
      };
      traceByCitationId[citation.id] = message.trace;
    }
  }

  return {
    citations,
    traceByCitationId,
    latestTrace,
    contextItems: [
      { label: "Patient", value: patientId ?? "No patient selected" },
      { label: "Session", value: sessionId ?? "—" },
      { label: "Messages", value: String(messages.length) },
      { label: "Latest engine", value: latestEngine },
    ],
  };
}

export function useCaspianAssistantSession(
  patientId: string | null,
  sessionId: string | null,
) {
  const key = useMemo(() => storageKey(patientId, sessionId), [patientId, sessionId]);
  const [messages, setMessages] = useState<CaspianAssistantMessage[]>(() => readMessages(key));

  useEffect(() => {
    setMessages(readMessages(key));
  }, [key]);

  useEffect(() => {
    if (!key) return;
    try {
      window.localStorage.setItem(key, JSON.stringify(messages));
    } catch {
      // Best-effort persistence only.
    }
  }, [key, messages]);

  const mutation = useMutation({
    mutationFn: async (payload: { question: string; history: ProviderAssistantTurn[] }) => {
      if (!patientId) {
        throw new Error("Select a patient before using Caspian.");
      }
      return api.chatProviderAssistant({
        patient_id: patientId,
        question: payload.question,
        history: payload.history,
        stance: "opinionated",
      });
    },
    onSuccess: (data) => {
      setMessages((current) => [...current, buildAssistantMessage(data, current)]);
    },
  });

  const submitQuestion = useCallback((question: string) => {
    const trimmed = question.trim();
    if (!trimmed || mutation.isPending || !patientId || !sessionId) return;

    const history: ProviderAssistantTurn[] = messages.map((message) => ({
      role: message.role,
      content: message.content,
    }));

    setMessages((current) => [
      ...current,
      {
        id: messageId("u"),
        role: "user",
        content: trimmed,
        createdAt: new Date().toISOString(),
      },
    ]);

    mutation.mutate({ question: trimmed, history });
  }, [messages, mutation, patientId, sessionId]);

  const resetConversation = useCallback(() => {
    setMessages([]);
    mutation.reset();
    if (!key) return;
    try {
      window.localStorage.removeItem(key);
    } catch {
      // noop
    }
  }, [key, mutation]);

  const inspector = useMemo(
    () => buildCaspianInspectorData(messages, patientId, sessionId),
    [messages, patientId, sessionId],
  );

  return {
    messages,
    isPending: mutation.isPending,
    isError: mutation.isError,
    error: mutation.error,
    submitQuestion,
    resetConversation,
    inspector,
  };
}

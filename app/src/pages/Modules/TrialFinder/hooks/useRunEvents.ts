import { useEffect, useRef, useState } from "react";
import type { TranscriptEvent } from "../../../../types/skills";

interface UseRunEventsArgs {
  skillName: string;
  runId: string;
  patientId: string;
  /**
   * Called every time a new event arrives — useful for invalidating
   * dependent React Query caches (e.g., refetch the workspace markdown
   * when a `workspace_write` or `cite` event lands so the rendered
   * artifact tracks live writes without a 2s polling cadence).
   */
  onEvent?: (event: TranscriptEvent) => void;
}

interface UseRunEventsResult {
  events: TranscriptEvent[];
  /** Connection state for the SSE feed. */
  connection: "connecting" | "open" | "closed" | "error";
  /** True after the server emits the `stream_closed` sentinel. */
  streamClosed: boolean;
}

/**
 * Subscribe to a run's SSE event stream.
 *
 * Replays the persisted transcript (sent by the server before live
 * events) and then continues with new events until the run terminates
 * and the server emits `stream_closed`. Reconnects automatically via
 * the browser's `EventSource` semantics.
 *
 * The hook holds the events in component state so the same array can
 * back the transcript pane without per-event re-fetching.
 */
export function useRunEvents({
  skillName,
  runId,
  patientId,
  onEvent,
}: UseRunEventsArgs): UseRunEventsResult {
  const [events, setEvents] = useState<TranscriptEvent[]>([]);
  const [connection, setConnection] =
    useState<UseRunEventsResult["connection"]>("connecting");
  const [streamClosed, setStreamClosed] = useState(false);
  // Track the latest onEvent in a ref so the EventSource lifecycle
  // doesn't depend on a re-renderable callback identity.
  const onEventRef = useRef(onEvent);
  useEffect(() => {
    onEventRef.current = onEvent;
  }, [onEvent]);

  useEffect(() => {
    setEvents([]);
    setStreamClosed(false);
    setConnection("connecting");

    const url =
      `/api/skills/${encodeURIComponent(skillName)}` +
      `/runs/${encodeURIComponent(runId)}/events` +
      `?patient_id=${encodeURIComponent(patientId)}`;

    const source = new EventSource(url);

    source.onopen = () => setConnection("open");

    source.onmessage = (raw) => {
      let parsed: TranscriptEvent;
      try {
        parsed = JSON.parse(raw.data) as TranscriptEvent;
      } catch {
        // Garbage line — ignore rather than poison the transcript.
        return;
      }
      if (parsed.kind === "stream_closed") {
        setStreamClosed(true);
        setConnection("closed");
        source.close();
        return;
      }
      setEvents((prev) => [...prev, parsed]);
      onEventRef.current?.(parsed);
    };

    source.onerror = () => {
      // EventSource will retry automatically on transient drops; we
      // surface the state so the UI can show a reconnect indicator
      // without forcing a hard refresh.
      setConnection("error");
    };

    return () => {
      source.close();
    };
  }, [skillName, runId, patientId]);

  return { events, connection, streamClosed };
}

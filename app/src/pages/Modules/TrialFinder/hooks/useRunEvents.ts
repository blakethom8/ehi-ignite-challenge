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
  const streamKey = `${skillName}:${runId}:${patientId}`;
  const [eventState, setEventState] = useState<{
    key: string;
    events: TranscriptEvent[];
  }>({ key: streamKey, events: [] });
  const [connectionState, setConnectionState] = useState<{
    key: string;
    connection: UseRunEventsResult["connection"];
    streamClosed: boolean;
  }>({ key: streamKey, connection: "connecting", streamClosed: false });
  const events = eventState.key === streamKey ? eventState.events : [];
  const connection =
    connectionState.key === streamKey ? connectionState.connection : "connecting";
  const streamClosed =
    connectionState.key === streamKey ? connectionState.streamClosed : false;
  // Track the latest onEvent in a ref so the EventSource lifecycle
  // doesn't depend on a re-renderable callback identity.
  const onEventRef = useRef(onEvent);
  useEffect(() => {
    onEventRef.current = onEvent;
  }, [onEvent]);

  useEffect(() => {
    const url =
      `/api/skills/${encodeURIComponent(skillName)}` +
      `/runs/${encodeURIComponent(runId)}/events` +
      `?patient_id=${encodeURIComponent(patientId)}`;

    const source = new EventSource(url);

    source.onopen = () =>
      setConnectionState({ key: streamKey, connection: "open", streamClosed: false });

    source.onmessage = (raw) => {
      let parsed: TranscriptEvent;
      try {
        parsed = JSON.parse(raw.data) as TranscriptEvent;
      } catch {
        // Garbage line — ignore rather than poison the transcript.
        return;
      }
      if (parsed.kind === "stream_closed") {
        setConnectionState({ key: streamKey, connection: "closed", streamClosed: true });
        source.close();
        return;
      }
      setEventState((prev) => ({
        key: streamKey,
        events: prev.key === streamKey ? [...prev.events, parsed] : [parsed],
      }));
      onEventRef.current?.(parsed);
    };

    source.onerror = () => {
      // EventSource will retry automatically on transient drops; we
      // surface the state so the UI can show a reconnect indicator
      // without forcing a hard refresh.
      setConnectionState({ key: streamKey, connection: "error", streamClosed: false });
    };

    return () => {
      source.close();
    };
  }, [skillName, runId, patientId, streamKey]);

  return { events, connection, streamClosed };
}

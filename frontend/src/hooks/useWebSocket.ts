import { useEffect, useRef, useState } from 'react';
import type { WsEvent } from '../types/draft';

type WsStatus = 'connecting' | 'open' | 'closed';

interface UseWebSocketResult {
  status: WsStatus;
  /** Ref to the accumulated event queue — drain with .splice(0) in a useEffect. */
  eventQueue: React.MutableRefObject<WsEvent[]>;
  /** Increments each time one or more events are pushed; use as useEffect dep. */
  eventTick: number;
}

export function useWebSocket(draftId: string | null): UseWebSocketResult {
  const [status, setStatus] = useState<WsStatus>('connecting');
  const [eventTick, setEventTick] = useState(0);
  const eventQueue = useRef<WsEvent[]>([]);
  const wsRef = useRef<WebSocket | null>(null);
  const reconnectTimeout = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    if (!draftId) return;

    let cancelled = false;

    const connect = () => {
      if (cancelled) return;

      const protocol = window.location.protocol === 'https:' ? 'wss' : 'ws';
      const host = window.location.host;
      const ws = new WebSocket(`${protocol}://${host}/ws/${draftId}`);
      wsRef.current = ws;
      setStatus('connecting');

      ws.onopen = () => {
        if (!cancelled) setStatus('open');
      };

      ws.onmessage = (event) => {
        try {
          const parsed: WsEvent = JSON.parse(event.data);
          if (parsed.type === 'ping') {
            ws.send(JSON.stringify({ type: 'pong' }));
          } else {
            // Push to queue and bump tick — React may batch multiple ticks, but
            // useDraft drains the entire queue array on each effect run, so no
            // event is lost even if several arrive in the same render cycle.
            eventQueue.current.push(parsed);
            setEventTick((t) => t + 1);
          }
        } catch {
          // ignore malformed messages
        }
      };

      ws.onclose = () => {
        if (!cancelled) {
          setStatus('closed');
          // Reconnect after 2 seconds
          reconnectTimeout.current = setTimeout(connect, 2000);
        }
      };

      ws.onerror = () => {
        ws.close();
      };
    };

    connect();

    return () => {
      cancelled = true;
      if (reconnectTimeout.current) clearTimeout(reconnectTimeout.current);
      wsRef.current?.close();
    };
  }, [draftId]);

  return { status, eventQueue, eventTick };
}

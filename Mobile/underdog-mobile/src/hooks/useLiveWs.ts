import { useCallback, useRef, useState } from 'react';
import { WS_MSG } from '../config';
import type { WsAlert, WsCaption } from '../config';

export type LogEntry =
  | { type: 'caption'; id: string; text: string; ts_ms: number }
  | { type: 'alert'; id: string; text: string; ts_ms: number; event_type: string; event_id?: number; keyword?: string };

type WsStatus = 'disconnected' | 'connecting' | 'connected';

export function useLiveWs(wsUrl: string) {
  const [status, setStatus] = useState<WsStatus>('disconnected');
  const [logs, setLogs] = useState<LogEntry[]>([]);
  const [latestAlert, setLatestAlert] = useState<LogEntry | null>(null);
  const [currentCaption, setCurrentCaption] = useState<string>('');
  const wsRef = useRef<WebSocket | null>(null);

  const disconnect = useCallback(() => {
    if (wsRef.current) {
      wsRef.current.close();
      wsRef.current = null;
    }
    setStatus('disconnected');
  }, []);

  const connect = useCallback(
    (sessionId: string) => {
      if (wsRef.current) {
        disconnect();
      }
      setStatus('connecting');
      const ws = new WebSocket(wsUrl);
      wsRef.current = ws;

      ws.onopen = () => {
        setStatus('connected');
        ws.send(JSON.stringify({ type: WS_MSG.JOIN, session_id: sessionId }));
      };

      ws.onclose = () => {
        wsRef.current = null;
        setStatus('disconnected');
      };

      ws.onerror = () => {
        // onclose will run after
      };

      ws.onmessage = (event) => {
        let msg: { type: string; [key: string]: unknown };
        try {
          msg = JSON.parse(event.data as string);
        } catch {
          return;
        }
        if (!msg.type) return;

        if (msg.type === WS_MSG.HELLO) {
          // 이미 join 보냄 (onopen에서)
          return;
        }

        if (msg.type === WS_MSG.JOIN_ACK) {
          // 세션 입장 완료
          return;
        }

        if (msg.type === WS_MSG.CAPTION) {
          const c = msg as unknown as WsCaption;
          const id = `c-${c.ts_ms}-${Math.random().toString(36).slice(2, 9)}`;
          const entry: LogEntry = { type: 'caption', id, text: c.text, ts_ms: c.ts_ms };
          setCurrentCaption(c.text);
          setLogs((prev) => [entry, ...prev].slice(0, 500));
          return;
        }

        if (msg.type === WS_MSG.ALERT) {
          const a = msg as unknown as WsAlert;
          const id = `a-${a.event_id ?? a.ts_ms}-${Math.random().toString(36).slice(2, 9)}`;
          const entry: LogEntry = {
            type: 'alert',
            id,
            text: a.text,
            ts_ms: a.ts_ms,
            event_type: a.event_type,
            event_id: a.event_id,
            keyword: a.keyword,
          };
          setLatestAlert(entry);
          setLogs((prev) => [entry, ...prev].slice(0, 500));
          return;
        }
      };
    },
    [wsUrl, disconnect]
  );

  const toggle = useCallback(
    (sessionId: string | null) => {
      if (status === 'disconnected' && sessionId) {
        connect(sessionId);
      } else {
        disconnect();
      }
    },
    [status, connect, disconnect]
  );

  const sendAudioChunk = useCallback(
    (sessionId: string, tsMs: number, dataB64: string) => {
      const ws = wsRef.current;
      if (!ws || ws.readyState !== WebSocket.OPEN) return false;
      ws.send(
        JSON.stringify({
          type: WS_MSG.AUDIO_CHUNK,
          session_id: sessionId,
          ts_ms: tsMs,
          sr: 16000,
          format: 'pcm_s16le',
          data_b64: dataB64,
        })
      );
      return true;
    },
    []
  );

  return {
    status,
    connected: status === 'connected',
    connecting: status === 'connecting',
    connect,
    disconnect,
    toggle,
    sendAudioChunk,
    logs,
    latestAlert,
    currentCaption,
  };
}

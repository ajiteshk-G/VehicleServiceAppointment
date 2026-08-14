import { useState, useEffect, useRef, useCallback } from 'react';

export function useLiveTelemetry() {
  const [isConnected, setIsConnected] = useState(false);
  const [callActive, setCallActive] = useState(false);
  const [callInfo, setCallInfo] = useState(null);
  const [transcripts, setTranscripts] = useState([]);
  const [toolEvents, setToolEvents] = useState([]);
  const [bargeInEvents, setBargeInEvents] = useState([]);
  const [audioEnergy, setAudioEnergy] = useState({ user: 0, ai: 0 });
  const [lastDmsUpdate, setLastDmsUpdate] = useState(Date.now());

  const wsRef = useRef(null);
  const reconnectTimeoutRef = useRef(null);

  const connect = useCallback(() => {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const host = window.location.host;
    const wsUrl = `${protocol}//${host}/ws/telemetry`;

    try {
      const ws = new WebSocket(wsUrl);
      wsRef.current = ws;

      ws.onopen = () => {
        setIsConnected(true);
        console.log('[Telemetry] WebSocket connected');
      };

      ws.onmessage = (event) => {
        try {
          const message = JSON.parse(event.data);
          const { type, data } = message;

          if (type === 'CALL_STARTED') {
            setCallActive(true);
            setCallInfo(data);
            setTranscripts([]);
            setToolEvents([]);
          } else if (type === 'CALL_ENDED') {
            setCallActive(false);
            setLastDmsUpdate(Date.now());
          } else if (type === 'TRANSCRIPT') {
            setTranscripts((prev) => [...prev, data.entry]);
          } else if (type === 'TOOL_EXECUTION') {
            setToolEvents((prev) => [data.event, ...prev]);
            setLastDmsUpdate(Date.now());
          } else if (type === 'BARGE_IN') {
            setBargeInEvents((prev) => [
              { ...data, id: Date.now(), time: new Date().toLocaleTimeString() },
              ...prev.slice(0, 9),
            ]);
          } else if (type === 'AUDIO_ENERGY') {
            if (data.source === 'USER') {
              setAudioEnergy((prev) => ({ ...prev, user: data.rms }));
            } else {
              setAudioEnergy((prev) => ({ ...prev, ai: data.rms }));
            }
          }
        } catch (err) {
          console.error('[Telemetry] Error parsing message:', err);
        }
      };

      ws.onclose = () => {
        setIsConnected(false);
        console.log('[Telemetry] WebSocket closed, retrying in 2s...');
        reconnectTimeoutRef.current = setTimeout(connect, 2000);
      };

      ws.onerror = (err) => {
        console.error('[Telemetry] WebSocket error:', err);
        ws.close();
      };
    } catch (err) {
      console.error('[Telemetry] Failed to initiate WebSocket:', err);
      reconnectTimeoutRef.current = setTimeout(connect, 2000);
    }
  }, []);

  useEffect(() => {
    connect();
    return () => {
      if (wsRef.current) wsRef.current.close();
      if (reconnectTimeoutRef.current) clearTimeout(reconnectTimeoutRef.current);
    };
  }, [connect]);

  const clearSession = () => {
    setTranscripts([]);
    setToolEvents([]);
    setBargeInEvents([]);
    setAudioEnergy({ user: 0, ai: 0 });
  };

  return {
    isConnected,
    callActive,
    callInfo,
    transcripts,
    toolEvents,
    bargeInEvents,
    audioEnergy,
    lastDmsUpdate,
    clearSession,
  };
}

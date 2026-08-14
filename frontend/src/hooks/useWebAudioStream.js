import { useState, useRef, useCallback } from 'react';

export function useWebAudioStream() {
  const [isStreaming, setIsStreaming] = useState(false);
  const [isMuted, setIsMuted] = useState(false);
  const [error, setError] = useState(null);

  const wsRef = useRef(null);
  const audioContextRef = useRef(null);
  const mediaStreamRef = useRef(null);
  const processorNodeRef = useRef(null);
  const isMutedRef = useRef(false);

  const startStream = useCallback(async (customerId = 'CUST-101') => {
    setError(null);
    try {
      // 1. Request microphone access
      const stream = await navigator.mediaDevices.getUserMedia({
        audio: {
          channelCount: 1,
          sampleRate: 16000,
          echoCancellation: true,
          noiseSuppression: true,
          autoGainControl: true,
        },
      });
      mediaStreamRef.current = stream;

      // 2. Open WebSocket to browser audio stream endpoint
      const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
      const host = window.location.host;
      const wsUrl = `${protocol}//${host}/ws/browser/stream?customer_id=${customerId}`;
      const ws = new WebSocket(wsUrl);
      wsRef.current = ws;
      ws.binaryType = 'arraybuffer';

      // 3. Setup AudioContext & ScriptProcessor / AudioWorklet
      const AudioCtx = window.AudioContext || window.webkitAudioContext;
      const audioCtx = new AudioCtx({ sampleRate: 16000 });
      audioContextRef.current = audioCtx;

      const source = audioCtx.createMediaStreamSource(stream);
      // ScriptProcessor with 512 buffer (~32ms chunks)
      const processor = audioCtx.createScriptProcessor(512, 1, 1);
      processorNodeRef.current = processor;

      processor.onaudioprocess = (e) => {
        if (ws.readyState === WebSocket.OPEN && !isMutedRef.current) {
          const inputData = e.inputBuffer.getChannelData(0);
          // Convert Float32 [-1.0, 1.0] to Int16 PCM [-32768, 32767]
          const pcm16 = new Int16Array(inputData.length);
          for (let i = 0; i < inputData.length; i++) {
            const s = Math.max(-1, Math.min(1, inputData[i]));
            pcm16[i] = s < 0 ? s * 0x8000 : s * 0x7fff;
          }
          ws.send(pcm16.buffer);
        }
      };

      source.connect(processor);
      processor.connect(audioCtx.destination);

      // 4. Handle incoming audio playback from server
      let nextPlayTime = 0;
      ws.onmessage = async (event) => {
        if (event.data instanceof ArrayBuffer) {
          // Received 24kHz PCM from server
          const pcm16Data = new Int16Array(event.data);
          const float32Data = new Float32Array(pcm16Data.length);
          for (let i = 0; i < pcm16Data.length; i++) {
            float32Data[i] = pcm16Data[i] / 32768.0;
          }

          if (audioCtx.state === 'suspended') {
            await audioCtx.resume();
          }

          const playbackBuffer = audioCtx.createBuffer(1, float32Data.length, 24000);
          playbackBuffer.copyToChannel(float32Data, 0);

          const bufferSource = audioCtx.createBufferSource();
          bufferSource.buffer = playbackBuffer;
          bufferSource.connect(audioCtx.destination);

          const currentTime = audioCtx.currentTime;
          // Prevent queue drift if lagging or interrupted
          if (nextPlayTime < currentTime || nextPlayTime > currentTime + 0.3) {
            nextPlayTime = currentTime;
          }
          bufferSource.start(nextPlayTime);
          nextPlayTime += playbackBuffer.duration;
        }
      };

      ws.onopen = () => {
        setIsStreaming(true);
      };

      ws.onclose = () => {
        stopStream();
      };

      ws.onerror = (err) => {
        console.error('[WebAudio] Stream socket error:', err);
        setError('WebSocket stream connection failed.');
        stopStream();
      };
    } catch (err) {
      console.error('[WebAudio] Error starting mic stream:', err);
      setError(err.message || 'Microphone access denied.');
      stopStream();
    }
  }, []);

  const stopStream = useCallback(() => {
    if (processorNodeRef.current) {
      try {
        processorNodeRef.current.disconnect();
      } catch (e) {}
      processorNodeRef.current = null;
    }
    if (audioContextRef.current) {
      try {
        audioContextRef.current.close();
      } catch (e) {}
      audioContextRef.current = null;
    }
    if (mediaStreamRef.current) {
      mediaStreamRef.current.getTracks().forEach((t) => t.stop());
      mediaStreamRef.current = null;
    }
    if (wsRef.current) {
      if (wsRef.current.readyState === WebSocket.OPEN) {
        wsRef.current.send('STOP');
      }
      wsRef.current.close();
      wsRef.current = null;
    }
    setIsStreaming(false);
  }, []);

  const toggleMute = useCallback(() => {
    isMutedRef.current = !isMutedRef.current;
    setIsMuted(isMutedRef.current);
  }, []);

  return {
    isStreaming,
    isMuted,
    error,
    startStream,
    stopStream,
    toggleMute,
  };
}

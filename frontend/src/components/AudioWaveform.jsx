import React, { useEffect, useRef } from 'react';
import { Activity, Mic, Volume2 } from 'lucide-react';

export default function AudioWaveform({ userEnergy = 0, aiEnergy = 0, isActive = false }) {
  const canvasRef = useRef(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    let animationId;
    let phase = 0;

    const render = () => {
      ctx.clearRect(0, 0, canvas.width, canvas.height);

      const width = canvas.width;
      const height = canvas.height;
      const centerY = height / 2;

      // Determine active amplitude
      const effectiveAiAmp = Math.min(1.0, aiEnergy / 2500) * (isActive ? 1 : 0);
      const effectiveUserAmp = Math.min(1.0, userEnergy / 2500) * (isActive ? 1 : 0);

      // AI Wave (Rose / Pink)
      ctx.beginPath();
      ctx.lineWidth = 2.5;
      ctx.strokeStyle = effectiveAiAmp > 0.05 ? '#f43f5e' : '#475569';
      for (let x = 0; x < width; x++) {
        const norm = (x / width) * Math.PI * 4;
        const amp = (effectiveAiAmp > 0.05 ? 18 : 2) * effectiveAiAmp + 2;
        const y = centerY + Math.sin(norm + phase) * amp * Math.sin((x / width) * Math.PI);
        if (x === 0) ctx.moveTo(x, y);
        else ctx.lineTo(x, y);
      }
      ctx.stroke();

      // User Wave (Cyan / Teal)
      ctx.beginPath();
      ctx.lineWidth = 2;
      ctx.strokeStyle = effectiveUserAmp > 0.05 ? '#06b6d4' : '#334155';
      for (let x = 0; x < width; x++) {
        const norm = (x / width) * Math.PI * 6;
        const amp = (effectiveUserAmp > 0.05 ? 16 : 2) * effectiveUserAmp + 2;
        const y = centerY + Math.cos(norm - phase * 1.2) * amp * Math.sin((x / width) * Math.PI);
        if (x === 0) ctx.moveTo(x, y);
        else ctx.lineTo(x, y);
      }
      ctx.stroke();

      phase += 0.08;
      animationId = requestAnimationFrame(render);
    };

    render();
    return () => cancelAnimationFrame(animationId);
  }, [userEnergy, aiEnergy, isActive]);

  return (
    <div className="glass-panel rounded-xl p-3 border border-slate-800 space-y-2">
      <div className="flex items-center justify-between text-xs">
        <div className="flex items-center gap-1.5 font-medium text-slate-300">
          <Activity className="w-3.5 h-3.5 text-rose-500 animate-pulse" />
          <span>Live Audio Waveform</span>
        </div>
        <div className="flex items-center gap-3 text-[11px] font-mono">
          <span className="flex items-center gap-1 text-cyan-400">
            <Mic className="w-3 h-3" /> User: {Math.round(userEnergy)} RMS
          </span>
          <span className="flex items-center gap-1 text-rose-400">
            <Volume2 className="w-3 h-3" /> AI: {Math.round(aiEnergy)} RMS
          </span>
        </div>
      </div>

      <canvas
        ref={canvasRef}
        width={380}
        height={56}
        className="w-full h-14 rounded-lg bg-slate-950/80 border border-slate-900"
      />
    </div>
  );
}

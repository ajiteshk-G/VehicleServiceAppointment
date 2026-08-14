import React, { useEffect, useRef } from 'react';
import { Bot, User, Zap, MessageSquare } from 'lucide-react';

export default function LiveTranscript({ transcripts = [], bargeInEvents = [], isCallActive }) {
  const endRef = useRef(null);

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [transcripts, bargeInEvents]);

  return (
    <div className="glass-panel rounded-xl p-3.5 border border-slate-800 flex flex-col flex-1 min-h-[320px] max-h-[440px]">
      <div className="flex items-center justify-between pb-2.5 border-b border-slate-800/80 mb-2.5">
        <div className="flex items-center gap-1.5 text-xs font-semibold text-slate-300 uppercase tracking-wider">
          <MessageSquare className="w-3.5 h-3.5 text-rose-500" />
          <span>Streaming Dialogue Transcript</span>
        </div>
        <div className="flex items-center gap-2">
          {isCallActive && (
            <span className="flex items-center gap-1 text-[10px] px-2 py-0.5 rounded-full bg-rose-950/80 text-rose-400 border border-rose-800 font-mono animate-pulse">
              <span className="w-1.5 h-1.5 rounded-full bg-rose-500 animate-ping" />
              Live Transcoding G.711u / 16kHz
            </span>
          )}
        </div>
      </div>

      {/* Barge-In Alert Banner if recent */}
      {bargeInEvents.length > 0 && (
        <div className="mb-2.5 space-y-1.5">
          {bargeInEvents.slice(0, 1).map((ev) => (
            <div
              key={ev.id}
              className="barge-in-badge flex items-center justify-between bg-amber-950/70 border border-amber-500/50 px-3 py-1.5 rounded-lg text-amber-300 text-xs font-medium"
            >
              <div className="flex items-center gap-1.5">
                <Zap className="w-3.5 h-3.5 text-amber-400 fill-amber-400" />
                <span>Barge-in Interruption Detected</span>
              </div>
              <span className="font-mono text-[10px] bg-amber-900/60 px-1.5 py-0.5 rounded text-amber-200">
                Twilio Clear Frame Emitted (&lt;40ms)
              </span>
            </div>
          ))}
        </div>
      )}

      {/* Messages Scroll Area */}
      <div className="flex-1 overflow-y-auto space-y-3 pr-1 text-sm">
        {transcripts.length === 0 ? (
          <div className="h-full flex flex-col items-center justify-center text-slate-500 text-xs text-center p-6 space-y-2">
            <Bot className="w-8 h-8 text-slate-700 stroke-1" />
            <p>Awaiting voice session initiation...</p>
            <p className="text-[11px] text-slate-600">
              Start an In-Browser Mic call or trigger a real PSTN Twilio dial to begin.
            </p>
          </div>
        ) : (
          transcripts.map((t, idx) => {
            const isAI = t.role === 'assistant' || t.role === 'model';
            return (
              <div
                key={idx}
                className={`flex gap-2.5 ${isAI ? 'justify-start' : 'justify-end'}`}
              >
                {isAI && (
                  <div className="w-7 h-7 rounded-full bg-rose-950 border border-rose-700/60 flex items-center justify-center flex-shrink-0 mt-0.5">
                    <Bot className="w-4 h-4 text-rose-400" />
                  </div>
                )}

                <div
                  className={`max-w-[82%] rounded-2xl px-3.5 py-2 text-xs leading-relaxed ${
                    isAI
                      ? 'bg-slate-900/90 text-slate-200 border border-slate-800 rounded-tl-sm'
                      : 'bg-rose-600 text-white rounded-tr-sm shadow-md shadow-rose-900/20'
                  }`}
                >
                  <div className="flex items-center justify-between gap-3 mb-1 text-[10px] opacity-70">
                    <span className="font-semibold">
                      {isAI ? 'Pooja (AI Concierge)' : 'Customer'}
                    </span>
                    <span className="font-mono">{t.time_str || ''}</span>
                  </div>
                  <p className="whitespace-pre-wrap">{t.text}</p>
                </div>

                {!isAI && (
                  <div className="w-7 h-7 rounded-full bg-slate-800 border border-slate-700 flex items-center justify-center flex-shrink-0 mt-0.5">
                    <User className="w-4 h-4 text-slate-300" />
                  </div>
                )}
              </div>
            );
          })
        )}
        <div ref={endRef} />
      </div>
    </div>
  );
}

import React, { useState } from 'react';
import { Cpu, ChevronDown, ChevronRight, CheckCircle2, Clock, Database, Terminal } from 'lucide-react';

export default function ToolExecutionFeed({ toolEvents = [] }) {
  const [expandedIndex, setExpandedIndex] = useState(0);

  const toggleExpand = (idx) => {
    setExpandedIndex(expandedIndex === idx ? -1 : idx);
  };

  return (
    <div className="glass-panel rounded-xl p-3.5 border border-slate-800 flex flex-col h-full overflow-hidden">
      <div className="flex items-center justify-between pb-2.5 border-b border-slate-800/80 mb-2.5">
        <div className="flex items-center gap-1.5 text-xs font-semibold text-slate-300 uppercase tracking-wider">
          <Cpu className="w-3.5 h-3.5 text-cyan-400" />
          <span>AI Reasoning & Domain Tool Feed</span>
        </div>
        <div className="flex items-center gap-1.5 font-mono text-[11px] text-slate-400">
          <Database className="w-3 h-3 text-cyan-500" />
          <span>{toolEvents.length} Calls Executed</span>
        </div>
      </div>

      <div className="flex-1 overflow-y-auto space-y-2.5 pr-1">
        {toolEvents.length === 0 ? (
          <div className="h-full flex flex-col items-center justify-center text-slate-500 text-xs text-center p-6 space-y-2">
            <Terminal className="w-8 h-8 text-slate-700 stroke-1" />
            <p>Awaiting Gemini Live tool execution...</p>
            <p className="text-[11px] text-slate-600">
              Tool calls for vehicle profile lookup, transparent pricing estimation, 180s slot locks, and bookings will appear here in real time.
            </p>
          </div>
        ) : (
          toolEvents.map((ev, idx) => {
            const isExpanded = expandedIndex === idx;
            const latency = ev.latency_ms || ev.result?._latency_ms || 25;
            const isSuccess = ev.result?.status === 'SUCCESS' || ev.result?.success === true;

            return (
              <div
                key={idx}
                className="bg-slate-900/90 border border-slate-800 rounded-xl overflow-hidden text-xs transition-all hover:border-slate-700"
              >
                <div
                  onClick={() => toggleExpand(idx)}
                  className="p-2.5 flex items-center justify-between cursor-pointer select-none bg-slate-900/40 hover:bg-slate-800/50"
                >
                  <div className="flex items-center gap-2">
                    {isExpanded ? (
                      <ChevronDown className="w-3.5 h-3.5 text-slate-400" />
                    ) : (
                      <ChevronRight className="w-3.5 h-3.5 text-slate-400" />
                    )}
                    <span className="font-mono font-semibold text-rose-400">
                      {ev.tool_name}()
                    </span>
                  </div>

                  <div className="flex items-center gap-2">
                    <span className="flex items-center gap-1 text-[10px] px-2 py-0.5 rounded bg-emerald-950/80 text-emerald-400 border border-emerald-800 font-mono">
                      <Clock className="w-2.5 h-2.5" /> {latency}ms DB
                    </span>
                    {isSuccess && (
                      <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400" />
                    )}
                  </div>
                </div>

                {isExpanded && (
                  <div className="p-3 border-t border-slate-800/80 bg-slate-950/70 space-y-2.5 font-mono text-[11px]">
                    <div>
                      <div className="text-slate-500 font-sans font-semibold mb-1 text-[10px] uppercase tracking-wider">
                        Input Arguments
                      </div>
                      <pre className="p-2 rounded bg-slate-900 border border-slate-800 text-slate-300 overflow-x-auto">
                        {JSON.stringify(ev.args, null, 2)}
                      </pre>
                    </div>

                    <div>
                      <div className="text-slate-500 font-sans font-semibold mb-1 text-[10px] uppercase tracking-wider">
                        Database Result Payload
                      </div>
                      <pre className="p-2 rounded bg-slate-900 border border-slate-800 text-emerald-300 overflow-x-auto">
                        {JSON.stringify(ev.result, null, 2)}
                      </pre>
                    </div>
                  </div>
                )}
              </div>
            );
          })
        )}
      </div>
    </div>
  );
}

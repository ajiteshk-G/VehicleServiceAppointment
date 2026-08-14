import React, { useEffect, useState } from 'react';
import { LayoutGrid, CheckCircle, Clock, AlertTriangle, PhoneCall, RefreshCw, Send } from 'lucide-react';

export default function DmsBayMonitor({ lastDmsUpdate, onTriggerDial }) {
  const [slots, setSlots] = useState([]);
  const [campaignQueue, setCampaignQueue] = useState([]);
  const [activeTab, setActiveTab] = useState('bays'); // 'bays' | 'campaign'
  const [loading, setLoading] = useState(false);
  const [simulatingBatch, setSimulatingBatch] = useState(false);

  const fetchDmsData = async () => {
    setLoading(true);
    try {
      const [slotsRes, queueRes] = await Promise.all([
        fetch('/api/slots?dealer_id=DLR-PUN-01'),
        fetch('/api/campaign/queue'),
      ]);
      const slotsData = await slotsRes.json();
      const queueData = await queueRes.json();
      setSlots(slotsData);
      setCampaignQueue(queueData);
    } catch (err) {
      console.error('Error fetching DMS data:', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchDmsData();
  }, [lastDmsUpdate]);

  // Periodic refresh for lock expiration countdowns
  useEffect(() => {
    const timer = setInterval(() => {
      setSlots((prev) => [...prev]);
    }, 1000);
    return () => clearInterval(timer);
  }, []);

  const handleSimulateBatch = () => {
    setSimulatingBatch(true);
    setTimeout(() => {
      setSimulatingBatch(false);
      alert('Simulated outbound batch campaign triggered for 5 due vehicles via Twilio Voice API!');
    }, 1200);
  };

  return (
    <div className="glass-panel rounded-xl p-3.5 border border-slate-800 flex flex-col h-full overflow-hidden">
      {/* Header & Tabs */}
      <div className="flex items-center justify-between pb-2.5 border-b border-slate-800/80 mb-3">
        <div className="flex items-center gap-1.5 text-xs font-semibold text-slate-300 uppercase tracking-wider">
          <LayoutGrid className="w-3.5 h-3.5 text-rose-500" />
          <span>DMS Workshop Bay & Campaign Hub</span>
        </div>

        <div className="flex items-center gap-1.5">
          <button
            onClick={() => setActiveTab('bays')}
            className={`px-2.5 py-1 rounded-md text-xs font-medium transition-colors ${
              activeTab === 'bays'
                ? 'bg-rose-600 text-white'
                : 'bg-slate-900 text-slate-400 hover:text-slate-200'
            }`}
          >
            Bay Grid (6 Bays)
          </button>
          <button
            onClick={() => setActiveTab('campaign')}
            className={`px-2.5 py-1 rounded-md text-xs font-medium transition-colors ${
              activeTab === 'campaign'
                ? 'bg-rose-600 text-white'
                : 'bg-slate-900 text-slate-400 hover:text-slate-200'
            }`}
          >
            Campaign Queue ({campaignQueue.length})
          </button>
          <button
            onClick={fetchDmsData}
            title="Refresh DMS Data"
            className="p-1 rounded bg-slate-900 text-slate-400 hover:text-slate-200"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${loading ? 'animate-spin' : ''}`} />
          </button>
        </div>
      </div>

      {/* Main Tab Content */}
      <div className="flex-1 overflow-y-auto pr-1">
        {activeTab === 'bays' ? (
          <div className="space-y-3">
            <div className="flex items-center justify-between text-[11px] text-slate-400">
              <span>Mahindra Sahyadri Auto Pune (Live Slots)</span>
              <div className="flex items-center gap-2">
                <span className="flex items-center gap-1">
                  <span className="w-2 h-2 rounded-full bg-emerald-500" /> Open
                </span>
                <span className="flex items-center gap-1">
                  <span className="w-2 h-2 rounded-full bg-amber-500 animate-pulse" /> 180s Hold
                </span>
                <span className="flex items-center gap-1">
                  <span className="w-2 h-2 rounded-full bg-rose-500" /> Booked
                </span>
              </div>
            </div>

            <div className="grid grid-cols-3 gap-2 text-xs">
              {slots.slice(0, 12).map((slot) => {
                const isBooked = slot.is_booked;
                const isLocked = slot.is_locked;
                const slotTimeFormatted = slot.slot_time
                  ? new Date(slot.slot_time).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
                  : '10:00 AM';

                let remainingSeconds = 0;
                if (isLocked && slot.locked_until) {
                  remainingSeconds = Math.max(0, Math.round((new Date(slot.locked_until) - new Date()) / 1000));
                }

                return (
                  <div
                    key={slot.slot_id}
                    className={`p-2.5 rounded-lg border flex flex-col justify-between h-20 transition-all ${
                      isBooked
                        ? 'bg-rose-950/40 border-rose-800/80 text-rose-300'
                        : isLocked && remainingSeconds > 0
                        ? 'bg-amber-950/50 border-amber-500/80 text-amber-200 slot-locked-pulse'
                        : 'bg-emerald-950/30 border-emerald-800/60 text-emerald-300 hover:border-emerald-700'
                    }`}
                  >
                    <div className="flex items-center justify-between font-mono text-[10px]">
                      <span className="font-semibold">BAY #{slot.bay_number}</span>
                      <span>{slotTimeFormatted}</span>
                    </div>

                    <div className="text-[11px] font-medium">
                      {isBooked ? (
                        <div className="flex items-center gap-1 text-rose-400">
                          <CheckCircle className="w-3 h-3" /> Booked
                        </div>
                      ) : isLocked && remainingSeconds > 0 ? (
                        <div className="flex items-center gap-1 text-amber-300 font-mono text-[10px]">
                          <Clock className="w-3 h-3 text-amber-400 animate-spin" /> Held ({remainingSeconds}s)
                        </div>
                      ) : (
                        <div className="text-emerald-400 text-[10px]">Available</div>
                      )}
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        ) : (
          <div className="space-y-2.5">
            <div className="flex items-center justify-between">
              <span className="text-xs text-slate-400 font-medium">Due Periodic Service Triggers</span>
              <button
                onClick={handleSimulateBatch}
                disabled={simulatingBatch}
                className="flex items-center gap-1 px-2.5 py-1 rounded bg-rose-600 hover:bg-rose-500 text-white text-xs font-semibold disabled:opacity-50"
              >
                <Send className="w-3 h-3" /> {simulatingBatch ? 'Dispatching...' : 'Batch Dial Queue'}
              </button>
            </div>

            <div className="space-y-2">
              {campaignQueue.map((item, idx) => (
                <div
                  key={idx}
                  className="bg-slate-900/80 border border-slate-800 rounded-lg p-2.5 flex items-center justify-between text-xs"
                >
                  <div className="space-y-0.5">
                    <div className="font-semibold text-slate-200">
                      {item.full_name} &bull; {item.model_name}
                    </div>
                    <div className="text-[11px] text-rose-400 font-mono">
                      {item.service_due_type} ({item.current_odometer_km?.toLocaleString()} km)
                    </div>
                  </div>

                  <button
                    onClick={() => onTriggerDial(item)}
                    className="flex items-center gap-1 px-2.5 py-1 rounded bg-slate-800 hover:bg-rose-600 text-slate-200 hover:text-white transition-colors text-xs font-medium"
                  >
                    <PhoneCall className="w-3 h-3" /> Dial
                  </button>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

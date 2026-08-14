import React, { useState } from 'react';
import {
  Phone,
  PhoneCall,
  PhoneOff,
  Mic,
  MicOff,
  Radio,
  Sparkles,
  Shield,
  Layers,
  Activity,
  Car,
  Trash2
} from 'lucide-react';

import CustomerSelector from './components/CustomerSelector';
import AudioWaveform from './components/AudioWaveform';
import LiveTranscript from './components/LiveTranscript';
import ToolExecutionFeed from './components/ToolExecutionFeed';
import DmsBayMonitor from './components/DmsBayMonitor';
import OutboundDialerModal from './components/OutboundDialerModal';

import { useLiveTelemetry } from './hooks/useLiveTelemetry';
import { useWebAudioStream } from './hooks/useWebAudioStream';

export default function App() {
  const [selectedCustomer, setSelectedCustomer] = useState(null);
  const [dialerOpen, setDialerOpen] = useState(false);
  const [activeChannel, setActiveChannel] = useState('WEBRTC_BROWSER'); // 'TWILIO_PSTN' | 'WEBRTC_BROWSER'

  const {
    isConnected,
    callActive: telemetryCallActive,
    callInfo,
    transcripts,
    toolEvents,
    bargeInEvents,
    audioEnergy,
    lastDmsUpdate,
    clearSession,
  } = useLiveTelemetry();

  const {
    isStreaming: isBrowserStreaming,
    isMuted,
    startStream: startBrowserStream,
    stopStream: stopBrowserStream,
    toggleMute,
  } = useWebAudioStream();

  const isCallActive = telemetryCallActive || isBrowserStreaming;

  const handleStartBrowserCall = () => {
    setActiveChannel('WEBRTC_BROWSER');
    startBrowserStream(selectedCustomer?.customer_id || 'CUST-101');
  };

  const handleEndCall = () => {
    if (isBrowserStreaming) {
      stopBrowserStream();
    }
  };

  const handleTriggerCampaignDial = (item) => {
    setSelectedCustomer({
      customer_id: item.customer_id,
      full_name: item.full_name,
      phone_number: item.phone_number,
      vehicle: {
        model_name: item.model_name,
        registration_number: item.registration_number,
        vin: item.vin,
        current_odometer_km: item.current_odometer_km,
        service_due_type: item.service_due_type,
      },
    });
    setDialerOpen(true);
  };

  return (
    <div className="flex flex-col h-screen bg-slate-950 text-slate-100 selection:bg-rose-500 selection:text-white">
      {/* Top Navigation Bar */}
      <header className="h-16 border-b border-slate-800/80 bg-slate-950/90 backdrop-blur-md px-5 flex items-center justify-between z-10 flex-shrink-0">
        <div className="flex items-center gap-3">
          <div className="w-9 h-9 rounded-xl bg-gradient-to-tr from-rose-700 to-rose-500 flex items-center justify-center shadow-lg shadow-rose-900/30">
            <Car className="w-5 h-5 text-white" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h1 className="font-bold text-sm tracking-tight text-white">
                Mahindra & Swaraj AI Voice Concierge
              </h1>
              <span className="text-[10px] px-2 py-0.5 rounded-full bg-rose-950 text-rose-300 border border-rose-800 font-mono font-medium">
                Gemini 2.5 Live + Twilio PSTN
              </span>
            </div>
            <p className="text-[11px] text-slate-400">
              Real-time Indic Automotive Voice Service Reminder & Workshop Bay Concierge
            </p>
          </div>
        </div>

        {/* Global Controls & Status */}
        <div className="flex items-center gap-3">
          {/* Telemetry Status Indicator */}
          <div className="flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-slate-900 border border-slate-800 text-xs font-mono">
            <span
              className={`w-2 h-2 rounded-full ${
                isConnected ? 'bg-emerald-400 animate-pulse' : 'bg-amber-400'
              }`}
            />
            <span className="text-[11px] text-slate-300">
              {isConnected ? 'Telemetry Gateway Active' : 'Connecting Gateway...'}
            </span>
          </div>

          {/* Clear Session */}
          <button
            onClick={clearSession}
            title="Clear Call History"
            className="p-2 rounded-lg bg-slate-900 hover:bg-slate-800 text-slate-400 hover:text-slate-200 border border-slate-800"
          >
            <Trash2 className="w-4 h-4" />
          </button>

          {/* Twilio PSTN Dial Modal Trigger */}
          <button
            onClick={() => {
              setActiveChannel('TWILIO_PSTN');
              setDialerOpen(true);
            }}
            className="flex items-center gap-1.5 px-3.5 py-2 rounded-lg bg-slate-900 hover:bg-slate-800 border border-slate-700 text-slate-200 text-xs font-semibold transition-all shadow-sm"
          >
            <PhoneCall className="w-3.5 h-3.5 text-rose-400" />
            <span>PSTN Twilio Dial</span>
          </button>

          {/* Browser Mic Call Trigger */}
          {!isCallActive ? (
            <button
              onClick={handleStartBrowserCall}
              className="flex items-center gap-1.5 px-4 py-2 rounded-lg bg-rose-600 hover:bg-rose-500 text-white text-xs font-semibold transition-all shadow-lg shadow-rose-900/30"
            >
              <Mic className="w-3.5 h-3.5" />
              <span>Start In-Browser Call (Mic)</span>
            </button>
          ) : (
            <div className="flex items-center gap-2">
              <button
                onClick={toggleMute}
                className={`p-2 rounded-lg text-xs font-semibold border ${
                  isMuted
                    ? 'bg-amber-950 border-amber-700 text-amber-300'
                    : 'bg-slate-900 border-slate-700 text-slate-300'
                }`}
              >
                {isMuted ? <MicOff className="w-4 h-4" /> : <Mic className="w-4 h-4" />}
              </button>
              <button
                onClick={handleEndCall}
                className="flex items-center gap-1.5 px-4 py-2 rounded-lg bg-red-600 hover:bg-red-500 text-white text-xs font-semibold transition-all shadow-lg shadow-red-900/30"
              >
                <PhoneOff className="w-3.5 h-3.5" />
                <span>End Voice Call</span>
              </button>
            </div>
          )}
        </div>
      </header>

      {/* Main 3-Column Executive Split Screen */}
      <main className="flex-1 grid grid-cols-12 gap-4 p-4 overflow-hidden">
        {/* Left Column (4 cols): Profile, Audio Waveform & Streaming Transcript */}
        <section className="col-span-4 flex flex-col gap-3.5 h-full overflow-hidden">
          <CustomerSelector
            selectedCustomer={selectedCustomer}
            onSelectCustomer={setSelectedCustomer}
            disabled={isCallActive}
          />
          <AudioWaveform
            userEnergy={audioEnergy.user}
            aiEnergy={audioEnergy.ai}
            isActive={isCallActive}
          />
          <LiveTranscript
            transcripts={transcripts}
            bargeInEvents={bargeInEvents}
            isCallActive={isCallActive}
          />
        </section>

        {/* Middle Column (4 cols): AI Reasoning & Tool Execution Feed */}
        <section className="col-span-4 flex flex-col h-full overflow-hidden">
          <ToolExecutionFeed toolEvents={toolEvents} />
        </section>

        {/* Right Column (4 cols): Live DMS Workshop Bay Monitor & Campaign Hub */}
        <section className="col-span-4 flex flex-col h-full overflow-hidden">
          <DmsBayMonitor
            lastDmsUpdate={lastDmsUpdate}
            onTriggerDial={handleTriggerCampaignDial}
          />
        </section>
      </main>

      {/* Outbound PSTN Dialer Modal */}
      <OutboundDialerModal
        isOpen={dialerOpen}
        onClose={() => setDialerOpen(false)}
        selectedCustomer={selectedCustomer}
      />
    </div>
  );
}

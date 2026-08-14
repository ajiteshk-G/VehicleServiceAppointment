import React, { useState } from 'react';
import { Phone, PhoneOutgoing, X, CheckCircle, AlertCircle, Shield } from 'lucide-react';

export default function OutboundDialerModal({ isOpen, onClose, selectedCustomer, onCallInitiated }) {
  const [phoneNumber, setPhoneNumber] = useState(selectedCustomer?.phone_number || '+919820198201');
  const [callerId, setCallerId] = useState('+13369154920');
  const [loading, setLoading] = useState(false);
  const [statusMsg, setStatusMsg] = useState(null);

  if (!isOpen) return null;

  const handleOriginateCall = async (e) => {
    e.preventDefault();
    setLoading(true);
    setStatusMsg(null);

    try {
      const res = await fetch('/api/telephony/originate-call', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          customer_id: selectedCustomer?.customer_id || 'CUST-101',
          phone_number: phoneNumber,
          caller_id: callerId,
        }),
      });
      const data = await res.json();

      if (data.success) {
        setStatusMsg({ type: 'success', text: `Call originated successfully! Call SID: ${data.call_sid}` });
        if (onCallInitiated) onCallInitiated(data);
        setTimeout(() => {
          onClose();
        }, 2000);
      } else {
        setStatusMsg({ type: 'error', text: data.error || 'Failed to originate Twilio call.' });
      }
    } catch (err) {
      setStatusMsg({ type: 'error', text: err.message || 'Network error originating call.' });
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-sm p-4">
      <div className="bg-slate-900 border border-slate-700 rounded-2xl max-w-md w-full p-5 shadow-2xl space-y-4">
        <div className="flex items-center justify-between pb-3 border-b border-slate-800">
          <div className="flex items-center gap-2">
            <div className="w-8 h-8 rounded-full bg-rose-950 border border-rose-700 flex items-center justify-center">
              <PhoneOutgoing className="w-4 h-4 text-rose-400" />
            </div>
            <div>
              <h3 className="font-semibold text-slate-100 text-sm">Originate Real PSTN Twilio Call</h3>
              <p className="text-[11px] text-slate-400">Outbound voice call via Twilio Media Streams</p>
            </div>
          </div>
          <button onClick={onClose} className="p-1 rounded-lg text-slate-400 hover:text-slate-200">
            <X className="w-5 h-5" />
          </button>
        </div>

        <form onSubmit={handleOriginateCall} className="space-y-3.5 text-xs">
          <div>
            <label className="block text-slate-400 font-medium mb-1">Target Recipient Mobile Number</label>
            <input
              type="text"
              value={phoneNumber}
              onChange={(e) => setPhoneNumber(e.target.value)}
              placeholder="+9198XXXXXXXX"
              className="w-full bg-slate-950 border border-slate-700 rounded-lg px-3 py-2 text-slate-100 font-mono text-sm focus:ring-2 focus:ring-rose-500 focus:outline-none"
              required
            />
          </div>

          <div>
            <label className="block text-slate-400 font-medium mb-1">Twilio Caller ID (From Phone)</label>
            <input
              type="text"
              value={callerId}
              onChange={(e) => setCallerId(e.target.value)}
              className="w-full bg-slate-950 border border-slate-700 rounded-lg px-3 py-2 text-slate-100 font-mono text-xs focus:ring-2 focus:ring-rose-500 focus:outline-none"
            />
          </div>

          {selectedCustomer && (
            <div className="bg-slate-950/70 p-3 rounded-lg border border-slate-800 space-y-1">
              <div className="text-slate-300 font-semibold">{selectedCustomer.full_name}</div>
              <div className="text-rose-400 font-mono text-[11px]">
                {selectedCustomer.vehicle?.model_name} &bull; {selectedCustomer.vehicle?.service_due_type}
              </div>
            </div>
          )}

          {statusMsg && (
            <div
              className={`p-2.5 rounded-lg flex items-center gap-2 text-xs ${
                statusMsg.type === 'success'
                  ? 'bg-emerald-950/80 border border-emerald-700 text-emerald-300'
                  : 'bg-rose-950/80 border border-rose-700 text-rose-300'
              }`}
            >
              {statusMsg.type === 'success' ? <CheckCircle className="w-4 h-4" /> : <AlertCircle className="w-4 h-4" />}
              <span>{statusMsg.text}</span>
            </div>
          )}

          <div className="flex items-center justify-end gap-2 pt-2">
            <button
              type="button"
              onClick={onClose}
              className="px-3 py-2 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300 font-medium"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={loading}
              className="flex items-center gap-1.5 px-4 py-2 rounded-lg bg-rose-600 hover:bg-rose-500 text-white font-semibold shadow-lg shadow-rose-900/30 disabled:opacity-50"
            >
              <Phone className="w-3.5 h-3.5" />
              <span>{loading ? 'Origination in Progress...' : 'Originate Outbound Call'}</span>
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

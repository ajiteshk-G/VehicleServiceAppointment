import React, { useEffect, useState } from 'react';
import { User, Car, Wrench, ShieldCheck, MapPin, Gauge } from 'lucide-react';

export default function CustomerSelector({ selectedCustomer, onSelectCustomer, disabled }) {
  const [customers, setCustomers] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetch('/api/customers')
      .then((res) => res.json())
      .then((data) => {
        setCustomers(data);
        if (data.length > 0 && !selectedCustomer) {
          onSelectCustomer(data[0]);
        }
        setLoading(false);
      })
      .catch((err) => {
        console.error('Failed to fetch customers:', err);
        setLoading(false);
      });
  }, []);

  const handleChange = (e) => {
    const custId = e.target.value;
    const found = customers.find((c) => c.customer_id === custId);
    if (found) {
      onSelectCustomer(found);
    }
  };

  if (loading) {
    return (
      <div className="animate-pulse bg-slate-900 border border-slate-800 rounded-xl p-3 text-xs text-slate-400">
        Loading customer records from PostgreSQL / SQLite database...
      </div>
    );
  }

  const currentVehicle = selectedCustomer?.vehicle || {};
  const currentDealer = selectedCustomer?.dealership || {};

  return (
    <div className="glass-panel rounded-xl p-3.5 border border-slate-800 space-y-2.5">
      <div className="flex items-center justify-between">
        <label className="text-xs font-semibold text-slate-400 uppercase tracking-wider flex items-center gap-1.5">
          <User className="w-3.5 h-3.5 text-rose-500" /> Dynamic Customer Database Profile
        </label>
        <span className="text-[10px] px-2 py-0.5 rounded-full bg-emerald-950 text-emerald-400 border border-emerald-800 font-mono">
          100% DB-Driven
        </span>
      </div>

      <select
        value={selectedCustomer?.customer_id || ''}
        onChange={handleChange}
        disabled={disabled}
        className="w-full bg-slate-900 border border-slate-700 text-slate-100 text-sm rounded-lg px-3 py-2 font-medium focus:ring-2 focus:ring-rose-500 focus:outline-none disabled:opacity-50 cursor-pointer"
      >
        {customers.map((c) => (
          <option key={c.customer_id} value={c.customer_id}>
            {c.full_name} — {c.vehicle?.model_name} ({c.city})
          </option>
        ))}
      </select>

      {selectedCustomer && (
        <div className="grid grid-cols-2 gap-2 text-xs bg-slate-950/60 p-2.5 rounded-lg border border-slate-800/80">
          <div className="space-y-1">
            <div className="flex items-center gap-1 text-slate-400">
              <Car className="w-3 h-3 text-rose-400" />
              <span className="text-slate-200 font-semibold">{currentVehicle.model_name}</span>
            </div>
            <div className="font-mono text-[11px] text-slate-400">
              {currentVehicle.registration_number} &bull; {currentVehicle.vin?.slice(-8)}
            </div>
            <div className="flex items-center gap-1 text-amber-400 text-[11px]">
              <Gauge className="w-3 h-3" />
              <span>{currentVehicle.current_odometer_km?.toLocaleString()} km</span>
            </div>
          </div>

          <div className="space-y-1 border-l border-slate-800 pl-2.5">
            <div className="flex items-center gap-1 text-rose-400 font-medium text-[11px]">
              <Wrench className="w-3 h-3" />
              <span className="truncate">{currentVehicle.service_due_type}</span>
            </div>
            <div className="flex items-center gap-1 text-slate-400 text-[11px] truncate">
              <MapPin className="w-3 h-3 text-slate-500" />
              <span className="truncate">{currentDealer.name || 'Sahyadri Pune'}</span>
            </div>
            <div className="flex items-center gap-1 text-slate-400 text-[11px]">
              <ShieldCheck className="w-3 h-3 text-emerald-400" />
              <span>{selectedCustomer.phone_number}</span>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

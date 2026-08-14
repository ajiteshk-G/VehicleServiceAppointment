"""SQLAlchemy ORM Models for Database Entities."""

import json
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
try:
    from sqlalchemy import (
        Boolean,
        Column,
        Date,
        DateTime,
        ForeignKey,
        Integer,
        Numeric,
        String,
        Text,
        func
    )
    from sqlalchemy.orm import relationship
    from backend.app.database import Base
except ImportError:
    class _FallbackBase:
        def __init__(self, **kwargs):
            for k, v in kwargs.items():
                setattr(self, k, v)

    Base = _FallbackBase  # type: ignore

    class _DummyCol:
        def __init__(self, *args, **kwargs):
            pass
        def __call__(self, *args, **kwargs):
            return self
        def __getattr__(self, name):
            return self

    _dummy = _DummyCol()
    Boolean = Column = Date = DateTime = ForeignKey = Integer = Numeric = String = Text = func = relationship = _dummy


class Dealership(Base):
    __tablename__ = "dealerships"

    dealer_id = Column(String(50), primary_key=True)
    name = Column(String(150), nullable=False)
    city = Column(String(100), nullable=False)
    state = Column(String(100), nullable=False)
    address = Column(Text, nullable=False)
    phone_number = Column(String(20), nullable=False)
    maps_url = Column(Text, nullable=True)
    service_advisor_phone = Column(String(20), nullable=True)
    total_service_bays = Column(Integer, default=6)

    # Relationships
    vehicles = relationship("Vehicle", back_populates="dealer")
    slots = relationship("ServiceSlot", back_populates="dealer")
    bookings = relationship("ServiceBooking", back_populates="dealer")

    def to_dict(self) -> Dict[str, Any]:
        return {
            "dealer_id": self.dealer_id,
            "name": self.name,
            "city": self.city,
            "state": self.state,
            "address": self.address,
            "phone_number": self.phone_number,
            "maps_url": self.maps_url,
            "service_advisor_phone": self.service_advisor_phone,
            "total_service_bays": self.total_service_bays,
        }


class Customer(Base):
    __tablename__ = "customers"

    customer_id = Column(String(50), primary_key=True)
    full_name = Column(String(150), nullable=False)
    phone_number = Column(String(20), nullable=False)
    email = Column(String(100), nullable=True)
    preferred_language = Column(String(20), default="hinglish")
    city = Column(String(100), nullable=True)
    consent_dnd_scrubbed = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    vehicles = relationship("Vehicle", back_populates="customer")
    bookings = relationship("ServiceBooking", back_populates="customer")
    call_logs = relationship("CallLog", back_populates="customer")

    def to_dict(self) -> Dict[str, Any]:
        return {
            "customer_id": self.customer_id,
            "full_name": self.full_name,
            "phone_number": self.phone_number,
            "email": self.email,
            "preferred_language": self.preferred_language,
            "city": self.city,
            "consent_dnd_scrubbed": self.consent_dnd_scrubbed,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class Vehicle(Base):
    __tablename__ = "vehicles"

    vin = Column(String(50), primary_key=True)
    customer_id = Column(String(50), ForeignKey("customers.customer_id"), nullable=False)
    registration_number = Column(String(30), nullable=False)
    model_name = Column(String(100), nullable=False)
    fuel_type = Column(String(30), default="Diesel")
    purchase_date = Column(Date, nullable=False)
    current_odometer_km = Column(Integer, nullable=False)
    last_service_date = Column(Date, nullable=False)
    last_service_mileage_km = Column(Integer, nullable=False)
    service_interval_months = Column(Integer, default=6)
    service_interval_km = Column(Integer, default=10000)
    service_due_type = Column(String(50), default="PERIODIC_MAINTENANCE")
    assigned_dealer_id = Column(String(50), ForeignKey("dealerships.dealer_id"), nullable=True)

    # Relationships
    customer = relationship("Customer", back_populates="vehicles")
    dealer = relationship("Dealership", back_populates="vehicles")
    bookings = relationship("ServiceBooking", back_populates="vehicle")

    def to_dict(self) -> Dict[str, Any]:
        return {
            "vin": self.vin,
            "customer_id": self.customer_id,
            "registration_number": self.registration_number,
            "model_name": self.model_name,
            "fuel_type": self.fuel_type,
            "purchase_date": self.purchase_date.isoformat() if self.purchase_date else None,
            "current_odometer_km": self.current_odometer_km,
            "last_service_date": self.last_service_date.isoformat() if self.last_service_date else None,
            "last_service_mileage_km": self.last_service_mileage_km,
            "service_interval_months": self.service_interval_months,
            "service_interval_km": self.service_interval_km,
            "service_due_type": self.service_due_type,
            "assigned_dealer_id": self.assigned_dealer_id,
        }


class ServiceCostCatalog(Base):
    __tablename__ = "service_cost_catalog"

    catalog_id = Column(Integer, primary_key=True, autoincrement=True)
    model_name = Column(String(100), nullable=False)
    service_type = Column(String(50), nullable=False)
    mileage_interval_km = Column(Integer, nullable=False)
    estimated_parts_cost = Column(Numeric(10, 2), nullable=False)
    estimated_labor_cost = Column(Numeric(10, 2), nullable=False)
    engine_oil_cost = Column(Numeric(10, 2), nullable=False)
    tax_percentage = Column(Numeric(4, 2), default=18.00)
    total_estimated_cost = Column(Numeric(10, 2), nullable=False)
    included_checklist = Column(Text, nullable=True)  # JSON string

    def get_checklist(self) -> List[str]:
        if not self.included_checklist:
            return []
        if isinstance(self.included_checklist, list):
            return self.included_checklist
        try:
            res = json.loads(self.included_checklist)
            if isinstance(res, list):
                return res
        except Exception:
            pass
        return [item.strip() for item in str(self.included_checklist).split(",") if item.strip()]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "catalog_id": self.catalog_id,
            "model_name": self.model_name,
            "service_type": self.service_type,
            "mileage_interval_km": self.mileage_interval_km,
            "estimated_parts_cost": float(self.estimated_parts_cost),
            "estimated_labor_cost": float(self.estimated_labor_cost),
            "engine_oil_cost": float(self.engine_oil_cost),
            "tax_percentage": float(self.tax_percentage),
            "total_estimated_cost": float(self.total_estimated_cost),
            "included_checklist": self.get_checklist(),
        }


class ServiceSlot(Base):
    __tablename__ = "service_slots"

    slot_id = Column(Integer, primary_key=True, autoincrement=True)
    dealer_id = Column(String(50), ForeignKey("dealerships.dealer_id"), nullable=False)
    slot_time = Column(DateTime(timezone=True), nullable=False)
    bay_number = Column(Integer, nullable=False)
    is_booked = Column(Boolean, default=False)
    locked_by_customer_id = Column(String(50), nullable=True)
    locked_until = Column(DateTime(timezone=True), nullable=True)

    # Relationships
    dealer = relationship("Dealership", back_populates="slots")

    def is_locked(self) -> bool:
        if not self.locked_until:
            return False
        now = datetime.now(timezone.utc)
        lock_dt = self.locked_until
        if isinstance(lock_dt, str):
            try:
                lock_dt = datetime.fromisoformat(lock_dt.replace("Z", "+00:00"))
            except Exception:
                return False
        if lock_dt.tzinfo is None:
            return lock_dt > now.replace(tzinfo=None)
        return lock_dt > now

    def is_available_for(self, customer_id: Optional[str] = None) -> bool:
        if self.is_booked:
            return False
        if not self.is_locked():
            return True
        return self.locked_by_customer_id == customer_id

    def to_dict(self) -> Dict[str, Any]:
        slot_time_str = self.slot_time.isoformat() if hasattr(self.slot_time, "isoformat") else (str(self.slot_time) if self.slot_time else None)
        locked_until_str = self.locked_until.isoformat() if hasattr(self.locked_until, "isoformat") else (str(self.locked_until) if self.locked_until else None)
        return {
            "slot_id": self.slot_id,
            "dealer_id": self.dealer_id,
            "slot_time": slot_time_str,
            "bay_number": self.bay_number,
            "is_booked": bool(self.is_booked),
            "is_locked": self.is_locked(),
            "locked_by_customer_id": self.locked_by_customer_id,
            "locked_until": locked_until_str,
        }


class ServiceBooking(Base):
    __tablename__ = "service_bookings"

    booking_id = Column(Integer, primary_key=True, autoincrement=True)
    booking_reference = Column(String(50), unique=True, nullable=False)
    customer_id = Column(String(50), ForeignKey("customers.customer_id"), nullable=False)
    vin = Column(String(50), ForeignKey("vehicles.vin"), nullable=False)
    dealer_id = Column(String(50), ForeignKey("dealerships.dealer_id"), nullable=False)
    slot_id = Column(Integer, ForeignKey("service_slots.slot_id"), nullable=True)
    slot_time = Column(DateTime(timezone=True), nullable=False)
    service_type = Column(String(50), nullable=False)
    pickup_drop_required = Column(Boolean, default=False)
    pickup_address = Column(Text, nullable=True)
    customer_notes = Column(Text, nullable=True)
    booking_status = Column(String(50), default="CONFIRMED")
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    customer = relationship("Customer", back_populates="bookings")
    vehicle = relationship("Vehicle", back_populates="bookings")
    dealer = relationship("Dealership", back_populates="bookings")
    slot = relationship("ServiceSlot")

    def to_dict(self) -> Dict[str, Any]:
        slot_time_str = self.slot_time.isoformat() if hasattr(self.slot_time, "isoformat") else (str(self.slot_time) if self.slot_time else None)
        created_at_str = self.created_at.isoformat() if hasattr(self.created_at, "isoformat") else (str(self.created_at) if self.created_at else None)
        return {
            "booking_id": self.booking_id,
            "booking_reference": self.booking_reference,
            "customer_id": self.customer_id,
            "vin": self.vin,
            "dealer_id": self.dealer_id,
            "slot_id": self.slot_id,
            "slot_time": slot_time_str,
            "service_type": self.service_type,
            "pickup_drop_required": bool(self.pickup_drop_required),
            "pickup_address": self.pickup_address,
            "customer_notes": self.customer_notes,
            "booking_status": self.booking_status,
            "created_at": created_at_str,
        }


class CallLog(Base):
    __tablename__ = "call_logs"

    call_id = Column(String(100), primary_key=True)
    customer_id = Column(String(50), ForeignKey("customers.customer_id"), nullable=True)
    vin = Column(String(50), ForeignKey("vehicles.vin"), nullable=True)
    channel = Column(String(30), default="TWILIO_PSTN")
    call_status = Column(String(50), nullable=False)
    disposition = Column(String(50), nullable=True)
    callback_scheduled_at = Column(DateTime(timezone=True), nullable=True)
    duration_seconds = Column(Integer, default=0)
    transcript_json = Column(Text, nullable=True)
    tool_calls_json = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    customer = relationship("Customer", back_populates="call_logs")

    def get_transcripts(self) -> List[Dict[str, Any]]:
        if not self.transcript_json:
            return []
        if isinstance(self.transcript_json, list):
            return self.transcript_json
        if isinstance(self.transcript_json, dict):
            return [self.transcript_json]
        try:
            res = json.loads(self.transcript_json)
            return res if isinstance(res, list) else [res]
        except Exception:
            return []

    def get_tool_calls(self) -> List[Dict[str, Any]]:
        if not self.tool_calls_json:
            return []
        if isinstance(self.tool_calls_json, list):
            return self.tool_calls_json
        if isinstance(self.tool_calls_json, dict):
            return [self.tool_calls_json]
        try:
            res = json.loads(self.tool_calls_json)
            return res if isinstance(res, list) else [res]
        except Exception:
            return []

    def to_dict(self) -> Dict[str, Any]:
        cb_time_str = self.callback_scheduled_at.isoformat() if hasattr(self.callback_scheduled_at, "isoformat") else (str(self.callback_scheduled_at) if self.callback_scheduled_at else None)
        created_at_str = self.created_at.isoformat() if hasattr(self.created_at, "isoformat") else (str(self.created_at) if self.created_at else None)
        return {
            "call_id": self.call_id,
            "customer_id": self.customer_id,
            "vin": self.vin,
            "channel": self.channel,
            "call_status": self.call_status,
            "disposition": self.disposition,
            "callback_scheduled_at": cb_time_str,
            "duration_seconds": self.duration_seconds,
            "transcripts": self.get_transcripts(),
            "tool_calls": self.get_tool_calls(),
            "created_at": created_at_str,
        }

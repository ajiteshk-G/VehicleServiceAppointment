"""Dealer Management System (DMS) Business Logic and DB Operations."""

import json
import logging
import random
import string
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional
try:
    from sqlalchemy import select, update, and_, or_
    from sqlalchemy.ext.asyncio import AsyncSession
    from backend.app.models import Dealership, Customer, Vehicle, ServiceCostCatalog, ServiceSlot, ServiceBooking, CallLog
except ImportError:
    select = update = and_ = or_ = None  # type: ignore
    AsyncSession = Any  # type: ignore
    Dealership = Customer = Vehicle = ServiceCostCatalog = ServiceSlot = ServiceBooking = CallLog = None  # type: ignore

logger = logging.getLogger(__name__)


def generate_booking_reference(dealer_city: Optional[str] = None, model_name: Optional[str] = None) -> str:
    """Generates an authentic Mahindra/Swaraj booking reference code, e.g. #MND-PUN-8921."""
    city_code = dealer_city[:3].upper() if dealer_city else "IND"
    m_name = model_name or ""
    prefix = "SWR" if "Swaraj" in m_name else "MND"
    num = random.randint(1000, 9999)
    return f"#{prefix}-{city_code}-{num}"


async def get_customer_profile_by_id_or_vin(
    session: AsyncSession,
    customer_id: Optional[str] = None,
    vin: Optional[str] = None,
    phone_number: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    """Retrieves full joined profile for customer, vehicle, and assigned dealership."""
    query = select(Vehicle, Customer, Dealership).join(
        Customer, Vehicle.customer_id == Customer.customer_id
    ).outerjoin(
        Dealership, Vehicle.assigned_dealer_id == Dealership.dealer_id
    )

    if customer_id:
        query = query.where(Customer.customer_id == customer_id)
    elif vin:
        query = query.where(Vehicle.vin == vin)
    elif phone_number:
        query = query.where(Customer.phone_number == phone_number)
    else:
        # Default to first customer if none specified
        pass

    result = await session.execute(query)
    row = result.first()
    if not row:
        return None

    vehicle, customer, dealer = row
    return {
        "customer": customer.to_dict(),
        "vehicle": vehicle.to_dict(),
        "dealership": dealer.to_dict() if dealer else None,
    }


async def get_cost_estimate(
    session: AsyncSession,
    model_name: Optional[str] = None,
    service_type: Optional[str] = "PERIODIC_MAINTENANCE"
) -> Optional[Dict[str, Any]]:
    """Fetches transparent itemized cost estimate from the catalog with robust keyword token matching."""
    raw_model = (model_name or "").strip()
    raw_service = (service_type or "PERIODIC_MAINTENANCE").strip()
    clean_model = raw_model.replace("Mahindra", "").replace("mahindra", "").strip() or raw_model

    if not clean_model:
        result = await session.execute(select(ServiceCostCatalog).limit(1))
        item = result.scalars().first()
        return item.to_dict() if item else None

    # 1. Direct exact or substring match with service type
    query = select(ServiceCostCatalog).where(
        and_(
            or_(
                ServiceCostCatalog.model_name.ilike(f"%{clean_model}%"),
                ServiceCostCatalog.model_name.ilike(f"%{raw_model}%")
            ),
            ServiceCostCatalog.service_type.ilike(f"%{raw_service}%")
        )
    )
    result = await session.execute(query)
    catalog_item = result.scalars().first()

    # 2. Match model without service_type constraint
    if not catalog_item:
        fallback_query = select(ServiceCostCatalog).where(
            or_(
                ServiceCostCatalog.model_name.ilike(f"%{clean_model}%"),
                ServiceCostCatalog.model_name.ilike(f"%{raw_model}%")
            )
        )
        fb_result = await session.execute(fallback_query)
        catalog_item = fb_result.scalars().first()

    # 3. Match individual model key tokens (Scorpio, XUV700, Thar, Swaraj, Classic)
    if not catalog_item:
        tokens = [t for t in clean_model.split() if len(t) > 2]
        for token in tokens:
            t_query = select(ServiceCostCatalog).where(
                ServiceCostCatalog.model_name.ilike(f"%{token}%")
            )
            t_res = await session.execute(t_query)
            catalog_item = t_res.scalars().first()
            if catalog_item:
                break

    if catalog_item:
        return catalog_item.to_dict()
    return None


async def get_available_workshop_slots(
    session: AsyncSession,
    dealer_id: str,
    target_date_str: Optional[str] = None
) -> List[Dict[str, Any]]:
    """Fetches available workshop bay slots for a given dealer and date."""
    now = datetime.now(timezone.utc)

    query = select(ServiceSlot).where(
        and_(
            ServiceSlot.dealer_id == dealer_id,
            ServiceSlot.is_booked == False,
            ServiceSlot.slot_time >= (now - timedelta(minutes=15)),
            or_(
                ServiceSlot.locked_until == None,
                ServiceSlot.locked_until < now
            )
        )
    ).order_by(ServiceSlot.slot_time.asc())

    result = await session.execute(query)
    slots = result.scalars().all()

    # If target_date_str provided (YYYY-MM-DD), filter for that date
    if target_date_str:
        try:
            target_date = datetime.strptime(target_date_str.strip(), "%Y-%m-%d").date()
            slots = [s for s in slots if s.slot_time.date() == target_date]
        except ValueError:
            logger.warning(f"Could not parse date string '{target_date_str}', returning all upcoming slots.")

    return [s.to_dict() for s in slots]


async def hold_slot_atomic(
    session: AsyncSession,
    slot_id: int,
    customer_id: str,
    hold_duration_seconds: int = 180
) -> Dict[str, Any]:
    """Atomically places a 180-second temporary hold on a workshop bay slot."""
    now = datetime.now(timezone.utc)
    locked_until = now + timedelta(seconds=hold_duration_seconds)

    # Fetch slot and ensure it's not booked or currently locked by someone else
    query = select(ServiceSlot).where(ServiceSlot.slot_id == slot_id).with_for_update()
    result = await session.execute(query)
    slot = result.scalars().first()

    if not slot:
        return {"success": False, "error": f"Slot ID {slot_id} not found."}

    if slot.is_booked:
        return {"success": False, "error": "This slot has already been booked by another customer."}

    if slot.is_locked() and slot.locked_by_customer_id != customer_id:
        return {
            "success": False,
            "error": "This slot is currently temporarily reserved by another advisor/customer. Please choose another time."
        }

    # Apply lock
    slot.locked_by_customer_id = customer_id
    slot.locked_until = locked_until
    await session.commit()
    await session.refresh(slot)

    return {
        "success": True,
        "slot_id": slot.slot_id,
        "slot_time": slot.slot_time.isoformat(),
        "bay_number": slot.bay_number,
        "locked_until": locked_until.isoformat(),
        "hold_duration_seconds": hold_duration_seconds,
        "message": f"Bay {slot.bay_number} at {slot.slot_time.strftime('%I:%M %p, %d %b')} is held for {hold_duration_seconds} seconds.",
    }


async def book_service_appointment_atomic(
    session: AsyncSession,
    customer_id: str,
    vin: Optional[str] = None,
    dealer_id: Optional[str] = None,
    slot_id: int = 0,
    preferred_date_time: Optional[Any] = None,
    service_type: str = "PERIODIC_MAINTENANCE",
    pickup_drop_required: bool = False,
    pickup_address: Optional[str] = None,
    customer_notes: Optional[str] = None,
) -> Dict[str, Any]:
    """Confirms service appointment, captures customer requested date/time, marks bay booked, and persists to DB."""
    slot = None
    if slot_id:
        query = select(ServiceSlot).where(ServiceSlot.slot_id == slot_id).with_for_update()
        result = await session.execute(query)
        slot = result.scalars().first()

    # Auto-resolve customer vehicle & dealer if not passed
    if not vin and customer_id:
        v_res = await session.execute(select(Vehicle).where(Vehicle.customer_id == customer_id))
        veh_obj = v_res.scalars().first()
        if veh_obj:
            vin = veh_obj.vin
            if not dealer_id:
                dealer_id = veh_obj.assigned_dealer_id

    if not dealer_id:
        dealer_id = slot.dealer_id if slot else "DLR-PUN-01"

    # If no explicit slot_id provided, parse preferred date/time or pick first open bay
    if not slot:
        slot_dt = None
        if preferred_date_time:
            try:
                clean_dt = str(preferred_date_time).strip().replace("Z", "+00:00")
                parsed_dt = datetime.fromisoformat(clean_dt)
                if parsed_dt.tzinfo is None:
                    parsed_dt = parsed_dt.replace(tzinfo=timezone.utc)
                slot_dt = parsed_dt
            except Exception:
                pass

        if not slot_dt:
            avail_q = select(ServiceSlot).where(
                and_(
                    ServiceSlot.dealer_id == dealer_id,
                    ServiceSlot.is_booked == False
                )
            ).order_by(ServiceSlot.slot_time.asc())
            avail_res = await session.execute(avail_q)
            slot = avail_res.scalars().first()

        if not slot:
            if not slot_dt:
                slot_dt = datetime.now(timezone.utc) + timedelta(days=2, hours=2)
            slot = ServiceSlot(
                dealer_id=dealer_id,
                slot_time=slot_dt,
                bay_number=1,
                is_booked=True,
                locked_by_customer_id=customer_id
            )
            session.add(slot)
            await session.flush()

    # Fetch vehicle & dealership for reference generation
    v_res = await session.execute(select(Vehicle).where(Vehicle.vin == vin))
    vehicle = v_res.scalars().first()
    model_name = vehicle.model_name if vehicle else "Mahindra"

    d_res = await session.execute(select(Dealership).where(Dealership.dealer_id == dealer_id))
    dealer = d_res.scalars().first()
    dealer_city = dealer.city if dealer else "PUN"

    booking_ref = generate_booking_reference(dealer_city, model_name)

    # Mark slot booked
    slot.is_booked = True
    slot.locked_by_customer_id = customer_id
    slot.locked_until = None

    booking = ServiceBooking(
        booking_reference=booking_ref,
        customer_id=customer_id,
        vin=vin or "VIN-MAH-000",
        dealer_id=dealer_id,
        slot_id=slot_id,
        slot_time=slot.slot_time,
        service_type=service_type,
        pickup_drop_required=pickup_drop_required,
        pickup_address=pickup_address,
        customer_notes=customer_notes,
        booking_status="CONFIRMED"
    )
    session.add(booking)
    await session.commit()
    await session.refresh(booking)

    return {
        "success": True,
        "booking_id": booking.booking_id,
        "booking_reference": booking.booking_reference,
        "slot_time": booking.slot_time.isoformat(),
        "bay_number": slot.bay_number,
        "dealer_name": dealer.name if dealer else dealer_id,
        "dealer_address": dealer.address if dealer else "",
        "service_type": service_type,
        "pickup_drop_required": pickup_drop_required,
        "pickup_address": pickup_address,
        "status": "CONFIRMED",
        "message": f"Appointment confirmed with reference {booking_ref}.",
    }


async def reschedule_callback(
    session: AsyncSession,
    customer_id: str,
    vin: Optional[str] = None,
    callback_time: Optional[datetime] = None,
    reason: Optional[str] = None
) -> Dict[str, Any]:
    """Records callback request when customer is busy or driving."""
    if not vin and customer_id:
        v_res = await session.execute(select(Vehicle).where(Vehicle.customer_id == customer_id))
        veh_obj = v_res.scalars().first()
        if veh_obj:
            vin = veh_obj.vin

    if not callback_time:
        callback_time = datetime.now(timezone.utc) + timedelta(days=1, hours=4)

    call_log_id = f"CALL-{customer_id}-{int(datetime.now(timezone.utc).timestamp())}"
    transcript_payload = json.dumps([{
        "role": "system",
        "text": f"Customer requested callback for {callback_time.isoformat()}. Reason: {reason or 'Customer busy'}",
        "timestamp": datetime.now(timezone.utc).isoformat()
    }])

    call_log = CallLog(
        call_id=call_log_id,
        customer_id=customer_id,
        vin=vin,
        channel="TWILIO_PSTN",
        call_status="ANSWERED",
        disposition="RESCHEDULED",
        callback_scheduled_at=callback_time,
        transcript_json=transcript_payload,
        tool_calls_json="[]"
    )
    session.add(call_log)
    await session.commit()

    return {
        "success": True,
        "customer_id": customer_id,
        "callback_scheduled_at": callback_time.isoformat(),
        "disposition": "RESCHEDULED",
        "message": f"Reminder rescheduled for {callback_time.strftime('%I:%M %p on %d %b %Y')}.",
    }


async def record_disposition(
    session: AsyncSession,
    customer_id: str,
    vin: Optional[str] = None,
    disposition: str = "DECLINED",
    notes: Optional[str] = None
) -> Dict[str, Any]:
    """Logs the final customer disposition (e.g. ALREADY_SERVICED, VEHICLE_SOLD, DECLINED)."""
    if not vin and customer_id:
        v_res = await session.execute(select(Vehicle).where(Vehicle.customer_id == customer_id))
        veh_obj = v_res.scalars().first()
        if veh_obj:
            vin = veh_obj.vin

    call_log_id = f"CALL-{customer_id}-{int(datetime.now(timezone.utc).timestamp())}"
    norm_disp = disposition.upper() if disposition else "DECLINED"
    if norm_disp in ["VEHICLE_SOLD", "NOT_INTERESTED", "WRONG_NUMBER", "DND_REQUESTED", "INQUIRY"]:
        norm_disp = "DECLINED"
    elif norm_disp not in ["BOOKED", "RESCHEDULED", "TRANSFERRED", "ALREADY_SERVICED", "DECLINED"]:
        norm_disp = "DECLINED"

    transcript_payload = json.dumps([{
        "role": "system",
        "text": notes or f"Disposition logged as {norm_disp}",
        "timestamp": datetime.now(timezone.utc).isoformat()
    }])

    call_log = CallLog(
        call_id=call_log_id,
        customer_id=customer_id,
        vin=vin,
        channel="TWILIO_PSTN",
        call_status="ANSWERED",
        disposition=norm_disp,
        transcript_json=transcript_payload,
        tool_calls_json="[]"
    )
    session.add(call_log)
    await session.commit()

    return {
        "success": True,
        "customer_id": customer_id,
        "disposition": norm_disp,
        "notes": notes,
        "message": f"Disposition '{norm_disp}' recorded successfully.",
    }


async def transfer_to_advisor(
    session: AsyncSession,
    dealer_id: str,
    customer_id: str,
    reason: Optional[str] = None
) -> Dict[str, Any]:
    """Prepares warm transfer to human service advisor with context handover."""
    d_res = await session.execute(select(Dealership).where(Dealership.dealer_id == dealer_id))
    dealer = d_res.scalars().first()

    advisor_phone = dealer.service_advisor_phone if dealer else "+919822012345"
    dealer_name = dealer.name if dealer else "Mahindra Service Center"

    return {
        "success": True,
        "advisor_phone": advisor_phone,
        "dealer_name": dealer_name,
        "reason": reason or "Customer requested technical specialist / custom repair estimate",
        "handover_context": f"Customer ID: {customer_id}, Dealer: {dealer_name}, Reason: {reason}",
        "message": f"Connecting you with our Senior Service Advisor at {dealer_name} ({advisor_phone}).",
    }

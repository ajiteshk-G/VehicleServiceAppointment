"""Database-Backed Async Tool Execution Handler for Gemini Function Calling."""

import logging
import time
from datetime import datetime, timezone, timedelta
from typing import Any, Dict
try:
    from sqlalchemy.ext.asyncio import AsyncSession
except ImportError:
    AsyncSession = Any  # type: ignore
from backend.app.services import dms_service, notification_service

logger = logging.getLogger(__name__)


async def execute_tool_call(
    tool_name: str,
    args: Dict[str, Any],
    session: AsyncSession
) -> Dict[str, Any]:
    """
    Executes a Gemini 2.5 Live tool call against the DMS database.
    Measures execution time and returns a structured output payload.
    """
    start_time = time.perf_counter()
    logger.info(f"Executing Tool Call: '{tool_name}' with args: {args}")

    try:
        if tool_name == "get_customer_vehicle_profile":
            customer_id = args.get("customer_id")
            vin = args.get("vin")
            profile = await dms_service.get_customer_profile_by_id_or_vin(session, customer_id=customer_id, vin=vin)
            if profile:
                result = {"status": "SUCCESS", "data": profile}
            else:
                result = {"status": "NOT_FOUND", "message": f"Profile not found for customer_id={customer_id}, vin={vin}"}

        elif tool_name == "get_service_cost_estimate":
            model_name = args.get("model_name") or args.get("model") or args.get("vehicle_model") or ""
            service_type = args.get("service_type") or args.get("type") or "PERIODIC_MAINTENANCE"
            estimate = await dms_service.get_cost_estimate(session, model_name=model_name, service_type=service_type)
            if estimate:
                result = {"status": "SUCCESS", "estimate": estimate}
            else:
                result = {"status": "NOT_FOUND", "message": f"Cost estimate not available for model '{model_name}'"}

        elif tool_name == "check_available_slots":
            dealer_id = args.get("dealer_id") or args.get("dealership_id") or "DLR-PUN-01"
            target_date = args.get("target_date") or args.get("date")
            slots = await dms_service.get_available_workshop_slots(session, dealer_id=dealer_id, target_date_str=target_date)
            result = {
                "status": "SUCCESS",
                "dealer_id": dealer_id,
                "available_slots_count": len(slots),
                "slots": slots[:8]  # Limit to 8 slots for concise model context
            }

        elif tool_name == "hold_service_slot":
            raw_slot_id = args.get("slot_id") or args.get("id") or 0
            try:
                slot_id = int(str(raw_slot_id).replace("slot_", "").strip())
            except (ValueError, TypeError):
                slot_id = 0
            customer_id = args.get("customer_id") or "CUST-101"
            hold_res = await dms_service.hold_slot_atomic(session, slot_id=slot_id, customer_id=customer_id)
            result = hold_res

        elif tool_name == "book_service_appointment":
            customer_id = args.get("customer_id", "")
            vin = args.get("vin", "")
            dealer_id = args.get("dealer_id") or args.get("dealership_id") or ""
            raw_slot_id = args.get("slot_id") or args.get("id") or 0
            try:
                slot_id = int(str(raw_slot_id).replace("slot_", "").strip())
            except (ValueError, TypeError):
                slot_id = 0
            service_type = args.get("service_type") or args.get("type") or "PERIODIC_MAINTENANCE"
            
            raw_pickup = args.get("pickup_drop_required", False)
            if isinstance(raw_pickup, str):
                pickup_drop = raw_pickup.strip().lower() in ("true", "1", "yes", "t")
            else:
                pickup_drop = bool(raw_pickup)

            pickup_addr = args.get("pickup_address") or args.get("address")
            notes = args.get("customer_notes") or args.get("notes")
            pref_date_time = args.get("preferred_date_time") or args.get("target_date") or args.get("slot_time") or args.get("date_time")

            booking_res = await dms_service.book_service_appointment_atomic(
                session=session,
                customer_id=customer_id,
                vin=vin,
                dealer_id=dealer_id,
                slot_id=slot_id,
                preferred_date_time=pref_date_time,
                service_type=service_type,
                pickup_drop_required=pickup_drop,
                pickup_address=pickup_addr,
                customer_notes=notes
            )

            if booking_res.get("success"):
                # Fetch customer & dealer details to dispatch WhatsApp / SMS
                profile = await dms_service.get_customer_profile_by_id_or_vin(session, customer_id=customer_id)
                if profile:
                    cust = profile.get("customer", {})
                    v = profile.get("vehicle", {})
                    d = profile.get("dealership", {})
                    # Look up cost estimate if available for confirmation card
                    cost_est = await dms_service.get_cost_estimate(session, model_name=v.get("model_name"), service_type=service_type)
                    total_cost = float(cost_est.get("total_estimated_cost", 0.0)) if cost_est else None

                    await notification_service.send_booking_confirmation(
                        customer_phone=cust.get("phone_number", ""),
                        customer_name=cust.get("full_name", "Valued Customer"),
                        booking_reference=booking_res.get("booking_reference", ""),
                        vehicle_model=v.get("model_name", "Mahindra"),
                        slot_time_str=booking_res.get("slot_time", ""),
                        dealer_name=d.get("name", "Mahindra Authorized Service"),
                        dealer_address=d.get("address", ""),
                        maps_url=d.get("maps_url"),
                        total_cost_estimate=total_cost,
                    )

            result = booking_res

        elif tool_name == "reschedule_reminder":
            customer_id = args.get("customer_id", "")
            vin = args.get("vin", "")
            cb_str = str(args.get("callback_date_time", "")).strip()
            reason = args.get("reason") or "Customer busy / requested callback"
            
            now_utc = datetime.now(timezone.utc)
            cb_time = now_utc + timedelta(days=1, hours=4)
            if cb_str:
                clean_cb = cb_str.replace("Z", "+00:00")
                parsed = None
                for fmt in (
                    "%Y-%m-%dT%H:%M:%S%z",
                    "%Y-%m-%dT%H:%M:%S",
                    "%Y-%m-%d %H:%M:%S",
                    "%Y-%m-%d %H:%M",
                    "%Y-%m-%d",
                    "%d/%m/%Y %H:%M",
                    "%d-%m-%Y %H:%M",
                ):
                    try:
                        parsed = datetime.strptime(clean_cb[:19] if "T" not in clean_cb else clean_cb, fmt)
                        break
                    except Exception:
                        pass
                if not parsed:
                    try:
                        parsed = datetime.fromisoformat(clean_cb)
                    except Exception:
                        pass
                if parsed:
                    if parsed.tzinfo is None:
                        parsed = parsed.replace(tzinfo=timezone.utc)
                    cb_time = parsed

            reschedule_res = await dms_service.reschedule_callback(
                session=session,
                customer_id=customer_id,
                vin=vin,
                callback_time=cb_time,
                reason=reason
            )
            result = reschedule_res

        elif tool_name == "record_customer_disposition":
            customer_id = args.get("customer_id", "")
            vin = args.get("vin", "")
            disp = args.get("disposition", "DECLINED")
            notes = args.get("notes")
            disp_res = await dms_service.record_disposition(
                session=session,
                customer_id=customer_id,
                vin=vin,
                disposition=disp,
                notes=notes
            )
            result = disp_res

        elif tool_name == "transfer_to_service_advisor":
            dealer_id = args.get("dealer_id", "DLR-PUN-01")
            customer_id = args.get("customer_id", "")
            reason = args.get("reason")
            transfer_res = await dms_service.transfer_to_advisor(
                session=session,
                dealer_id=dealer_id,
                customer_id=customer_id,
                reason=reason
            )
            result = transfer_res
        elif tool_name == "end_call":
            reason = args.get("reason", "Conversation ended normally")
            result = {"status": "SUCCESS", "action": "HANGUP", "reason": reason}

        else:
            result = {"status": "ERROR", "message": f"Unknown tool: '{tool_name}'"}

    except Exception as e:
        logger.exception(f"Error during tool execution '{tool_name}': {e}")
        result = {"status": "ERROR", "error": str(e)}

    elapsed_ms = (time.perf_counter() - start_time) * 1000
    result["_latency_ms"] = round(elapsed_ms, 2)
    logger.info(f"Tool '{tool_name}' completed in {elapsed_ms:.1f}ms")
    return result


def get_gemini_tool_declarations():
    """Returns Gemini Function Declarations for all 8 DMS domain tools."""
    from google.genai import types

    return [
        types.Tool(
            function_declarations=[
                types.FunctionDeclaration(
                    name="get_customer_vehicle_profile",
                    description="Fetches customer, vehicle odometer, warranty status, and service history.",
                    parameters=types.Schema(
                        type="OBJECT",
                        properties={
                            "customer_id": types.Schema(type="STRING", description="Unique Customer ID, e.g. CUST-101"),
                            "vin": types.Schema(type="STRING", description="Vehicle VIN if known"),
                        }
                    ),
                ),
                types.FunctionDeclaration(
                    name="get_service_cost_estimate",
                    description="Calculates transparent itemized pricing (Parts, Genuine Oil, Labor, 18% GST) for maintenance or repair.",
                    parameters=types.Schema(
                        type="OBJECT",
                        properties={
                            "model_name": types.Schema(type="STRING", description="Vehicle model, e.g. Scorpio-N Z8L, XUV700 AX7, Thar LX, Swaraj 855 FE"),
                            "service_type": types.Schema(type="STRING", description="Service type code, e.g. PERIODIC_MAINTENANCE"),
                        },
                        required=["model_name"],
                    ),
                ),
                types.FunctionDeclaration(
                    name="check_available_slots",
                    description="Queries real-time DMS workshop bay capacity and upcoming appointment slots.",
                    parameters=types.Schema(
                        type="OBJECT",
                        properties={
                            "dealer_id": types.Schema(type="STRING", description="Dealership ID, e.g. DLR-PUN-01"),
                            "target_date": types.Schema(type="STRING", description="Optional date (YYYY-MM-DD)"),
                        },
                        required=["dealer_id"],
                    ),
                ),
                types.FunctionDeclaration(
                    name="hold_service_slot",
                    description="Locks a workshop bay slot for 180 seconds to prevent double-booking while customer confirms.",
                    parameters=types.Schema(
                        type="OBJECT",
                        properties={
                            "slot_id": types.Schema(type="INTEGER", description="Numeric slot ID returned by check_available_slots"),
                            "customer_id": types.Schema(type="STRING", description="Customer ID locking the slot"),
                        },
                        required=["slot_id"],
                    ),
                ),
                types.FunctionDeclaration(
                    name="book_service_appointment",
                    description="Finalizes the workshop appointment booking in DMS, records customer requested date/time in database, and triggers instant confirmation.",
                    parameters=types.Schema(
                        type="OBJECT",
                        properties={
                            "customer_id": types.Schema(type="STRING", description="Customer ID"),
                            "slot_id": types.Schema(type="INTEGER", description="Reserved workshop bay slot ID (if chosen from check_available_slots)"),
                            "preferred_date_time": types.Schema(type="STRING", description="Customer's chosen service date & time ISO string (e.g. 2026-08-25T10:00:00)"),
                            "pickup_drop_required": types.Schema(type="BOOLEAN", description="True if customer requests pick and drop"),
                            "pickup_address": types.Schema(type="STRING", description="Customer address for pickup"),
                            "customer_notes": types.Schema(type="STRING", description="Any customer specific issues or complaints"),
                        },
                        required=["customer_id"],
                    ),
                ),
                types.FunctionDeclaration(
                    name="reschedule_reminder",
                    description="Reschedules the voice reminder when customer is busy, driving, or in a meeting.",
                    parameters=types.Schema(
                        type="OBJECT",
                        properties={
                            "customer_id": types.Schema(type="STRING", description="Customer ID"),
                            "callback_date_time": types.Schema(type="STRING", description="Requested callback date/time ISO string"),
                            "reason": types.Schema(type="STRING", description="Reason, e.g. Driving, In a meeting, Traveling"),
                        },
                        required=["customer_id"],
                    ),
                ),
                types.FunctionDeclaration(
                    name="record_customer_disposition",
                    description="Records call disposition in DMS (BOOKED, RESCHEDULED, ALREADY_SERVICED, VEHICLE_SOLD, DECLINED).",
                    parameters=types.Schema(
                        type="OBJECT",
                        properties={
                            "customer_id": types.Schema(type="STRING", description="Customer ID"),
                            "disposition": types.Schema(type="STRING", description="Disposition status code"),
                            "notes": types.Schema(type="STRING", description="Summary notes"),
                        },
                        required=["customer_id", "disposition"],
                    ),
                ),
                types.FunctionDeclaration(
                    name="transfer_to_service_advisor",
                    description="Transfers the call to a human service advisor for complex accidental or warranty disputes.",
                    parameters=types.Schema(
                        type="OBJECT",
                        properties={
                            "dealer_id": types.Schema(type="STRING", description="Dealership ID"),
                            "customer_id": types.Schema(type="STRING", description="Customer ID"),
                            "reason": types.Schema(type="STRING", description="Reason for transfer"),
                        },
                        required=["dealer_id", "customer_id"],
                    ),
                ),
                types.FunctionDeclaration(
                    name="end_call",
                    description="Hangs up and terminates the voice call after the conversation is finished (e.g. appointment is booked and confirmed, callback is scheduled, or customer has said goodbye).",
                    parameters=types.Schema(
                        type="OBJECT",
                        properties={
                            "reason": types.Schema(type="STRING", description="Reason for ending call, e.g. 'Appointment confirmed and goodbye completed', 'Callback scheduled', 'Customer declined'"),
                        },
                    ),
                ),
            ]
        )
    ]

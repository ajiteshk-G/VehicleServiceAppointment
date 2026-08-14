"""Declarations and Schemas for Gemini 2.5 Live Function Calling."""

from typing import Any, Dict, List

GEMINI_TOOLS_DECLARATIONS: List[Dict[str, Any]] = [
    {
        "name": "get_customer_vehicle_profile",
        "description": "Retrieves the dynamic customer details, vehicle specification, current odometer, service history, and assigned dealership from the DMS database.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "customer_id": {
                    "type": "STRING",
                    "description": "Unique customer identifier (e.g. 'CUST-101')."
                },
                "vin": {
                    "type": "STRING",
                    "description": "Vehicle Identification Number (e.g. 'VIN-MAH-SCN-2024-001')."
                }
            }
        }
    },
    {
        "name": "get_service_cost_estimate",
        "description": "Retrieves an itemized, transparent cost breakdown for a vehicle model including genuine parts, engine oil, labor charges, GST tax, and full inspection checklist.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "model_name": {
                    "type": "STRING",
                    "description": "Vehicle model name (e.g. 'Scorpio-N Z8L', 'XUV700 AX7', 'Thar LX', 'Swaraj 855 FE')."
                },
                "service_type": {
                    "type": "STRING",
                    "description": "Type of service required, e.g. 'PERIODIC_MAINTENANCE' or 'GENERAL_CHECKUP'."
                }
            },
            "required": ["model_name"]
        }
    },
    {
        "name": "check_available_slots",
        "description": "Checks available workshop bay appointment slots at an authorized dealership for a given date.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "dealer_id": {
                    "type": "STRING",
                    "description": "Dealership identifier (e.g. 'DLR-PUN-01')."
                },
                "target_date": {
                    "type": "STRING",
                    "description": "Date in YYYY-MM-DD format (e.g. '2026-08-16'). Optional; defaults to all upcoming slots."
                }
            },
            "required": ["dealer_id"]
        }
    },
    {
        "name": "hold_service_slot",
        "description": "Places an atomic 180-second temporary reservation hold on a specific workshop bay slot while the customer reviews details.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "slot_id": {
                    "type": "INTEGER",
                    "description": "The unique numerical slot ID to hold."
                },
                "customer_id": {
                    "type": "STRING",
                    "description": "The customer ID placing the hold."
                }
            },
            "required": ["slot_id", "customer_id"]
        }
    },
    {
        "name": "book_service_appointment",
        "description": "Confirms and books a service appointment in the DMS, locks the workshop bay, generates a booking reference code (#MND-...), and triggers WhatsApp/SMS confirmation dispatch.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "customer_id": {
                    "type": "STRING",
                    "description": "Customer identifier."
                },
                "vin": {
                    "type": "STRING",
                    "description": "Vehicle VIN."
                },
                "dealer_id": {
                    "type": "STRING",
                    "description": "Dealership ID."
                },
                "slot_id": {
                    "type": "INTEGER",
                    "description": "Workshop slot ID."
                },
                "service_type": {
                    "type": "STRING",
                    "description": "Service type (e.g. 'PERIODIC_MAINTENANCE')."
                },
                "pickup_drop_required": {
                    "type": "BOOLEAN",
                    "description": "True if customer requests doorstep pick-up and drop-off."
                },
                "pickup_address": {
                    "type": "STRING",
                    "description": "Customer pickup address if pickup is required."
                },
                "customer_notes": {
                    "type": "STRING",
                    "description": "Any specific issues reported by customer (e.g. AC noise, brake vibration)."
                }
            },
            "required": ["customer_id", "vin", "dealer_id", "slot_id"]
        }
    },
    {
        "name": "reschedule_reminder",
        "description": "Schedules a callback reminder for when the customer is busy, driving, or in a meeting.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "customer_id": {
                    "type": "STRING",
                    "description": "Customer ID."
                },
                "vin": {
                    "type": "STRING",
                    "description": "Vehicle VIN."
                },
                "callback_date_time": {
                    "type": "STRING",
                    "description": "Requested callback date and time string (e.g. 'Tomorrow at 4:00 PM' or ISO datetime)."
                },
                "reason": {
                    "type": "STRING",
                    "description": "Reason for callback (e.g. 'Customer is driving')."
                }
            },
            "required": ["customer_id", "vin", "callback_date_time"]
        }
    },
    {
        "name": "record_customer_disposition",
        "description": "Records non-booking call dispositions such as ALREADY_SERVICED, VEHICLE_SOLD, DECLINED, or DND request in the CRM.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "customer_id": {
                    "type": "STRING",
                    "description": "Customer ID."
                },
                "vin": {
                    "type": "STRING",
                    "description": "Vehicle VIN."
                },
                "disposition": {
                    "type": "STRING",
                    "description": "Disposition code: 'ALREADY_SERVICED', 'VEHICLE_SOLD', 'DECLINED', 'WRONG_NUMBER', 'DND_REQUESTED'."
                },
                "notes": {
                    "type": "STRING",
                    "description": "Optional notes from the conversation."
                }
            },
            "required": ["customer_id", "vin", "disposition"]
        }
    },
    {
        "name": "transfer_to_service_advisor",
        "description": "Initiates a live warm transfer to a human Senior Service Advisor at the dealership when the customer has complex mechanical or customized inquiries.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "dealer_id": {
                    "type": "STRING",
                    "description": "Dealership ID."
                },
                "customer_id": {
                    "type": "STRING",
                    "description": "Customer ID."
                },
                "reason": {
                    "type": "STRING",
                    "description": "Summary reason for transfer (e.g. 'Customer reported strange gearbox noise')."
                }
            },
            "required": ["dealer_id", "customer_id"]
        }
    },
    {
        "name": "end_call",
        "description": "Hangs up and terminates the voice call after the conversation is finished (e.g. appointment is booked and confirmed, callback is scheduled, or customer has said goodbye).",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "reason": {
                    "type": "STRING",
                    "description": "Reason for ending call, e.g. 'Appointment confirmed and goodbye completed', 'Callback scheduled', 'Customer declined'."
                }
            }
        }
    }
]

"""Omnichannel Notification Service (Twilio SMS, WhatsApp & Cloud Pub/Sub)."""

import json
import logging
from typing import Any, Dict, Optional
from backend.app.config import settings

logger = logging.getLogger(__name__)


async def send_booking_confirmation(
    customer_phone: str,
    customer_name: str,
    booking_reference: str,
    vehicle_model: str,
    slot_time_str: str,
    dealer_name: str,
    dealer_address: str,
    maps_url: Optional[str] = None,
    total_cost_estimate: Optional[float] = None
) -> Dict[str, Any]:
    """
    Sends WhatsApp and SMS service booking confirmation card to customer.
    Falls back to structured log simulation if Twilio API keys are not provided.
    """
    message_text = (
        f"🚗 Namaste {customer_name}! Your service appointment is confirmed.\n\n"
        f"📋 Booking Ref: {booking_reference}\n"
        f"🚘 Vehicle: {vehicle_model}\n"
        f"🗓️ Slot: {slot_time_str}\n"
        f"🏢 Workshop: {dealer_name}\n"
        f"📍 Address: {dealer_address}\n"
    )
    if total_cost_estimate:
        message_text += f"💰 Est. Cost: ₹{total_cost_estimate:,.2f} (Parts + Oil + Labor + GST)\n"
    if maps_url:
        message_text += f"🗺️ Google Maps: {maps_url}\n"
    message_text += "\nThank you for choosing Mahindra & Mahindra Service!"

    dispatch_result = {
        "status": "SENT",
        "channels": [],
        "booking_reference": booking_reference,
        "recipient": customer_phone,
        "payload_text": message_text,
    }

    if settings.is_twilio_configured:
        try:
            from twilio.rest import Client
            client = Client(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN)

            # Send SMS
            sms = client.messages.create(
                body=message_text,
                from_=settings.TWILIO_PHONE_NUMBER,
                to=customer_phone
            )
            dispatch_result["channels"].append({"channel": "SMS", "sid": sms.sid})
            logger.info(f"Twilio SMS dispatched successfully (SID: {sms.sid})")

            # Send WhatsApp if enabled
            if settings.TWILIO_WHATSAPP_NUMBER:
                try:
                    wa = client.messages.create(
                        body=message_text,
                        from_=f"whatsapp:{settings.TWILIO_WHATSAPP_NUMBER}",
                        to=f"whatsapp:{customer_phone}"
                    )
                    dispatch_result["channels"].append({"channel": "WHATSAPP", "sid": wa.sid})
                    logger.info(f"Twilio WhatsApp message dispatched (SID: {wa.sid})")
                except Exception as wa_err:
                    logger.warning(f"WhatsApp dispatch skipped/failed: {wa_err}")

        except Exception as e:
            logger.error(f"Error calling Twilio API: {e}")
            dispatch_result["status"] = "SIMULATED_DUE_TO_ERROR"
            dispatch_result["error"] = str(e)
    else:
        logger.info(f"[SIMULATED NOTIFICATION] Sent to {customer_phone}:\n{message_text}")
        dispatch_result["channels"].append({"channel": "SIMULATED_SMS", "status": "DELIVERED"})
        dispatch_result["channels"].append({"channel": "SIMULATED_WHATSAPP", "status": "DELIVERED"})

    # Publish to Cloud Pub/Sub if running in GCP environment
    try:
        if settings.GCP_PROJECT_ID and settings.ENVIRONMENT == "production":
            from google.cloud import pubsub_v1
            publisher = pubsub_v1.PublisherClient()
            topic_path = publisher.topic_path(settings.GCP_PROJECT_ID, settings.PUBSUB_TOPIC_BOOKING_CONFIRMED)
            pub_data = json.dumps({
                "booking_reference": booking_reference,
                "customer_name": customer_name,
                "phone": customer_phone,
                "vehicle": vehicle_model,
                "slot_time": slot_time_str,
                "dealer": dealer_name
            }).encode("utf-8")
            publisher.publish(topic_path, pub_data)
            logger.info(f"Published booking event to PubSub topic {settings.PUBSUB_TOPIC_BOOKING_CONFIRMED}")
    except Exception as ps_err:
        logger.debug(f"Cloud PubSub publish skipped: {ps_err}")

    return dispatch_result

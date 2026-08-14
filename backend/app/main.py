"""FastAPI Server with Twilio Webhooks, Media Streams WebSocket, WebRTC Mic, and DMS APIs."""

import asyncio
import json
import logging
import os
import time
from contextlib import asynccontextmanager
from typing import Any, Dict, Optional

try:
    from fastapi import Depends, FastAPI, HTTPException, Query, Request, Response, WebSocket, WebSocketDisconnect
    from fastapi.middleware.cors import CORSMiddleware
    _FASTAPI_AVAILABLE = True
except ImportError:
    _FASTAPI_AVAILABLE = False

    class _Dummy:
        def __call__(self, *args, **kwargs):
            return self
        def __getattr__(self, name):
            return self

    class Response:  # type: ignore
        def __init__(self, content: Any = "", media_type: str = ""):
            self.content = content
            self.body = content.encode("utf-8") if isinstance(content, str) else content
            self.media_type = media_type

    Depends = HTTPException = Query = Request = WebSocket = WebSocketDisconnect = _Dummy()
    CORSMiddleware = None

    class FastAPI:  # type: ignore
        def __init__(self, *args, **kwargs):
            pass
        def get(self, *args, **kwargs):
            return lambda fn: fn
        def post(self, *args, **kwargs):
            return lambda fn: fn
        def api_route(self, *args, **kwargs):
            return lambda fn: fn
        def websocket(self, *args, **kwargs):
            return lambda fn: fn
        def add_middleware(self, *args, **kwargs):
            pass

try:
    from sqlalchemy import select
    from sqlalchemy.ext.asyncio import AsyncSession
except ImportError:
    select = None
    AsyncSession = Any  # type: ignore

from backend.app.config import settings
from backend.app.database import get_db, init_db
from backend.app.models import Dealership, Customer, Vehicle, ServiceCostCatalog, ServiceSlot, ServiceBooking, CallLog
from backend.app.seed_db import seed_database
from backend.app.services import dms_service, campaign_service
from backend.app.core.audio_bridge import AudioBridgeSession, active_telemetry_sockets, broadcast_telemetry

logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("main")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application startup and shutdown events."""
    logger.info(f"Starting {settings.APP_NAME} v{settings.APP_VERSION}")
    await init_db()
    # Auto-seed test records if empty
    try:
        await seed_database()
    except Exception as e:
        logger.warning(f"Database auto-seeding notice: {e}")
    yield
    logger.info("Application shutting down.")


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    lifespan=lifespan
)

# CORS Setup
if _FASTAPI_AVAILABLE and CORSMiddleware:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )


# ==============================================================================
# Dynamic URL Resolution Helpers (Cloud Run Native)
# ==============================================================================

def resolve_request_base_url(request: Request) -> str:
    """Dynamically resolves the public base URL from Cloud Run headers, request.base_url, or K_SERVICE."""
    if settings.PUBLIC_BASE_URL:
        return settings.PUBLIC_BASE_URL.rstrip("/")
    headers = getattr(request, "headers", {})
    proto = headers.get("x-forwarded-proto") or (request.url.scheme if hasattr(request, "url") and hasattr(request.url, "scheme") else "https") or "https"
    host = headers.get("x-forwarded-host") or headers.get("host")
    if not host and hasattr(request, "url") and hasattr(request.url, "netloc") and request.url.netloc:
        host = request.url.netloc
    if not host and hasattr(request, "base_url") and hasattr(request.base_url, "netloc") and request.base_url.netloc:
        host = request.base_url.netloc

    if host:
        return f"{proto}://{host}"

    if os.getenv("K_SERVICE"):
        k_svc = os.getenv("K_SERVICE")
        return f"https://{k_svc}-{settings.GCP_PROJECT_ID}.{settings.GCP_LOCATION}.run.app"

    if hasattr(request, "base_url") and str(request.base_url).strip():
        return str(request.base_url).rstrip("/")

    return "http://localhost:8000"


def resolve_request_ws_url(request: Request) -> str:
    """Dynamically constructs the secure wss:// WebSocket URL for Twilio Media Streams on Cloud Run."""
    if settings.PUBLIC_BASE_URL:
        return f"{settings.ws_base_url}/ws/twilio/stream"

    headers = getattr(request, "headers", {})
    proto = headers.get("x-forwarded-proto") or (request.url.scheme if hasattr(request, "url") and hasattr(request.url, "scheme") else "https") or "https"
    host = headers.get("x-forwarded-host") or headers.get("host")
    if not host and hasattr(request, "url") and hasattr(request.url, "netloc") and request.url.netloc:
        host = request.url.netloc
    if not host and hasattr(request, "base_url") and hasattr(request.base_url, "netloc") and request.base_url.netloc:
        host = request.base_url.netloc

    if host:
        if proto == "https" or (not host.startswith("localhost") and not host.startswith("127.0.0.1") and not host.startswith("0.0.0.0")):
            return f"wss://{host}/ws/twilio/stream"
        return f"ws://{host}/ws/twilio/stream"

    if os.getenv("K_SERVICE"):
        k_svc = os.getenv("K_SERVICE")
        return f"wss://{k_svc}-{settings.GCP_PROJECT_ID}.{settings.GCP_LOCATION}.run.app/ws/twilio/stream"

    return f"{settings.ws_base_url}/ws/twilio/stream"


# ==============================================================================
# Health & Status Endpoint
# ==============================================================================

@app.get("/health")
async def health_check():
    return {
        "status": "HEALTHY",
        "app": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "environment": settings.ENVIRONMENT,
        "twilio_configured": settings.is_twilio_configured,
        "vertex_configured": settings.is_vertex_configured,
        "gemini_configured": settings.is_gemini_configured,
        "gcp_project_id": settings.GCP_PROJECT_ID,
        "gcp_location": settings.GCP_LOCATION,
        "database_url": settings.DATABASE_URL.split("@")[-1],  # Sanitized
    }


@app.get("/", response_class=Response)
async def serve_mission_control_console():
    """Serves the interactive Mission Control Web Console."""
    html_path = os.path.join(os.path.dirname(__file__), "static_index.html")
    if os.path.exists(html_path):
        with open(html_path, "r", encoding="utf-8") as f:
            html_content = f.read()
        return Response(
            content=html_content,
            media_type="text/html",
            headers={
                "Cache-Control": "no-cache, no-store, must-revalidate",
                "Pragma": "no-cache",
                "Expires": "0"
            }
        )
    return Response(
        content="<h1>Mahindra & Swaraj AI Voice Concierge API Live</h1><p>Visit /health for status</p>",
        media_type="text/html"
    )


# ==============================================================================
# DMS & Customer Database REST Endpoints
# ==============================================================================

@app.get("/api/dealerships")
async def list_dealerships(session: AsyncSession = Depends(get_db)):
    result = await session.execute(select(Dealership))
    dealers = result.scalars().all()
    return [d.to_dict() for d in dealers]


@app.get("/api/customers")
async def list_customers(session: AsyncSession = Depends(get_db)):
    """Returns customers joined with their primary vehicle and dealer information."""
    query = select(Customer, Vehicle, Dealership).join(
        Vehicle, Customer.customer_id == Vehicle.customer_id
    ).outerjoin(
        Dealership, Vehicle.assigned_dealer_id == Dealership.dealer_id
    )
    result = await session.execute(query)
    rows = result.all()

    output = []
    for customer, vehicle, dealer in rows:
        c_dict = customer.to_dict()
        c_dict["vehicle"] = vehicle.to_dict()
        c_dict["dealership"] = dealer.to_dict() if dealer else None
        output.append(c_dict)
    return output


@app.get("/api/customers/{customer_id}")
async def get_customer_detail(customer_id: str, session: AsyncSession = Depends(get_db)):
    profile = await dms_service.get_customer_profile_by_id_or_vin(session, customer_id=customer_id)
    if not profile:
        raise HTTPException(status_code=404, detail="Customer not found")
    return profile


@app.get("/api/catalog")
async def get_catalog(session: AsyncSession = Depends(get_db)):
    result = await session.execute(select(ServiceCostCatalog))
    items = result.scalars().all()
    return [item.to_dict() for item in items]


@app.get("/api/slots")
async def get_slots(
    dealer_id: str = Query("DLR-PUN-01"),
    date: Optional[str] = Query(None),
    session: AsyncSession = Depends(get_db)
):
    query = select(ServiceSlot).where(ServiceSlot.dealer_id == dealer_id).order_by(ServiceSlot.slot_time.asc())
    result = await session.execute(query)
    slots = result.scalars().all()

    if date:
        slots = [s for s in slots if s.slot_time.strftime("%Y-%m-%d") == date]

    return [s.to_dict() for s in slots]


@app.get("/api/bookings")
async def list_bookings(session: AsyncSession = Depends(get_db)):
    query = select(ServiceBooking).order_by(ServiceBooking.created_at.desc()).limit(20)
    result = await session.execute(query)
    bookings = result.scalars().all()
    return [b.to_dict() for b in bookings]


@app.get("/api/call-logs")
async def list_call_logs(session: AsyncSession = Depends(get_db)):
    """Returns detailed call history, transcripts, and customer dispositions."""
    query = select(CallLog).order_by(CallLog.created_at.desc()).limit(100)
    result = await session.execute(query)
    logs = result.scalars().all()

    enriched_logs = []
    for log in logs:
        log_dict = log.to_dict()
        
        # Enrich Customer & Vehicle Details
        if log.customer_id:
            c_res = await session.execute(select(Customer).where(Customer.customer_id == log.customer_id))
            c = c_res.scalars().first()
            if c:
                log_dict["customer_name"] = c.full_name
                log_dict["customer_phone"] = c.phone_number
                log_dict["customer_city"] = c.city

        if log.vin:
            v_res = await session.execute(select(Vehicle).where(Vehicle.vin == log.vin))
            v = v_res.scalars().first()
            if v:
                log_dict["model_name"] = v.model_name
                log_dict["registration_number"] = v.registration_number
                log_dict["current_odometer_km"] = v.current_odometer_km
        disp = (log.disposition or "DECLINED").upper()
        if disp in ["VEHICLE_SOLD", "NOT_INTERESTED", "WRONG_NUMBER", "DND_REQUESTED", "INQUIRY", ""]:
            disp = "DECLINED"
        elif disp == "CONFIRMED":
            disp = "BOOKED"
        elif disp not in ["BOOKED", "RESCHEDULED", "TRANSFERRED", "ALREADY_SERVICED", "DECLINED"]:
            disp = "DECLINED"
        log_dict["disposition"] = disp

        enriched_logs.append(log_dict)

    return enriched_logs


@app.get("/api/campaign/queue")
async def get_campaign_queue(session: AsyncSession = Depends(get_db)):
    queue = await campaign_service.get_due_campaign_queue(session)
    return queue


@app.post("/api/campaign/trigger-scheduled-run")
async def trigger_scheduled_campaign_run(request: Request, session: AsyncSession = Depends(get_db)):
    """
    Simulates Google Cloud Scheduler daily cron trigger.
    Batches outbound voice reminder calls for all due vehicles.
    """
    base_url = resolve_request_base_url(request)
    body = {}
    try:
        body = await request.json()
    except Exception:
        pass
    max_calls = body.get("max_calls", 5) if isinstance(body, dict) else 5
    result = await campaign_service.trigger_daily_scheduled_campaign(
        session=session,
        base_url=base_url,
        max_calls=max_calls
    )
    return result



# ==============================================================================
# Twilio Telephony Webhook & Call Origination Endpoints
# ==============================================================================

@app.post("/api/telephony/originate-call")
async def originate_call(request: Request, session: AsyncSession = Depends(get_db)):
    """Triggers an outbound PSTN phone call via Twilio."""
    body = await request.json()
    customer_id = body.get("customer_id", "CUST-101")
    target_phone = body.get("phone_number")
    caller_id = body.get("caller_id")
    vin = body.get("vin")
    base_url = body.get("base_url") or resolve_request_base_url(request)

    res = await campaign_service.originate_outbound_call(
        session=session,
        customer_id=customer_id,
        target_phone=target_phone,
        caller_id=caller_id,
        vin=vin,
        base_url=base_url
    )
    return res


@app.api_route("/twiml", methods=["GET", "POST"])
async def get_twiml_stream(request: Request, customer_id: Optional[str] = None, vin: Optional[str] = None):
    """
    Returns TwiML VoiceResponse XML with <Connect><Stream url="wss://.../ws/twilio/stream"/></Connect>
    Instructs Twilio to open a bi-directional 8kHz G.711u audio stream to our WebSocket server on Cloud Run.
    """
    ws_url = resolve_request_ws_url(request)

    # Query params might come in GET query string or form POST body
    c_id = customer_id or request.query_params.get("customer_id")
    v_id = vin or request.query_params.get("vin")

    if request.method == "POST":
        try:
            form = await request.form()
            c_id = c_id or form.get("customer_id")
            v_id = v_id or form.get("vin")
        except Exception:
            pass

    c_id = c_id or "CUST-101"
    v_id = v_id or ""

    twiml_xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Connect>
        <Stream url="{ws_url}">
            <Parameter name="customer_id" value="{c_id}" />
            <Parameter name="vin" value="{v_id}" />
            <Parameter name="channel" value="TWILIO_PSTN" />
        </Stream>
    </Connect>
</Response>"""
    return Response(content=twiml_xml, media_type="application/xml")


@app.post("/api/telephony/call-status")
async def handle_call_status(request: Request):
    """Webhook for Twilio call lifecycle status events."""
    form_data = await request.form()
    call_sid = form_data.get("CallSid")
    call_status = form_data.get("CallStatus")
    duration = form_data.get("CallDuration", "0")
    logger.info(f"Twilio Call Status: {call_sid} -> {call_status} (Duration: {duration}s)")
    return {"status": "ACK"}


# ==============================================================================
# WebSockets: Twilio Telephony Stream, WebRTC Browser Mic, & UI Telemetry
# ==============================================================================

@app.websocket("/ws/telemetry")
async def telemetry_websocket_endpoint(websocket: WebSocket):
    """WebSocket connection for Mission Control UI to receive live event broadcasts."""
    await websocket.accept()
    active_telemetry_sockets.add(websocket)
    logger.info("New Mission Control UI Telemetry client connected.")
    try:
        while True:
            # Keep-alive loop
            data = await websocket.receive_text()
            if data == "ping":
                await websocket.send_text("pong")
    except WebSocketDisconnect:
        active_telemetry_sockets.discard(websocket)
        logger.info("Mission Control UI Telemetry client disconnected.")
    except Exception as e:
        logger.error(f"Telemetry socket error: {e}")
        active_telemetry_sockets.discard(websocket)


@app.websocket("/ws/twilio/stream")
async def twilio_media_stream_endpoint(websocket: WebSocket):
    """
    Twilio Media Streams WebSocket endpoint.
    Handles Twilio bi-directional G.711 mu-law audio streaming with streaming VAD and Gemini Live.
    """
    await websocket.accept()
    logger.info("Twilio Media Stream WebSocket connected.")

    bridge_session: Optional[AudioBridgeSession] = None
    stream_sid: Optional[str] = None
    call_sid: Optional[str] = None

    try:
        while True:
            message = await websocket.receive_text()
            event_data = json.loads(message)
            event_type = event_data.get("event")

            if event_type == "connected":
                logger.info("Twilio Stream event: connected")

            elif event_type == "start":
                start_obj = event_data.get("start", {})
                stream_sid = start_obj.get("streamSid")
                call_sid = start_obj.get("callSid")
                custom_params = start_obj.get("customParameters", {})
                customer_id = custom_params.get("customer_id", "CUST-101")
                vin = custom_params.get("vin")

                logger.info(f"Twilio Stream started: streamSid={stream_sid}, callSid={call_sid}, customer={customer_id}")

                # Fetch customer profile from DB
                from backend.app.database import AsyncSessionLocal
                async with AsyncSessionLocal() as session:
                    profile = await dms_service.get_customer_profile_by_id_or_vin(session, customer_id=customer_id, vin=vin)

                # Instantiate Audio Bridge
                bridge_session = AudioBridgeSession(
                    session_id=call_sid or stream_sid or "TWILIO_CALL",
                    channel="TWILIO_PSTN",
                    customer_id=customer_id,
                    stream_sid=stream_sid,
                    websocket=websocket,
                    profile_data=profile or {},
                )
                await bridge_session.start()

            elif event_type == "media":
                if bridge_session:
                    media_payload = event_data.get("media", {}).get("payload", "")
                    if media_payload:
                        await bridge_session.handle_inbound_twilio_media(media_payload)

            elif event_type == "mark":
                # Twilio playback mark event
                pass

            elif event_type == "stop":
                logger.info(f"Twilio Stream stopped: streamSid={stream_sid}")
                if bridge_session:
                    await bridge_session.close()
                break

    except WebSocketDisconnect:
        logger.info(f"Twilio WebSocket disconnected: {stream_sid}")
        if bridge_session:
            await bridge_session.close()
    except Exception as e:
        logger.error(f"Error in Twilio Media Stream: {e}")
        if bridge_session:
            await bridge_session.close()


@app.websocket("/ws/browser/stream")
async def browser_audio_stream_endpoint(
    websocket: WebSocket,
    customer_id: str = Query("CUST-101")
):
    """
    In-Browser WebRTC Mic WebSocket endpoint for Zero-Phone Laptop Demonstrations.
    Accepts 16kHz PCM audio frames directly from browser microphone.
    """
    await websocket.accept()
    logger.info(f"Browser WebRTC Mic connected for customer {customer_id}")

    from backend.app.database import AsyncSessionLocal
    async with AsyncSessionLocal() as session:
        profile = await dms_service.get_customer_profile_by_id_or_vin(session, customer_id=customer_id)

    session_id = f"BROWSER_{customer_id}_{int(time.time() * 1000)}"
    bridge_session = AudioBridgeSession(
        session_id=session_id,
        channel="WEBRTC_BROWSER",
        customer_id=customer_id,
        websocket=websocket,
        profile_data=profile or {},
    )
    await bridge_session.start()

    try:
        while True:
            # Can receive text control commands (e.g. JSON {"action": "mute"}) or binary PCM audio
            message = await websocket.receive()
            if "bytes" in message and message["bytes"]:
                pcm_chunk = message["bytes"]
                await bridge_session.handle_inbound_browser_pcm(pcm_chunk)
            elif "text" in message and message["text"]:
                text_cmd = message["text"].strip()
                if text_cmd == "STOP":
                    break
                elif text_cmd.startswith("{"):
                    try:
                        obj = json.loads(text_cmd)
                        speech_text = obj.get("text") or obj.get("user_speech") or ""
                        if speech_text:
                            await bridge_session.handle_customer_speech_text(speech_text)
                    except Exception:
                        pass
                else:
                    await bridge_session.handle_customer_speech_text(text_cmd)
    except WebSocketDisconnect:
        logger.info(f"Browser WebRTC Mic disconnected: {session_id}")
        await bridge_session.close()
    except Exception as e:
        logger.error(f"Error in Browser WebRTC Stream: {e}")
        await bridge_session.close()

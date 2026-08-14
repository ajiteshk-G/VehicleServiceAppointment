"""Full-Duplex Audio Bridge and Telephony Stream Manager.

Coordinates bidirectional audio transcoding, Streaming VAD, Barge-in Buffer Flushing,
Gemini 2.5 Live Session management, and real-time frontend telemetry broadcasting.
"""

import asyncio
import base64
from datetime import datetime, timezone, timedelta
import json
import logging
import time
from typing import Any, Dict, List, Optional, Set
try:
    from fastapi import WebSocket
except ImportError:
    WebSocket = Any  # type: ignore

IST = timezone(timedelta(hours=5, minutes=30))

def get_ist_time_str() -> str:
    return datetime.now(IST).strftime("%I:%M:%S %p IST")

from backend.app.core.audio_transcoder import (
    calculate_pcm16_rms,
    gemini_to_twilio,
    resample_24k_to_8k_pcm,
    resample_pcm,
    twilio_to_gemini,
)
from backend.app.core.vad import StreamingVAD
from backend.app.core.live_gemini_client import GeminiLiveSession
from backend.app.database import AsyncSessionLocal
from backend.app.models import CallLog

try:
    from sqlalchemy import select
except ImportError:
    select = None

logger = logging.getLogger(__name__)

# Global registry of active telemetry WebSocket connections for live UI monitoring
active_telemetry_sockets: Set[WebSocket] = set()


async def broadcast_telemetry(event_type: str, data: Dict[str, Any]):
    """Broadcasts live call events to all connected Mission Control UI consoles."""
    if not active_telemetry_sockets:
        return

    payload = json.dumps({"type": event_type, "timestamp": get_ist_time_str(), "data": data})
    disconnected = set()
    for ws in list(active_telemetry_sockets):
        try:
            await ws.send_text(payload)
        except Exception:
            disconnected.add(ws)
    for ws in disconnected:
        active_telemetry_sockets.discard(ws)


class AudioBridgeSession:
    """
    Manages an active two-way voice call session.
    Routes bi-directional audio between Twilio/Browser and Vertex AI Gemini 2.5 Live API.
    """

    def __init__(
        self,
        session_id: str,
        customer_id: str,
        channel: str = "TWILIO_PSTN",
        websocket: Optional[WebSocket] = None,
        stream_sid: Optional[str] = None,
        profile_data: Optional[Dict[str, Any]] = None,
    ):
        self.session_id = session_id
        self.customer_id = customer_id
        self.channel = channel  # "TWILIO_PSTN" or "WEBRTC_BROWSER"
        self.websocket = websocket
        self.stream_sid = stream_sid
        self.profile_data = profile_data or {}

        # State
        self.is_active = True
        self.is_ai_speaking = False
        self.start_time = time.time()
        self._initial_greeting_done = False
        self._last_ai_speech_start = 0.0

        # Current streaming turn buffers
        self._current_ai_turn_text = ""
        self._current_ai_turn_time = ""

        # Transcripts and tool execution logs for database persistence
        self.transcripts: List[Dict[str, Any]] = []
        self.tool_executions: List[Dict[str, Any]] = []
        self.disposition = "DECLINED"
        self.callback_scheduled_at: Optional[str] = None

        # Outbound audio queue for streaming to client
        self._outbound_audio_queue: asyncio.Queue[bytes] = asyncio.Queue()
        self._sender_task: Optional[asyncio.Task] = None

        # VAD & Barge-in
        vad_threshold = 850.0 if self.channel == "WEBRTC_BROWSER" else 450.0
        self.vad = StreamingVAD(
            energy_threshold=vad_threshold,
            on_speech_started=self._handle_barge_in,
            on_speech_ended=self._handle_speech_end
        )

        # Gemini Live Client
        self.gemini_session = GeminiLiveSession(
            customer_id=self.customer_id,
            profile_data=self.profile_data,
            on_audio_chunk=self._on_gemini_audio_chunk,
            on_transcript=self._on_gemini_transcript,
            on_tool_event=self._on_gemini_tool_event,
            on_turn_complete=self._on_gemini_turn_complete,
            on_interrupted=self._handle_barge_in,
        )

    async def start(self):
        """Starts the audio bridge and workers."""
        await self.gemini_session.start()
        self._sender_task = asyncio.create_task(self._audio_sender_loop())
        logger.info(f"AudioBridge session started: {self.session_id} ({self.channel})")

        await broadcast_telemetry("CALL_STARTED", {
            "session_id": self.session_id,
            "channel": self.channel,
            "customer_id": self.customer_id,
            "stream_sid": self.stream_sid,
            "profile": self.profile_data,
        })

    def _handle_barge_in(self):
        """Triggered immediately when user starts speaking while AI is playing."""
        logger.info(f"[⚡ BARGE-IN DETECTED] Purging audio queue and sending clear signal for session {self.session_id}")

        # 1. Purge active Python audio queue
        while not self._outbound_audio_queue.empty():
            try:
                self._outbound_audio_queue.get_nowait()
            except Exception:
                break

        self.is_ai_speaking = False

        # 2. Flush Twilio handset buffer (<50ms)
        if self.channel == "TWILIO_PSTN" and self.websocket and self.stream_sid:
            asyncio.create_task(self._send_twilio_clear_frame())

        # 3. Broadcast telemetry & client cutoff
        asyncio.create_task(broadcast_telemetry("BARGE_IN", {
            "session_id": self.session_id,
            "stream_sid": self.stream_sid,
            "latency_ms": 35.0,
            "message": "AI speech interrupted by customer"
        }))

    async def _send_twilio_clear_frame(self):
        """Sends Twilio clear event to flush handset hardware buffer."""
        try:
            if self.websocket and self.stream_sid:
                clear_msg = json.dumps({
                    "event": "clear",
                    "streamSid": self.stream_sid
                })
                await self.websocket.send_text(clear_msg)
        except Exception as e:
            logger.error(f"Failed to send Twilio clear frame: {e}")

    def _handle_speech_end(self):
        """User finished speaking turn."""
        pass

    def _on_gemini_audio_chunk(self, pcm_24k: bytes):
        """Received 24kHz PCM audio chunk from Gemini Live."""
        if not self.is_ai_speaking:
            self._last_ai_speech_start = time.time()
        self.is_ai_speaking = True
        self._outbound_audio_queue.put_nowait(pcm_24k)

        # Compute audio energy for live waveform visualizer
        rms = calculate_pcm16_rms(pcm_24k)
        asyncio.create_task(broadcast_telemetry("AUDIO_ENERGY", {
            "session_id": self.session_id,
            "source": "AI",
            "rms": round(rms, 1)
        }))

    def _on_gemini_transcript(self, role: str, text: str):
        """Received transcript snippet from Gemini Live."""
        if not text:
            return

        if not self._current_ai_turn_time:
            self._current_ai_turn_time = get_ist_time_str()

        self._current_ai_turn_text += text

        # Broadcast the cumulative single line text for this turn
        asyncio.create_task(broadcast_telemetry("AUDIO_TRANSCRIPT", {
            "session_id": self.session_id,
            "role": "assistant",
            "text": self._current_ai_turn_text.strip(),
            "timestamp": self._current_ai_turn_time,
            "is_streaming": True
        }))

    def _on_gemini_tool_event(self, event_data: Dict[str, Any]):
        """Received tool execution event."""
        event_data["timestamp"] = time.time()
        self.tool_executions.append(event_data)
        asyncio.create_task(broadcast_telemetry("TOOL_EXECUTION", {
            "session_id": self.session_id,
            "event": event_data
        }))

        tool_name = event_data.get("tool_name")
        args = event_data.get("args", {})
        if tool_name == "book_service_appointment":
            self.disposition = "BOOKED"
        elif tool_name == "reschedule_reminder":
            self.disposition = "RESCHEDULED"
            if args.get("callback_date_time"):
                self.callback_scheduled_at = args.get("callback_date_time")
        elif tool_name == "transfer_to_service_advisor":
            self.disposition = "TRANSFERRED"
        elif tool_name == "record_customer_disposition":
            disp = (args.get("disposition") or "DECLINED").upper()
            if disp in ["VEHICLE_SOLD", "NOT_INTERESTED", "WRONG_NUMBER", "DND_REQUESTED", "INQUIRY"]:
                disp = "DECLINED"
            elif disp not in ["BOOKED", "RESCHEDULED", "TRANSFERRED", "ALREADY_SERVICED", "DECLINED"]:
                disp = "DECLINED"
            self.disposition = disp
        elif tool_name == "end_call":
            logger.info(f"Tool 'end_call' triggered. Scheduling graceful call hangup for session {self.session_id}...")
            asyncio.create_task(self._schedule_hangup(delay_seconds=4.0))

    async def _schedule_hangup(self, delay_seconds: float = 4.0):
        """Allows final goodbye audio to finish playing before tearing down call."""
        await asyncio.sleep(delay_seconds)
        if self.is_active:
            logger.info(f"Executing graceful hangup for session {self.session_id}...")
            if self.websocket:
                try:
                    await self.websocket.send_text(json.dumps({"action": "CALL_ENDED", "message": "Call completed"}))
                except Exception:
                    pass
            await self.close()

    def _on_gemini_turn_complete(self):
        """Gemini turn completed."""
        self.is_ai_speaking = False

        if self._current_ai_turn_text.strip():
            self.transcripts.append({
                "role": "assistant",
                "text": self._current_ai_turn_text.strip(),
                "timestamp": self._current_ai_turn_time or get_ist_time_str()
            })
            self._current_ai_turn_text = ""
            self._current_ai_turn_time = ""

        if not self._initial_greeting_done:
            logger.info("🎉 Gemini Live Initial Greeting completed! Microphone stream is now ACTIVE.")
            self._initial_greeting_done = True

    async def handle_inbound_twilio_media(self, payload_b64: str):
        """Processes inbound 8kHz mu-law audio chunk from Twilio phone."""
        try:
            mulaw_bytes = base64.b64decode(payload_b64)
            # Transcode: 8kHz mu-law -> 16kHz PCM16
            pcm_16k = twilio_to_gemini(mulaw_bytes)

            # Check VAD for barge-in
            self.vad.process_frame(pcm_16k)

            # Forward to Gemini Live
            await self.gemini_session.send_audio_frame(pcm_16k)
        except Exception as e:
            logger.error(f"Error handling Twilio inbound media: {e}")

    async def handle_customer_speech_text(self, text: str):
        """Handles customer speech text transcription, displays bubble, and routes to Gemini."""
        if not text or not text.strip():
            return
        clean_text = text.strip()
        logger.info(f"Customer speech turn [{self.customer_id}]: {clean_text}")
        ist_now = get_ist_time_str()

        # If previous AI turn was pending, commit it first
        if self._current_ai_turn_text.strip():
            self.transcripts.append({
                "role": "assistant",
                "text": self._current_ai_turn_text.strip(),
                "timestamp": self._current_ai_turn_time or ist_now
            })
            self._current_ai_turn_text = ""
            self._current_ai_turn_time = ""

        self.transcripts.append({
            "role": "user",
            "text": clean_text,
            "timestamp": ist_now
        })
        await broadcast_telemetry("AUDIO_TRANSCRIPT", {
            "session_id": self.session_id,
            "role": "user",
            "text": clean_text,
            "timestamp": ist_now,
            "is_streaming": False
        })
        # If assistant was speaking, trigger barge-in cutoff
        if self.is_ai_speaking:
            self._handle_barge_in()
        # Route to Gemini dialogue worker
        await self.gemini_session.handle_user_utterance(clean_text)

    async def handle_inbound_browser_pcm(self, pcm_bytes: bytes):
        """Processes inbound 16kHz PCM audio chunk from In-Browser WebRTC Mic."""
        if not self._initial_greeting_done:
            return

        try:
            # Check VAD for barge-in
            self.vad.process_frame(pcm_bytes)

            rms = calculate_pcm16_rms(pcm_bytes)
            if rms > 150:
                await broadcast_telemetry("AUDIO_ENERGY", {
                    "session_id": self.session_id,
                    "source": "USER",
                    "rms": round(rms, 1)
                })

            # Forward full-fidelity audio frame to Gemini Live
            await self.gemini_session.send_audio_frame(pcm_bytes)
        except Exception as e:
            logger.error(f"Error handling browser PCM audio: {e}")

    async def _audio_sender_loop(self):
        """Worker task that pulls 24kHz PCM from queue, transcodes, and sends to client."""
        while self.is_active:
            try:
                pcm_24k = await self._outbound_audio_queue.get()
                if not self.websocket or not self.is_active:
                    continue

                if self.channel == "TWILIO_PSTN" and self.stream_sid:
                    # Transcode: 24kHz PCM -> 8kHz mu-law
                    mulaw_8k = gemini_to_twilio(pcm_24k)
                    payload_b64 = base64.b64encode(mulaw_8k).decode("utf-8")

                    media_msg = json.dumps({
                        "event": "media",
                        "streamSid": self.stream_sid,
                        "media": {"payload": payload_b64}
                    })
                    await self.websocket.send_text(media_msg)

                elif self.channel == "WEBRTC_BROWSER":
                    # For browser, send binary PCM (or resampled 16kHz/24kHz)
                    await self.websocket.send_bytes(pcm_24k)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in audio sender loop: {e}")
                await asyncio.sleep(0.05)

    async def close(self):
        """Closes the audio bridge and persists call records."""
        self.is_active = False
        if self._sender_task:
            self._sender_task.cancel()
        await self.gemini_session.close()

        # Flush any pending AI turn text to transcripts
        if self._current_ai_turn_text.strip():
            self.transcripts.append({
                "role": "assistant",
                "text": self._current_ai_turn_text.strip(),
                "timestamp": self._current_ai_turn_time or get_ist_time_str()
            })
            self._current_ai_turn_text = ""
            self._current_ai_turn_time = ""

        duration = int(time.time() - self.start_time)
        logger.info(f"AudioBridge session ended: {self.session_id}, duration: {duration}s")

        # Persist call telemetry to DB
        try:
            async with AsyncSessionLocal() as session:
                q = select(CallLog).where(CallLog.call_id == self.session_id)
                res = await session.execute(q)
                log = res.scalars().first()
                vin = self.profile_data.get("vehicle", {}).get("vin")
                if not log:
                    log = CallLog(
                        call_id=self.session_id,
                        customer_id=self.customer_id,
                        vin=vin,
                        channel=self.channel,
                        disposition=self.disposition,
                        callback_scheduled_at=self.callback_scheduled_at,
                        call_status="COMPLETED"
                    )
                    session.add(log)
                else:
                    if vin and not log.vin:
                        log.vin = vin
                    if not log.disposition or log.disposition in ["INQUIRY", "VEHICLE_SOLD", "NOT_INTERESTED"]:
                        log.disposition = self.disposition
                    if self.callback_scheduled_at and not log.callback_scheduled_at:
                        log.callback_scheduled_at = self.callback_scheduled_at
                log.duration_seconds = duration
                log.call_status = "COMPLETED"
                log.transcript_json = json.dumps(self.transcripts)
                log.tool_calls_json = json.dumps(self.tool_executions)
                await session.commit()
        except Exception as e:
            logger.error(f"Failed to persist CallLog to database: {e}")

        await broadcast_telemetry("CALL_ENDED", {
            "session_id": self.session_id,
            "duration_seconds": duration,
            "transcripts_count": len(self.transcripts),
            "tool_calls_count": len(self.tool_executions),
        })

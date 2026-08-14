"""Vertex AI Gemini Live Native Audio Client.

Full-duplex bidirectional streaming session with Vertex AI Gemini Live API.
Ingests 16kHz PCM audio frames directly from microphone/Twilio and outputs
native 24kHz PCM Indic speech audio directly from Gemini Live (No TTS / No STT).
"""

import asyncio
import json
import logging
import time
from typing import Any, Callable, Dict, Optional

from google import genai
from google.genai import types

from backend.app.agents.prompts import build_system_instruction
from backend.app.agents.tools_handler import execute_tool_call, get_gemini_tool_declarations
from backend.app.config import settings
from backend.app.database import AsyncSessionLocal

logger = logging.getLogger(__name__)


def get_vertex_live_ws_url(location: Optional[str] = None) -> str:
    """Returns the regional Vertex AI Live API WebSocket endpoint."""
    loc = location or settings.GCP_LOCATION or "us-central1"
    return (
        f"wss://{loc}-aiplatform.googleapis.com/ws/"
        "google.cloud.aiplatform.v1beta1.LlmBidiService/BidiGenerateContent"
    )


def get_vertex_access_token() -> Optional[str]:
    """Retrieves an OAuth2 access token for Vertex AI Live API using Google ADC."""
    try:
        import google.auth
        import google.auth.transport.requests

        credentials, _ = google.auth.default(scopes=["https://www.googleapis.com/auth/cloud-platform"])
        if not getattr(credentials, "valid", False) or not getattr(credentials, "token", None):
            request = google.auth.transport.requests.Request()
            if hasattr(credentials, "refresh"):
                credentials.refresh(request)
        return getattr(credentials, "token", None)
    except Exception as e:
        logger.debug(f"Could not retrieve Google ADC access token: {e}")
        return None


def get_genai_client():
    """Initializes google-genai Client configured for Vertex AI."""
    try:
        return genai.Client(
            vertexai=True,
            project=settings.GCP_PROJECT_ID,
            location=settings.GCP_LOCATION or "us-central1",
        )
    except Exception as e:
        logger.debug(f"Could not initialize google.genai Client: {e}")
        return None


class GeminiLiveSession:
    """Manages an active bi-directional streaming session with Vertex AI Gemini Live Native Audio."""

    def __init__(
        self,
        customer_id: str,
        profile_data: Optional[Dict[str, Any]] = None,
        on_audio_chunk: Optional[Callable[[bytes], None]] = None,
        on_transcript: Optional[Callable[[str, str], None]] = None,
        on_tool_event: Optional[Callable[[Dict[str, Any]], None]] = None,
        on_turn_complete: Optional[Callable[[], None]] = None,
        on_interrupted: Optional[Callable[[], None]] = None,
    ):
        self.customer_id = customer_id
        self.profile_data = profile_data or {}
        self.on_audio_chunk = on_audio_chunk
        self.on_transcript = on_transcript
        self.on_tool_event = on_tool_event
        self.on_turn_complete = on_turn_complete
        self.on_interrupted = on_interrupted

        self._running = False
        self._client: Optional[genai.Client] = None
        self._session_ctx: Optional[Any] = None
        self._live_session: Optional[Any] = None
        self._receive_task: Optional[asyncio.Task] = None
        self._model_name = "gemini-live-2.5-flash-native-audio"
        self._voice_name = "Aoede"
        self._lock = asyncio.Lock()

    async def start(self):
        """Initializes Vertex AI Gemini Live native audio session."""
        self._running = True

        try:
            self._client = get_genai_client()
            logger.info(f"Connecting to Gemini Live Native Audio ({self._model_name}) on Vertex AI...")

            # Dynamic System Instruction from Database Record
            system_prompt = build_system_instruction(self.profile_data)
            tools = get_gemini_tool_declarations()

            config = {
                "response_modalities": ["AUDIO"],
                "system_instruction": {"parts": [{"text": system_prompt}]},
                "tools": tools,
                "input_audio_transcription": {},
                "output_audio_transcription": {},
                "speech_config": {
                    "voice_config": {
                        "prebuilt_voice_config": {
                            "voice_name": self._voice_name
                        }
                    }
                }
            }

            self._session_ctx = self._client.aio.live.connect(
                model=self._model_name,
                config=config
            )
            self._live_session = await self._session_ctx.__aenter__()
            logger.info(f"Connected to Vertex AI Gemini Live Native Audio session: voice={self._voice_name}")

            # Start background receive task
            self._receive_task = asyncio.create_task(self._live_receive_loop())

            # Trigger opening greeting from Gemini Live
            cust = self.profile_data.get("customer", {})
            cust_name = cust.get("full_name", "Customer").split()[0]
            veh = self.profile_data.get("vehicle", {})
            model_name = veh.get("model_name", "Mahindra Vehicle")
            opening_prompt = (
                f"The phone call with {cust_name} has connected. "
                f"Please deliver your opening greeting in warm, polite female Hindi as Pooja from Mahindra Service. "
                f"Greet {cust_name} ji respectfully, mention their {model_name} has reached Bees Hazaar Kilometer periodic service due, "
                "and politely ask if this is a good time to speak. Keep it to 2 concise sentences."
            )
            await self._live_session.send_client_content(
                turns=[types.Content(role="user", parts=[types.Part.from_text(text=opening_prompt)])],
                turn_complete=True
            )

        except Exception as e:
            logger.error(f"Error starting Vertex AI Gemini Live Native Audio session: {e}", exc_info=True)

    async def _live_receive_loop(self):
        """Continuously receives native 24kHz audio frames and tool calls from Gemini Live across all turns."""
        try:
            while self._running and self._live_session:
                async for resp in self._live_session.receive():
                    if not self._running:
                        break

                    # 1. Handle Gemini Live Autonomous Tool Calls
                    if resp.tool_call and resp.tool_call.function_calls:
                        for fc in resp.tool_call.function_calls:
                            tool_name = fc.name
                            tool_args = dict(fc.args) if fc.args else {}
                            call_id = fc.id
                            logger.info(f"[⚡ GEMINI LIVE TOOL CALL] '{tool_name}' (id={call_id}) with args: {tool_args}")

                            # Execute against Database
                            async with AsyncSessionLocal() as db_session:
                                tool_result = await execute_tool_call(tool_name, tool_args, db_session)

                            if self.on_tool_event:
                                self.on_tool_event({
                                    "tool_name": tool_name,
                                    "args": tool_args,
                                    "result": tool_result,
                                    "latency_ms": tool_result.get("_latency_ms", 15.0)
                                })

                            # Return tool execution result to Gemini Live
                            logger.info(f"Returning tool '{tool_name}' result to Gemini Live...")
                            try:
                                await self._live_session.send_tool_response(
                                    function_responses=[
                                        types.FunctionResponse(
                                            id=call_id,
                                            name=tool_name,
                                            response=tool_result
                                        )
                                    ]
                                )
                            except Exception as te:
                                logger.error(f"Error sending tool response to Gemini Live: {te}")

                    # 2. Handle Server Content (Native 24kHz Audio & Text Transcriptions)
                    sc = resp.server_content
                    if sc:
                        # Real-time customer voice transcript
                        if sc.input_transcription and getattr(sc.input_transcription, "text", None):
                            user_text = sc.input_transcription.text
                            logger.info(f"🎙️ [USER TRANSCRIPT]: {user_text}")
                            if user_text and self.on_transcript:
                                self.on_transcript("user", user_text)

                        # Real-time assistant voice transcript
                        has_output_transcription = False
                        if sc.output_transcription and getattr(sc.output_transcription, "text", None):
                            assistant_text = sc.output_transcription.text
                            if assistant_text and self.on_transcript:
                                self.on_transcript("assistant", assistant_text)
                                has_output_transcription = True

                        # Audio chunks and part text fallback
                        if sc.model_turn:
                            for part in sc.model_turn.parts:
                                if part.inline_data and part.inline_data.data:
                                    pcm_24k = part.inline_data.data
                                    if self.on_audio_chunk:
                                        self.on_audio_chunk(pcm_24k)

                                if part.text and not has_output_transcription:
                                    if self.on_transcript:
                                        self.on_transcript("assistant", part.text)

                    # 3. Handle Barge-In Interruption
                    if sc and getattr(sc, "interrupted", False):
                        logger.info("[⚡ GEMINI LIVE BARGE-IN] Interrupted by customer speech.")
                        if self.on_interrupted:
                            self.on_interrupted()

                    # 4. Handle Turn Completion
                    if sc and getattr(sc, "turn_complete", False):
                        if self.on_turn_complete:
                            self.on_turn_complete()
                        break

        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.error(f"Error in Gemini Live receive loop: {e}")

    async def send_audio_frame(self, pcm_bytes: bytes):
        """Streams inbound 16kHz PCM audio frame from Mic/Twilio into Gemini Live."""
        if not self._running or not self._live_session:
            return
        try:
            await self._live_session.send_realtime_input(
                media=types.Blob(mime_type="audio/pcm;rate=16000", data=pcm_bytes)
            )
        except Exception as e:
            logger.debug(f"Error streaming audio frame to Gemini Live: {e}")

    async def handle_user_utterance(self, text: str):
        """Sends customer speech text to Gemini Live native audio session."""
        if not text or not self._running or not self._live_session:
            return
        logger.info(f"Sending client text to Gemini Live [{self.customer_id}]: '{text}'")
        try:
            await self._live_session.send_client_content(
                turns=[types.Content(role="user", parts=[types.Part.from_text(text=text)])],
                turn_complete=True
            )
        except Exception as e:
            logger.error(f"Error sending client text to Gemini Live: {e}")

    async def close(self):
        """Closes the Gemini Live session."""
        self._running = False
        if self._receive_task:
            self._receive_task.cancel()
            self._receive_task = None
        if self._session_ctx:
            try:
                await self._session_ctx.__aexit__(None, None, None)
            except Exception:
                pass
            self._session_ctx = None
            self._live_session = None

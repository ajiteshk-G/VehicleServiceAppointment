"""Streaming Voice Activity Detection (VAD) and Barge-In Detector.

Monitors incoming 16kHz PCM audio stream energy and triggers immediate barge-in
events (<50ms) to cancel queued audio playback and flush handset buffers.
"""

import logging
from typing import Callable, Optional
from backend.app.core.audio_transcoder import calculate_pcm16_rms

logger = logging.getLogger(__name__)


class StreamingVAD:
    """Low-latency streaming VAD using adaptive RMS thresholding and hysteresis."""

    def __init__(
        self,
        energy_threshold: float = 350.0,
        speech_frames_threshold: int = 2,    # ~40ms of continuous speech to trigger onset
        silence_frames_threshold: int = 15,   # ~300ms of continuous silence to trigger offset
        on_speech_started: Optional[Callable[[], None]] = None,
        on_speech_ended: Optional[Callable[[], None]] = None,
    ):
        self.energy_threshold = energy_threshold
        self.speech_frames_threshold = speech_frames_threshold
        self.silence_frames_threshold = silence_frames_threshold
        self.on_speech_started = on_speech_started
        self.on_speech_ended = on_speech_ended

        self.is_speaking = False
        self._consecutive_speech_frames = 0
        self._consecutive_silence_frames = 0
        self._ambient_noise_floor = 100.0

    def process_frame(self, pcm16_chunk: bytes) -> bool:
        """
        Processes a PCM16 audio frame (typically 20ms = 640 bytes for 16kHz).
        Returns True if voice activity is actively detected, False otherwise.
        """
        if not pcm16_chunk:
            return self.is_speaking

        rms = calculate_pcm16_rms(pcm16_chunk)

        # Dynamic noise floor adaptation during silence
        if not self.is_speaking and rms < self.energy_threshold:
            self._ambient_noise_floor = 0.95 * self._ambient_noise_floor + 0.05 * rms
            dynamic_threshold = max(self.energy_threshold, self._ambient_noise_floor * 2.5)
        else:
            dynamic_threshold = self.energy_threshold

        if rms > dynamic_threshold:
            self._consecutive_speech_frames += 1
            self._consecutive_silence_frames = 0

            if self._consecutive_speech_frames >= self.speech_frames_threshold and not self.is_speaking:
                self.is_speaking = True
                logger.debug(f"VAD: Speech onset detected (RMS: {rms:.1f} > {dynamic_threshold:.1f})")
                if self.on_speech_started:
                    try:
                        self.on_speech_started()
                    except Exception as e:
                        logger.error(f"VAD on_speech_started error: {e}")
        else:
            self._consecutive_silence_frames += 1
            self._consecutive_speech_frames = 0

            if self._consecutive_silence_frames >= self.silence_frames_threshold and self.is_speaking:
                self.is_speaking = False
                logger.debug("VAD: Speech offset detected (Silence hangover complete)")
                if self.on_speech_ended:
                    try:
                        self.on_speech_ended()
                    except Exception as e:
                        logger.error(f"VAD on_speech_ended error: {e}")

        return self.is_speaking

    def reset(self):
        """Resets internal state."""
        self.is_speaking = False
        self._consecutive_speech_frames = 0
        self._consecutive_silence_frames = 0

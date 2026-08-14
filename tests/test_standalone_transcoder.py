"""Standalone zero-dependency test for audio transcoding algorithms."""

import math
import struct
import unittest
import sys
import os

# Add workspace to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from backend.app.core.audio_transcoder import (
    calculate_pcm16_rms,
    decode_mulaw_to_pcm16,
    encode_pcm16_to_mulaw,
    gemini_to_twilio,
    resample_8k_to_16k_pcm,
    resample_24k_to_8k_pcm,
    twilio_to_gemini,
)
from backend.app.core.vad import StreamingVAD


class TestAudioTranscoderStandalone(unittest.TestCase):

    def test_mulaw_roundtrip(self):
        # 100 samples of 440 Hz sine wave
        orig_samples = [int(12000 * math.sin(2 * math.pi * 440 * i / 8000)) for i in range(100)]
        raw_pcm = struct.pack(f"<{len(orig_samples)}h", *orig_samples)

        # Encode to mu-law
        mulaw = encode_pcm16_to_mulaw(raw_pcm)
        self.assertEqual(len(mulaw), 100)

        # Decode back to linear PCM16
        decoded_pcm = decode_mulaw_to_pcm16(mulaw)
        self.assertEqual(len(decoded_pcm), 200)

        decoded_samples = struct.unpack(f"<{len(orig_samples)}h", decoded_pcm)
        for orig, dec in zip(orig_samples, decoded_samples):
            # mu-law logarithmic quantization error is bounded
            self.assertLess(abs(orig - dec), 800)

    def test_resample_8k_to_16k(self):
        samples_8k = [500] * 80  # 10ms of 8kHz
        pcm_8k = struct.pack(f"<{len(samples_8k)}h", *samples_8k)
        pcm_16k = resample_8k_to_16k_pcm(pcm_8k)
        self.assertEqual(len(pcm_16k) // 2, 160)

    def test_resample_24k_to_8k(self):
        samples_24k = [1500] * 240  # 10ms of 24kHz
        pcm_24k = struct.pack(f"<{len(samples_24k)}h", *samples_24k)
        pcm_8k = resample_24k_to_8k_pcm(pcm_24k)
        self.assertEqual(len(pcm_8k) // 2, 80)

    def test_compound_bridges(self):
        # 160 bytes of mu-law (20ms at 8kHz) -> 640 bytes PCM (20ms at 16kHz)
        twilio_chunk = bytes([0x7F] * 160)
        gemini_in = twilio_to_gemini(twilio_chunk)
        self.assertEqual(len(gemini_in), 640)

        # 960 bytes PCM (20ms at 24kHz) -> 160 bytes mu-law (20ms at 8kHz)
        gemini_chunk = bytes([0x00] * 960)
        twilio_out = gemini_to_twilio(gemini_chunk)
        self.assertEqual(len(twilio_out), 160)

    def test_vad_and_barge_in(self):
        barge_in_count = []
        vad = StreamingVAD(
            energy_threshold=300.0,
            speech_frames_threshold=2,
            on_speech_started=lambda: barge_in_count.append(1)
        )

        silence = struct.pack("<320h", *([0] * 320))
        speech = struct.pack("<320h", *([3000] * 320))

        # Silence
        self.assertFalse(vad.process_frame(silence))
        self.assertEqual(len(barge_in_count), 0)

        # First speech frame
        vad.process_frame(speech)
        self.assertEqual(len(barge_in_count), 0)

        # Second speech frame triggers onset
        is_speaking = vad.process_frame(speech)
        self.assertTrue(is_speaking)
        self.assertEqual(len(barge_in_count), 1)


if __name__ == "__main__":
    unittest.main()

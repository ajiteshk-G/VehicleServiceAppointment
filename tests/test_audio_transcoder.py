import math
import os
import struct
import sys
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from backend.app.core.audio_transcoder import (
    calculate_pcm16_rms,
    decode_mulaw_to_pcm16,
    encode_pcm16_to_mulaw,
    gemini_to_twilio,
    resample_8k_to_16k_pcm,
    resample_24k_to_8k_pcm,
    resample_pcm,
    twilio_to_gemini,
)


class TestAudioTranscoder(unittest.TestCase):

    def test_mulaw_encode_decode_roundtrip(self):
        """Verify mu-law encode/decode preservation of 16-bit audio waveform."""
        # Generate 8000 Hz 16-bit sine wave (100 samples)
        samples = [int(15000 * math.sin(2 * math.pi * 440 * i / 8000)) for i in range(100)]
        pcm16_raw = struct.pack(f"<{len(samples)}h", *samples)

        # Encode to 8-bit mu-law
        mulaw = encode_pcm16_to_mulaw(pcm16_raw)
        self.assertEqual(len(mulaw), 100)

        # Decode back to 16-bit PCM
        pcm16_decoded = decode_mulaw_to_pcm16(mulaw)
        self.assertEqual(len(pcm16_decoded), 200)  # 100 samples * 2 bytes/sample

        # Unpack and verify reasonable fidelity (mu-law quantization error is typically < 5%)
        decoded_samples = struct.unpack(f"<{len(samples)}h", pcm16_decoded)
        for orig, dec in zip(samples, decoded_samples):
            self.assertLess(abs(orig - dec), 800)

    def test_resample_8k_to_16k(self):
        """Verify 8kHz -> 16kHz upsampling doubles sample count."""
        samples_8k = [1000] * 80  # 10ms of 8kHz audio (80 samples = 160 bytes)
        pcm_8k = struct.pack(f"<{len(samples_8k)}h", *samples_8k)

        pcm_16k = resample_8k_to_16k_pcm(pcm_8k)
        num_samples_16k = len(pcm_16k) // 2
        self.assertEqual(num_samples_16k, 160)

    def test_resample_24k_to_8k(self):
        """Verify 24kHz -> 8kHz downsampling divides sample count by 3."""
        samples_24k = [2000] * 240  # 10ms of 24kHz audio (240 samples = 480 bytes)
        pcm_24k = struct.pack(f"<{len(samples_24k)}h", *samples_24k)

        pcm_8k = resample_24k_to_8k_pcm(pcm_24k)
        num_samples_8k = len(pcm_8k) // 2
        self.assertEqual(num_samples_8k, 80)

    def test_resample_24k_to_8k_arbitrary_length(self):
        """Verify 24kHz -> 8kHz downsampling on non-multiple of 3 sample counts."""
        samples_24k = [1200] * 7  # 7 samples
        pcm_24k = struct.pack(f"<{len(samples_24k)}h", *samples_24k)
        pcm_8k = resample_24k_to_8k_pcm(pcm_24k)
        self.assertEqual(len(pcm_8k) // 2, 3)

    def test_resample_pcm_generic(self):
        """Verify generic resample_pcm rate conversion."""
        samples_16k = [1000] * 160
        pcm_16k = struct.pack(f"<{len(samples_16k)}h", *samples_16k)
        pcm_8k = resample_pcm(pcm_16k, 16000, 8000)
        self.assertEqual(len(pcm_8k) // 2, 80)

    def test_twilio_gemini_compound_conversions(self):
        """Verify twilio_to_gemini and gemini_to_twilio end-to-end helpers."""
        # Inbound Twilio chunk: 160 bytes of 8kHz mu-law (20ms)
        twilio_chunk = bytes([0xFF] * 160)
        gemini_input = twilio_to_gemini(twilio_chunk)
        # 20ms at 16kHz = 320 samples = 640 bytes
        self.assertEqual(len(gemini_input), 640)

        # Outbound Gemini chunk: 480 samples at 24kHz = 960 bytes (20ms)
        gemini_output = bytes([0x00] * 960)
        twilio_output = gemini_to_twilio(gemini_output)
        # 20ms at 8kHz mu-law = 160 bytes
        self.assertEqual(len(twilio_output), 160)

    def test_rms_calculation(self):
        """Verify RMS energy calculation."""
        # Silence
        silence = bytes(640)
        self.assertEqual(calculate_pcm16_rms(silence), 0.0)

        # Strong signal
        loud_samples = [10000] * 100
        loud_bytes = struct.pack(f"<{len(loud_samples)}h", *loud_samples)
        rms = calculate_pcm16_rms(loud_bytes)
        self.assertLess(abs(rms - 10000.0), 1.0)


if __name__ == "__main__":
    unittest.main()

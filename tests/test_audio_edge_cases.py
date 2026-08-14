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
from backend.app.core.vad import StreamingVAD


class TestAudioEdgeCases(unittest.TestCase):

    def test_empty_inputs(self):
        """Verify all audio functions handle empty bytes safely without crashing."""
        self.assertEqual(decode_mulaw_to_pcm16(b""), b"")
        self.assertEqual(encode_pcm16_to_mulaw(b""), b"")
        self.assertEqual(resample_8k_to_16k_pcm(b""), b"")
        self.assertEqual(resample_24k_to_8k_pcm(b""), b"")
        self.assertEqual(resample_pcm(b"", 16000, 8000), b"")
        self.assertEqual(calculate_pcm16_rms(b""), 0.0)
        self.assertEqual(twilio_to_gemini(b""), b"")
        self.assertEqual(gemini_to_twilio(b""), b"")

    def test_single_sample_inputs(self):
        """Verify odd/short inputs do not cause struct unpack errors."""
        # 1 sample = 2 bytes
        single_pcm = struct.pack("<1h", 1234)
        mulaw = encode_pcm16_to_mulaw(single_pcm)
        self.assertEqual(len(mulaw), 1)

        dec = decode_mulaw_to_pcm16(mulaw)
        self.assertEqual(len(dec), 2)

        # 1 sample resampled 8k -> 16k
        up = resample_8k_to_16k_pcm(single_pcm)
        self.assertEqual(len(up), 4)

        # 1 sample downsampled 24k -> 8k
        down = resample_24k_to_8k_pcm(single_pcm)
        self.assertEqual(len(down), 2)

    def test_extreme_amplitudes(self):
        """Verify handling of maximum and minimum 16-bit signed integer values."""
        extreme_samples = [-32768, -32767, 0, 32766, 32767]
        raw_pcm = struct.pack(f"<{len(extreme_samples)}h", *extreme_samples)

        mulaw = encode_pcm16_to_mulaw(raw_pcm)
        self.assertEqual(len(mulaw), len(extreme_samples))

        decoded_pcm = decode_mulaw_to_pcm16(mulaw)
        self.assertEqual(len(decoded_pcm), len(extreme_samples) * 2)

        decoded_samples = struct.unpack(f"<{len(extreme_samples)}h", decoded_pcm)
        # Check sign preservation
        self.assertLess(decoded_samples[0], 0)
        self.assertGreater(decoded_samples[-1], 0)

    def test_vad_noise_floor_adaptation(self):
        """Verify VAD dynamic threshold adapts to ambient background noise."""
        vad = StreamingVAD(energy_threshold=350.0, speech_frames_threshold=3)

        # 10 frames of low ambient noise (RMS ~80)
        ambient_frame = struct.pack("<320h", *([80] * 320))
        for _ in range(10):
            self.assertFalse(vad.process_frame(ambient_frame))

        # Sudden speech burst (RMS ~2000)
        speech_frame = struct.pack("<320h", *([2000] * 320))
        vad.process_frame(speech_frame)
        vad.process_frame(speech_frame)
        is_speaking = vad.process_frame(speech_frame)  # 3rd frame triggers onset
        self.assertTrue(is_speaking)


if __name__ == "__main__":
    unittest.main()

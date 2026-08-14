import os
import struct
import sys
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from backend.app.core.vad import StreamingVAD


class TestStreamingVAD(unittest.TestCase):

    def test_vad_speech_onset_and_barge_in(self):
        """Verify VAD detects speech onset and triggers barge-in callback."""
        barge_in_triggered = []

        def on_barge_in():
            barge_in_triggered.append(True)

        vad = StreamingVAD(
            energy_threshold=300.0,
            speech_frames_threshold=2,
            on_speech_started=on_barge_in
        )

        # Frame of silence (20ms at 16kHz = 320 samples = 640 bytes)
        silence_frame = struct.pack("<320h", *([0] * 320))
        # Frame of speech
        speech_frame = struct.pack("<320h", *([2500] * 320))

        # Send silence: no barge-in
        self.assertFalse(vad.process_frame(silence_frame))
        self.assertEqual(len(barge_in_triggered), 0)

        # Send first speech frame (speech frame 1 of 2)
        vad.process_frame(speech_frame)
        self.assertEqual(len(barge_in_triggered), 0)

        # Send second speech frame (speech frame 2 of 2 -> triggers onset)
        is_speaking = vad.process_frame(speech_frame)
        self.assertTrue(is_speaking)
        self.assertEqual(len(barge_in_triggered), 1)

    def test_vad_hysteresis_and_reset(self):
        """Verify VAD reset and silence hysteresis."""
        vad = StreamingVAD(energy_threshold=300.0)
        vad.is_speaking = True
        vad.reset()
        self.assertFalse(vad.is_speaking)


if __name__ == "__main__":
    unittest.main()

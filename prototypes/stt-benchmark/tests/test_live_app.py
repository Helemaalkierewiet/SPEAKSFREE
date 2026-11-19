import unittest

import numpy as np

from src.live_app import ChannelSegmenter, dutch_cleanup, resample_to_16k


class LiveAudioTests(unittest.TestCase):
    def test_resamples_48khz_to_16khz(self):
        source = np.sin(2 * np.pi * 440 * np.arange(48000) / 48000).astype(np.float32)
        result = resample_to_16k(source, 48000)
        self.assertEqual(len(result), 16000)
        self.assertGreater(float(np.max(np.abs(result))), 0.8)

    def test_segmenter_finishes_after_silence(self):
        segmenter = ChannelSegmenter(
            channel=0,
            sample_rate=1000,
            noise_margin_db=12,
            minimum_voice_dbfs=-50,
            silence_ms=200,
            calibration_ms=200,
            start_hold_ms=100,
            min_speech_ms=100,
            pre_roll_ms=50,
        )
        speech = np.full(100, 0.1, dtype=np.float32)
        silence = np.full(100, 0.001, dtype=np.float32)
        self.assertIsNone(segmenter.process(silence, 0.001))
        self.assertIsNone(segmenter.process(silence, 0.001))
        self.assertTrue(segmenter.calibrated)
        self.assertAlmostEqual(segmenter.start_threshold_db, -48.0, places=1)
        self.assertIsNone(segmenter.process(speech, 0.1))
        self.assertIsNone(segmenter.process(silence, 0.0))
        result = segmenter.process(silence, 0.0)
        self.assertIsNotNone(result)
        self.assertEqual(result.channel, 0)

    def test_conservative_dutch_cleanup(self):
        self.assertEqual(dutch_cleanup("yeah, yeah."), "Ja, ja.")
        self.assertEqual(dutch_cleanup("Sofie gaat naar Barcelona."), "Sofie gaat naar Barcelona.")
        self.assertEqual(dutch_cleanup("(C) TV GELDERLAND 2021"), "")

    def test_absolute_voice_threshold_overrides_noise_margin(self):
        segmenter = ChannelSegmenter(
            channel=0,
            sample_rate=1000,
            noise_margin_db=12,
            minimum_voice_dbfs=-32,
            calibration_ms=100,
        )
        silence = np.full(100, 0.001, dtype=np.float32)
        self.assertIsNone(segmenter.process(silence, 0.001))
        self.assertTrue(segmenter.calibrated)
        self.assertAlmostEqual(segmenter.start_threshold_db, -32.0, places=1)


if __name__ == "__main__":
    unittest.main()

import tempfile
import unittest
import wave
from pathlib import Path

from src.audio import inspect_wav, write_pcm16_wav


class AudioTests(unittest.TestCase):
    @staticmethod
    def temporary_directory():
        root = Path("results/tmp")
        root.mkdir(parents=True, exist_ok=True)
        return tempfile.TemporaryDirectory(dir=root)

    def test_writes_required_format(self):
        with self.temporary_directory() as directory:
            path = Path(directory) / "silence.wav"
            write_pcm16_wav(path, b"\x00\x00" * 1600)
            audio = inspect_wav(path)
            self.assertEqual(audio.sample_rate, 16000)
            self.assertEqual(audio.channels, 1)
            self.assertAlmostEqual(audio.duration_seconds, 0.1)

    def test_rejects_wrong_sample_rate(self):
        with self.temporary_directory() as directory:
            path = Path(directory) / "wrong.wav"
            with wave.open(str(path), "wb") as handle:
                handle.setnchannels(1)
                handle.setsampwidth(2)
                handle.setframerate(8000)
                handle.writeframes(b"\x00\x00" * 800)
            with self.assertRaisesRegex(ValueError, "16000"):
                inspect_wav(path)


if __name__ == "__main__":
    unittest.main()


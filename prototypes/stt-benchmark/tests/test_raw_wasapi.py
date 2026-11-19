import unittest

from src.raw_wasapi import STREAM_MAGIC, parse_stream_header


class RawWasapiProtocolTests(unittest.TestCase):
    def test_parses_four_channel_header(self):
        header = STREAM_MAGIC + (4).to_bytes(4, "little") + (48000).to_bytes(4, "little")
        metadata = parse_stream_header(header)
        self.assertEqual(metadata.channels, 4)
        self.assertEqual(metadata.sample_rate, 48000)

    def test_rejects_unknown_magic(self):
        with self.assertRaises(RuntimeError):
            parse_stream_header(b"UNKNOWN!" + b"\x00" * 8)


if __name__ == "__main__":
    unittest.main()

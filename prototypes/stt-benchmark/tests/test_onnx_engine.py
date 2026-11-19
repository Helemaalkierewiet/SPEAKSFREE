import unittest

from src.engines.onnx_asr_engine import result_text


class ResultTextTests(unittest.TestCase):
    def test_plain_and_segmented_results(self):
        class Segment:
            def __init__(self, text):
                self.text = text

        self.assertEqual(result_text(" hallo "), "hallo")
        self.assertEqual(
            result_text([Segment("goedemorgen"), Segment("oma")]),
            "goedemorgen oma",
        )
        self.assertEqual(result_text({"transcript": "test"}), "test")


if __name__ == "__main__":
    unittest.main()

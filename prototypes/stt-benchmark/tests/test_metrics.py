import unittest

from src.metrics import edit_counts, measure, normalize_text


class NormalizeTests(unittest.TestCase):
    def test_shared_dutch_normalization(self):
        self.assertEqual(
            normalize_text("  De afspraak is om 12:30! "),
            "de afspraak is om twaalf dertig",
        )

    def test_unicode_and_punctuation(self):
        self.assertEqual(normalize_text("Één—twee... drie?"), "één twee drie")


class MetricTests(unittest.TestCase):
    def test_edit_operation_counts(self):
        counts = edit_counts("ik ga naar huis".split(), "ik naar huis toe".split())
        self.assertEqual(counts.deletions, 1)
        self.assertEqual(counts.insertions, 1)
        self.assertEqual(counts.substitutions, 0)
        self.assertAlmostEqual(counts.error_rate, 0.5)

    def test_omissions_and_critical_recall(self):
        result = measure(
            "de huisarts belt morgen om twaalf uur",
            "de huisarts belt morgen",
            ["huisarts", "twaalf uur"],
        )
        self.assertAlmostEqual(result["omitted_word_rate"], 3 / 7)
        self.assertEqual(result["critical_words_found"], 1)
        self.assertEqual(result["critical_word_recall"], 0.5)

    def test_silence_hallucination(self):
        result = measure("", "Hallo, dit is een test.")
        self.assertEqual(result["hallucinated_words"], 5)


if __name__ == "__main__":
    unittest.main()


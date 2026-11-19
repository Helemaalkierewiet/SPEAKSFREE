import json
import tempfile
import unittest
from pathlib import Path

from src.report import _latest_runs, _quality


class ReportAggregationTests(unittest.TestCase):
    def test_corpus_weighted_quality(self):
        records = [
            {
                "exit_status": "ok",
                "reference_words": 2,
                "substitutions": 1,
                "deletions": 0,
                "insertions": 0,
                "reference_characters": 4,
                "character_errors": 1,
                "critical_words_found": 1,
                "critical_words_total": 1,
                "hallucinated_words": 0,
                "english_intrusions": [],
                "realtime_factor": 0.2,
            },
            {
                "exit_status": "ok",
                "reference_words": 8,
                "substitutions": 0,
                "deletions": 1,
                "insertions": 0,
                "reference_characters": 16,
                "character_errors": 2,
                "critical_words_found": 1,
                "critical_words_total": 2,
                "hallucinated_words": 0,
                "english_intrusions": ["okay"],
                "realtime_factor": 0.4,
            },
        ]
        result = _quality(records)
        self.assertAlmostEqual(result["wer"], 0.2)
        self.assertAlmostEqual(result["omission"], 0.1)
        self.assertAlmostEqual(result["cer"], 0.15)
        self.assertAlmostEqual(result["critical_recall"], 2 / 3)
        self.assertEqual(result["english_intrusions"], 1)
        self.assertAlmostEqual(result["rtf_mean"], 0.3)

    def test_latest_runs_filters_recording_session(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for session, started in (("baseline", "2026-01-01"), ("dji", "2026-01-02")):
                payload = {
                    "run": {
                        "session": session,
                        "engine": "model-a",
                        "mode": "offline",
                        "concurrency": 1,
                        "started_at": started,
                    }
                }
                (root / f"{session}.json").write_text(json.dumps(payload), encoding="utf-8")

            selected = _latest_runs(root, session="baseline")
            self.assertEqual(len(selected), 1)
            self.assertEqual(selected[("model-a", "offline", 1)]["run"]["session"], "baseline")


if __name__ == "__main__":
    unittest.main()


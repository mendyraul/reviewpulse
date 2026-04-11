from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from src.pipeline import run_pipeline


class PipelineTests(unittest.TestCase):
    def test_pipeline_writes_expected_artifacts(self) -> None:
        fixture_dir = Path("fixtures")
        inputs = sorted(fixture_dir.glob("*.json"))
        self.assertGreater(len(inputs), 0)

        with tempfile.TemporaryDirectory() as tmp:
            report = run_pipeline(inputs, Path(tmp))

            self.assertEqual(report["totalInput"], len(inputs))
            self.assertGreater(report["normalized"], 0)
            self.assertGreater(report["clusters"], 0)
            self.assertGreaterEqual(report["invalid"], 1)

            summary = Path(tmp, "pr-summary.md").read_text(encoding="utf-8")
            self.assertIn("## ReviewPulse Summary", summary)
            self.assertIn("### Next Actions", summary)

            ranked = json.loads(Path(tmp, "ranked-findings.json").read_text(encoding="utf-8"))
            self.assertIsInstance(ranked, list)
            self.assertGreater(len(ranked), 0)


if __name__ == "__main__":
    unittest.main()

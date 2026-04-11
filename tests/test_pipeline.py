from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

import src.pipeline as pipeline_module
from src.pipeline import run_pipeline


class PipelineTests(unittest.TestCase):
    def test_pipeline_retries_transient_errors_then_processes(self) -> None:
        payload = {
            "source": "github_review",
            "repo": "mendyraul/reviewpulse",
            "prNumber": 1,
            "path": "src/example.py",
            "lineStart": 1,
            "lineEnd": 1,
            "ruleId": "style/nit",
            "severity": "low",
            "message": "Nit",
        }
        with tempfile.TemporaryDirectory() as tmp:
            payload_path = Path(tmp, "payload.json")
            payload_path.write_text(json.dumps(payload), encoding="utf-8")

            original_adapt = pipeline_module._adapt_payload
            call_count = {"count": 0}

            def flaky_adapt(raw):
                call_count["count"] += 1
                if call_count["count"] < 3:
                    raise TimeoutError("transient timeout")
                return original_adapt(raw)

            pipeline_module._adapt_payload = flaky_adapt
            try:
                report = run_pipeline([payload_path], Path(tmp, "out"))
            finally:
                pipeline_module._adapt_payload = original_adapt

            self.assertEqual(report["normalized"], 1)
            self.assertEqual(report["invalid"], 0)
            self.assertEqual(report["reliability"]["retried"], 2)

    def test_pipeline_skips_retry_for_terminal_errors(self) -> None:
        payload = {
            "source": "github_review",
            "repo": "mendyraul/reviewpulse",
            "prNumber": 1,
            "path": "src/example.py",
            "lineStart": 1,
            "lineEnd": 1,
            "ruleId": "style/nit",
            "severity": "low",
            "message": "Nit",
        }
        with tempfile.TemporaryDirectory() as tmp:
            payload_path = Path(tmp, "payload.json")
            payload_path.write_text(json.dumps(payload), encoding="utf-8")

            original_adapt = pipeline_module._adapt_payload
            call_count = {"count": 0}

            def broken_adapt(_raw):
                call_count["count"] += 1
                raise ValueError("unsupported shape")

            pipeline_module._adapt_payload = broken_adapt
            try:
                report = run_pipeline([payload_path], Path(tmp, "out"))
            finally:
                pipeline_module._adapt_payload = original_adapt

            self.assertEqual(call_count["count"], 1)
            self.assertEqual(report["normalized"], 0)
            self.assertEqual(report["invalid"], 1)
            self.assertEqual(report["reliability"]["retried"], 0)

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

            reliability_metrics = json.loads(Path(tmp, "reliability-metrics.json").read_text(encoding="utf-8"))
            self.assertEqual(reliability_metrics["processed"], report["normalized"])
            self.assertEqual(reliability_metrics["deadLettered"], report["invalid"])

            reliability_events = json.loads(Path(tmp, "reliability-events.json").read_text(encoding="utf-8"))
            self.assertEqual(len(reliability_events), report["totalInput"])


if __name__ == "__main__":
    unittest.main()

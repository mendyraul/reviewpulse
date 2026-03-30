import unittest

from src.reporting import calculate_baseline_metrics, render_pr_summary


class TestReporting(unittest.TestCase):
    def setUp(self):
        self.findings = [
            {
                "severity": "medium",
                "path": "src/b.py",
                "lineStart": 12,
                "lineEnd": 12,
                "ruleId": "style.m1",
                "message": "Use explicit type hints",
                "fingerprint": "ccc",
                "status": "open",
                "firstSeenAt": "2026-03-28T08:00:00Z",
            },
            {
                "severity": "critical",
                "path": "src/a.py",
                "lineStart": 3,
                "lineEnd": 5,
                "ruleId": "security.c1",
                "message": "Unsanitized shell execution",
                "fingerprint": "aaa",
                "status": "resolved",
                "firstSeenAt": "2026-03-28T06:00:00Z",
                "resolvedAt": "2026-03-28T09:00:00Z",
            },
            {
                "severity": "high",
                "path": "src/a.py",
                "lineStart": 7,
                "lineEnd": 7,
                "ruleId": "perf.h1",
                "message": "N+1 query in request path",
                "fingerprint": "bbb",
                "status": "resolved",
                "firstSeenAt": "2026-03-28T06:30:00Z",
                "resolvedAt": "2026-03-28T08:30:00Z",
            },
        ]

    def test_summary_output_is_deterministic_and_ordered(self):
        shuffled = [self.findings[0], self.findings[2], self.findings[1]]
        out_one = render_pr_summary(shuffled)
        out_two = render_pr_summary(list(reversed(shuffled)))

        self.assertEqual(out_one, out_two)
        self.assertIn("### Critical (1)", out_one)
        self.assertIn("### High (1)", out_one)
        self.assertIn("### Medium (1)", out_one)
        self.assertIn("### Low (0)", out_one)

        critical_idx = out_one.index("### Critical (1)")
        high_idx = out_one.index("### High (1)")
        medium_idx = out_one.index("### Medium (1)")
        self.assertLess(critical_idx, high_idx)
        self.assertLess(high_idx, medium_idx)

    def test_metrics_match_expected_counts_with_placeholder_time_to_green(self):
        metrics = calculate_baseline_metrics(self.findings)
        self.assertEqual(metrics["openFindings"], 1)
        self.assertEqual(metrics["resolvedFindings"], 2)
        self.assertIsNone(metrics["timeToGreenHours"])

    def test_time_to_green_populates_when_all_findings_resolved(self):
        resolved_only = [dict(f, status="resolved", resolvedAt="2026-03-28T10:00:00Z") for f in self.findings]
        metrics = calculate_baseline_metrics(resolved_only)
        self.assertEqual(metrics["openFindings"], 0)
        self.assertEqual(metrics["resolvedFindings"], 3)
        self.assertEqual(metrics["timeToGreenHours"], 4.0)


if __name__ == "__main__":
    unittest.main()

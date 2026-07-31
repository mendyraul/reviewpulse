import unittest
from datetime import datetime, timezone

from src.dashboard_risk_summary import build_pr_risk_summary_panel


class TestDashboardRiskSummary(unittest.TestCase):
    def setUp(self):
        self.now = datetime(2026, 5, 13, 10, 0, tzinfo=timezone.utc)
        self.rows = [
            {
                "number": 101,
                "title": "Safe cleanup",
                "repo": "mendyraul/reviewpulse",
                "updatedAt": "2026-05-12T10:00:00Z",
                "signals": {"test_delta": 10, "churn": 15, "ownership_hotspot": 20, "prior_defect_density": 10},
            },
            {
                "number": 102,
                "title": "Risky migration",
                "repo": "mendyraul/reviewpulse",
                "updatedAt": "2026-05-11T10:00:00Z",
                "signals": {"test_delta": 80, "churn": 90, "ownership_hotspot": 70, "prior_defect_density": 95},
            },
            {
                "number": 103,
                "title": "Risky infra",
                "repo": "mendyraul/TrackFlights",
                "updatedAt": "2026-05-08T10:00:00Z",
                "signals": {"test_delta": 75, "churn": 75, "ownership_hotspot": 80, "prior_defect_density": 80},
            },
        ]

    def test_panel_metrics_with_7d_window(self):
        panel = build_pr_risk_summary_panel(self.rows, window="7d", now=self.now)
        self.assertEqual(panel["window"], "7d")
        self.assertEqual(panel["highRiskPrCount"], 2)
        self.assertEqual(panel["trend"]["direction"], "up")
        self.assertEqual(panel["hotRepositories"][0]["repo"], "mendyraul/reviewpulse")

    def test_invalid_window_raises(self):
        with self.assertRaises(ValueError):
            build_pr_risk_summary_panel(self.rows, window="14d", now=self.now)


if __name__ == "__main__":
    unittest.main()

import unittest
from datetime import datetime, timezone

from src.risk_dashboard import build_pr_risk_panel


class TestDashboardRiskPanel(unittest.TestCase):
    def test_dashboard_supports_7d_window_and_links(self):
        now = datetime(2026, 5, 13, 15, 35, tzinfo=timezone.utc)
        rows = [
            {
                "number": 10,
                "title": "Risky PR",
                "repo": "mendyraul/reviewpulse",
                "mergedAt": "2026-05-12T10:00:00Z",
                "signals": {
                    "test_delta": 90,
                    "churn": 90,
                    "ownership_hotspot": 90,
                    "prior_defect_density": 90,
                },
            },
            {
                "number": 9,
                "title": "Safe PR",
                "repo": "mendyraul/reviewpulse",
                "mergedAt": "2026-05-11T10:00:00Z",
                "signals": {
                    "test_delta": 5,
                    "churn": 10,
                    "ownership_hotspot": 5,
                    "prior_defect_density": 5,
                },
            },
        ]

        panel = build_pr_risk_panel(rows, days=7, now_iso=now.isoformat())

        self.assertEqual(panel["windowDays"], 7)
        self.assertEqual(panel["highRiskCount"], 1)
        self.assertIn("/dashboard/prs?riskMin=70&window=7", panel["links"]["prList"])

    def test_dashboard_supports_30d_window_and_hot_repositories(self):
        now = datetime(2026, 5, 13, 15, 35, tzinfo=timezone.utc)
        rows = [
            {
                "number": 20,
                "title": "Risky A",
                "repo": "mendyraul/reviewpulse",
                "mergedAt": "2026-05-01T10:00:00Z",
                "signals": {
                    "test_delta": 90,
                    "churn": 90,
                    "ownership_hotspot": 90,
                    "prior_defect_density": 90,
                },
            },
            {
                "number": 21,
                "title": "Risky B",
                "repo": "mendyraul/TrackFlights",
                "mergedAt": "2026-04-25T10:00:00Z",
                "signals": {
                    "test_delta": 88,
                    "churn": 82,
                    "ownership_hotspot": 90,
                    "prior_defect_density": 91,
                },
            },
        ]

        panel = build_pr_risk_panel(rows, days=30, now_iso=now.isoformat())
        self.assertEqual(panel["windowDays"], 30)
        self.assertEqual(panel["highRiskCount"], 2)
        self.assertEqual(len(panel["hotRepositories"]), 2)


if __name__ == "__main__":
    unittest.main()

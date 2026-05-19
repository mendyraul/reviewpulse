import unittest

from src.pr_risk_summary import (
    build_pr_risk_panel,
    build_risk_cta,
    build_risk_summary,
    compute_risk_score,
    recommendation_for_score,
    score_to_confidence,
    summarize_pr_row,
)


class TestPrRiskSummary(unittest.TestCase):
    def test_weighted_risk_score_is_deterministic(self):
        score = compute_risk_score(
            {
                "test_delta": 80,
                "churn": 40,
                "ownership_hotspot": 30,
                "prior_defect_density": 90,
            }
        )
        self.assertEqual(score, 60)

    def test_recommendation_bands(self):
        self.assertEqual(recommendation_for_score(20), "safe_to_merge")
        self.assertEqual(recommendation_for_score(50), "review_required")
        self.assertEqual(recommendation_for_score(88), "block_pending")

    def test_confidence_bands(self):
        self.assertEqual(score_to_confidence(20), "high")
        self.assertEqual(score_to_confidence(55), "medium")
        self.assertEqual(score_to_confidence(80), "low")

    def test_summary_returns_top_drivers_with_evidence_links(self):
        summary = build_risk_summary(
            {
                "test_delta": 70,
                "churn": 90,
                "ownership_hotspot": 85,
                "prior_defect_density": 65,
            },
            evidence_by_signal={
                "churn": "/evidence?pr=12&signal=churn",
                "ownership_hotspot": "/evidence?pr=12&signal=ownership_hotspot",
                "test_delta": "/evidence?pr=12&signal=test_delta",
            },
        )

        self.assertEqual(summary.recommendation, "block_pending")
        self.assertEqual([d.name for d in summary.top_drivers], ["churn", "ownership_hotspot", "test_delta"])
        self.assertEqual(summary.top_drivers[0].evidence_url, "/evidence?pr=12&signal=churn")

    def test_summarize_pr_row_shape(self):
        row = summarize_pr_row(
            {
                "number": 42,
                "title": "Reduce flaky test retries",
                "repo": "mendyraul/reviewpulse",
                "createdAt": "2026-05-12T10:00:00Z",
                "signals": {
                    "test_delta": 20,
                    "churn": 10,
                    "ownership_hotspot": 10,
                    "prior_defect_density": 5,
                },
            }
        )

        self.assertEqual(row["prNumber"], 42)
        self.assertEqual(row["recommendation"], "safe_to_merge")
        self.assertEqual(len(row["topDrivers"]), 3)
        self.assertEqual(row["repo"], "mendyraul/reviewpulse")
        self.assertTrue(row["topDrivers"][0]["evidenceUrl"].startswith("/evidence?pr=42"))

    def test_build_pr_risk_panel_7d_window_with_trend_and_hot_repos(self):
        panel = build_pr_risk_panel(
            [
                {"repo": "a/r1", "riskScore": 81, "createdAt": "2026-05-11T10:00:00Z"},
                {"repo": "a/r1", "riskScore": 75, "createdAt": "2026-05-10T10:00:00Z"},
                {"repo": "a/r2", "riskScore": 40, "createdAt": "2026-05-10T10:00:00Z"},
                {"repo": "a/r2", "riskScore": 80, "createdAt": "2026-05-02T10:00:00Z"},
            ],
            window_days=7,
            now_iso="2026-05-12T12:00:00Z",
        )

        self.assertEqual(panel["window"], "7d")
        self.assertEqual(panel["highRiskPrCount"], 2)
        self.assertEqual(panel["trend"], 1)
        self.assertEqual(panel["hotRepositories"][0]["repo"], "a/r1")
        self.assertEqual(panel["severityBreakdown"], {"high": 2, "medium": 1, "low": 0})
        self.assertIn("/prs?risk=high&window=7d", panel["links"]["highRiskPrs"])

    def test_build_pr_risk_panel_includes_top_contributors(self):
        panel = build_pr_risk_panel(
            [
                {
                    "repo": "a/r1",
                    "riskScore": 81,
                    "createdAt": "2026-05-11T10:00:00Z",
                    "topDrivers": [{"signal": "churn"}, {"signal": "test_delta"}],
                },
                {
                    "repo": "a/r2",
                    "riskScore": 72,
                    "createdAt": "2026-05-11T11:00:00Z",
                    "topDrivers": [{"signal": "churn"}, {"signal": "ownership_hotspot"}],
                },
            ],
            now_iso="2026-05-12T12:00:00Z",
        )

        self.assertEqual(panel["topContributors"][0]["signal"], "churn")
        self.assertEqual(panel["topContributors"][0]["count"], 2)
        self.assertTrue(panel["topContributors"][0]["link"].startswith("/findings?signal=churn"))

    def test_cta_actions_emit_tracking_event_and_backend_update(self):
        now = "2026-05-14T10:35:00Z"
        cta = build_risk_cta("request_review", "mendyraul/reviewpulse", 46, "rico", now)

        self.assertEqual(cta["trackingEvent"]["type"], "pr.risk.request_review")
        self.assertEqual(cta["trackingEvent"]["repo"], "mendyraul/reviewpulse")
        self.assertEqual(cta["backendUpdate"]["fields"]["reviewRequested"], True)
        self.assertEqual(cta["backendUpdate"]["updatedAt"], now)

    def test_unknown_cta_action_raises(self):
        with self.assertRaises(ValueError):
            build_risk_cta("ship_it", "mendyraul/reviewpulse", 46, "rico")


if __name__ == "__main__":
    unittest.main()

import unittest

from src.pr_risk_summary import (
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
        self.assertTrue(row["topDrivers"][0]["evidenceUrl"].startswith("/evidence?pr=42"))


if __name__ == "__main__":
    unittest.main()

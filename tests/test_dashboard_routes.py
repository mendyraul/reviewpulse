import unittest

from src.dashboard_routes import (
    build_active_dashboard_payload,
    build_dashboard_routes,
    build_done_dashboard_payload,
)


class TestDashboardRoutes(unittest.TestCase):
    def setUp(self):
        self.findings = [
            {
                "fingerprint": "a",
                "repo": "mendyraul/reviewpulse",
                "severity": "critical",
                "status": "new",
                "owner": "rico",
                "firstSeenAt": "2026-05-12T00:00:00Z",
                "timeline": [
                    {"event": "status_transition", "actor": "rico", "at": "2026-05-12T00:00:00Z"}
                ],
            },
            {
                "fingerprint": "b",
                "repo": "mendyraul/reviewpulse",
                "severity": "high",
                "status": "in_progress",
                "owner": "sage",
                "firstSeenAt": "2026-05-11T00:00:00Z",
                "timeline": [
                    {"event": "status_transition", "actor": "sage", "at": "2026-05-12T04:00:00Z"}
                ],
            },
            {
                "fingerprint": "c",
                "repo": "mendyraul/reviewpulse",
                "severity": "medium",
                "status": "resolved",
                "owner": "rico",
                "firstSeenAt": "2026-05-10T00:00:00Z",
                "resolvedAt": "2026-05-12T06:00:00Z",
                "timeline": [
                    {"event": "status_transition", "actor": "rico", "at": "2026-05-12T06:00:00Z", "to": "resolved"}
                ],
            },
            {
                "fingerprint": "d",
                "repo": "mendyraul/reviewpulse",
                "severity": "low",
                "status": "archived",
                "owner": "sage",
                "firstSeenAt": "2026-05-09T00:00:00Z",
                "closedAt": "2026-05-12T07:00:00Z",
                "history": [
                    {"event": "done_state_set", "actor": "sage", "at": "2026-05-12T07:00:00Z", "state": "archived"}
                ],
            },
        ]
        self.pr_rows = [
            {"repo": "mendyraul/reviewpulse", "riskScore": 80, "updatedAt": "2026-05-12T00:00:00Z"},
            {"repo": "mendyraul/TrackFlights", "riskScore": 30, "updatedAt": "2026-05-10T00:00:00Z"},
        ]

    def test_dashboard_active_only_includes_actionable_findings(self):
        payload = build_active_dashboard_payload(
            self.findings,
            now_iso="2026-05-13T00:00:00Z",
        )
        self.assertEqual(payload["route"], "/dashboard/active")
        self.assertEqual([row["fingerprint"] for row in payload["rows"]], ["a", "b"])

    def test_dashboard_done_only_includes_completed_findings(self):
        payload = build_done_dashboard_payload(
            self.findings,
            now_iso="2026-05-13T00:00:00Z",
        )
        self.assertEqual(payload["route"], "/dashboard/done")
        self.assertEqual([row["fingerprint"] for row in payload["rows"]], ["d", "c"])
        self.assertTrue(all(row["doneState"] for row in payload["rows"]))
        self.assertEqual(payload["rows"][0]["timelineSummary"]["lastActor"], "sage")

    def test_non_done_rows_keep_owner_and_stale_flags(self):
        payload = build_active_dashboard_payload(
            self.findings,
            now_iso="2026-05-13T00:00:00Z",
            stale_after_hours=24,
        )
        first = payload["rows"][0]
        second = payload["rows"][1]
        self.assertEqual(first["owner"], "rico")
        self.assertTrue(first["isStale"])
        self.assertEqual(second["owner"], "sage")
        self.assertTrue(second["isStale"])

    def test_dashboard_routes_keep_pr_risk_contract_stable(self):
        routes = build_dashboard_routes(
            self.findings,
            self.pr_rows,
            now_iso="2026-05-13T00:00:00Z",
        )
        risk = routes["risk"]
        self.assertEqual(risk["windowDays"], 7)
        self.assertEqual(risk["highRiskCount"], 1)
        self.assertIn("hotRepositories", risk)
        self.assertIn("links", risk)
        self.assertIn("highRisk", risk["links"])


if __name__ == "__main__":
    unittest.main()

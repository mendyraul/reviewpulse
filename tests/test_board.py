import unittest

from src.board import enrich_findings, filter_findings, split_active_and_archive, transition_status


class TestBoard(unittest.TestCase):
    def setUp(self):
        self.rows = [
            {
                "fingerprint": "a",
                "repo": "mendyraul/reviewpulse",
                "severity": "high",
                "status": "new",
                "owner": "rico",
                "firstSeenAt": "2026-04-17T00:00:00Z",
            },
            {
                "fingerprint": "b",
                "repo": "mendyraul/reviewpulse",
                "severity": "medium",
                "status": "triaged",
                "owner": "",
                "firstSeenAt": "2026-04-18T11:00:00Z",
            },
            {
                "fingerprint": "c",
                "repo": "mendyraul/other",
                "severity": "low",
                "status": "resolved",
                "owner": "sage",
                "firstSeenAt": "2026-04-16T10:00:00Z",
            },
        ]

    def test_enrich_adds_owner_escalation_age_and_sla(self):
        enriched = enrich_findings(self.rows, now_iso="2026-04-18T12:00:00Z", stale_after_hours=24)

        first = enriched[0]
        self.assertEqual(first["owner"], "rico")
        self.assertEqual(first["escalation"], "none")
        self.assertTrue(first["isStale"])
        self.assertEqual(first["sla"], "breached")

        second = enriched[1]
        self.assertEqual(second["owner"], "unassigned")
        self.assertFalse(second["isStale"])

        third = enriched[2]
        self.assertTrue(third["doneState"])

    def test_filters_are_deterministic(self):
        enriched = enrich_findings(self.rows, now_iso="2026-04-18T12:00:00Z")
        filtered = filter_findings(enriched, severity="high", owner="rico", status="new", repo="mendyraul/reviewpulse")
        self.assertEqual(len(filtered), 1)
        self.assertEqual(filtered[0]["fingerprint"], "a")

    def test_status_transition_and_timeline(self):
        finding = {"status": "triaged", "timeline": []}
        updated = transition_status(
            finding,
            "in_progress",
            actor="rico",
            at_iso="2026-04-18T12:30:00Z",
        )
        self.assertEqual(updated["status"], "in_progress")
        self.assertEqual(len(updated["timeline"]), 1)
        self.assertEqual(updated["timeline"][0]["from"], "triaged")

    def test_invalid_transition_raises(self):
        with self.assertRaises(ValueError):
            transition_status(
                {"status": "new"},
                "resolved",
                actor="rico",
                at_iso="2026-04-18T12:30:00Z",
            )

    def test_archive_split(self):
        rows = [
            {"fingerprint": "x", "status": "in_progress"},
            {"fingerprint": "y", "status": "archived"},
        ]
        split = split_active_and_archive(rows)
        self.assertEqual(len(split["active"]), 1)
        self.assertEqual(len(split["archive"]), 1)


if __name__ == "__main__":
    unittest.main()

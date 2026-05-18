import unittest
from datetime import datetime, timezone

from src.active_findings_board import (
    BoardFilters,
    build_active_findings_board,
    filters_from_query,
    filters_to_query,
    transition_status,
)


class TestActiveFindingsBoard(unittest.TestCase):
    def setUp(self):
        self.now = datetime(2026, 4, 17, 20, 0, tzinfo=timezone.utc)
        self.findings = [
            {
                "fingerprint": "a",
                "severity": "high",
                "status": "new",
                "owner": "rico",
                "repo": "mendyraul/reviewpulse",
                "firstSeenAt": "2026-04-17T16:00:00Z",
            },
            {
                "fingerprint": "b",
                "severity": "critical",
                "status": "triaged",
                "owner": "sage",
                "repo": "mendyraul/reviewpulse",
                "firstSeenAt": "2026-04-17T12:00:00Z",
            },
            {
                "fingerprint": "c",
                "severity": "medium",
                "status": "resolved",
                "owner": "rico",
                "repo": "mendyraul/reviewpulse",
                "firstSeenAt": "2026-04-17T10:00:00Z",
            },
            {
                "fingerprint": "d",
                "severity": "critical",
                "status": "in_progress",
                "owner": "rico",
                "repo": "mendyraul/TrackFlights",
                "firstSeenAt": "2026-04-17T15:00:00Z",
            },
        ]

    def test_board_includes_only_active_statuses_and_sorts_by_severity_then_age(self):
        board = build_active_findings_board(self.findings, now=self.now)
        self.assertEqual([f["fingerprint"] for f in board], ["b", "d", "a"])
        self.assertEqual(board[0]["ageHours"], 8.0)

    def test_board_filters_are_deterministic(self):
        filters = BoardFilters(owner="rico", severity="critical")
        board = build_active_findings_board(self.findings, filters=filters, now=self.now)
        self.assertEqual([f["fingerprint"] for f in board], ["d"])

    def test_valid_status_transition_updates_record(self):
        finding = self.findings[0]
        triaged = transition_status(finding, "triaged")
        in_progress = transition_status(triaged, "in_progress")
        resolved = transition_status(in_progress, "resolved")

        self.assertEqual(triaged["status"], "triaged")
        self.assertEqual(in_progress["status"], "in_progress")
        self.assertEqual(resolved["status"], "resolved")
        self.assertIn("resolvedAt", resolved)

    def test_invalid_status_transition_raises(self):
        with self.assertRaises(ValueError):
            transition_status(self.findings[0], "resolved")

    def test_filter_query_roundtrip(self):
        filters = BoardFilters(severity="high", owner="rico", status="new", repo="mendyraul/reviewpulse")
        query = filters_to_query(filters)
        restored = filters_from_query(query)
        self.assertEqual(restored, filters)


if __name__ == "__main__":
    unittest.main()

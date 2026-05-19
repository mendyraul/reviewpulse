from src.reporting import calculate_owner_routing_metrics

import unittest
from datetime import datetime, timezone

from src.owner_routing import OwnerRoutingFilters, build_owner_routing_view


class TestOwnerRouting(unittest.TestCase):
    def setUp(self):
        self.now = datetime(2026, 5, 12, 16, 0, tzinfo=timezone.utc)
        self.findings = [
            {"id": "a", "status": "new", "owner": None, "team": "alpha", "firstSeenAt": "2026-05-10T10:00:00Z"},
            {"id": "b", "status": "triaged", "owner": "rico", "team": "alpha", "firstSeenAt": "2026-05-12T10:00:00Z"},
            {"id": "c", "status": "in_progress", "owner": None, "team": "beta", "firstSeenAt": "2026-05-12T08:00:00Z"},
            {"id": "d", "status": "resolved", "owner": "sage", "team": "beta", "firstSeenAt": "2026-05-11T08:00:00Z"},
        ]

    def test_summary_and_drilldown(self):
        view = build_owner_routing_view(self.findings, now=self.now)
        self.assertEqual(view["summary"]["unowned"], 2)
        self.assertEqual(view["summary"]["staleUnowned"], 1)
        self.assertEqual(view["summary"]["owners"]["rico"], 1)
        self.assertEqual(len(view["drilldown"]), 2)

        stale_row = view["rows"][0]
        self.assertEqual(stale_row["owner"], "unassigned")
        self.assertEqual(stale_row["routingStatus"], "stale_unassigned")
        self.assertEqual(stale_row["assignmentAction"], "pending_backend")

    def test_team_filter(self):
        view = build_owner_routing_view(self.findings, filters=OwnerRoutingFilters(team="alpha"), now=self.now)
        self.assertEqual(view["summary"]["unowned"], 1)
        self.assertEqual(len(view["rows"]), 2)

def test_owner_routing_metrics_counts_and_filters() -> None:
    findings = [
        {"id": "1", "status": "open", "owner": None, "updatedAt": "2026-05-09T00:00:00Z", "team": "platform"},
        {"id": "2", "status": "open", "owner": "alice", "updatedAt": "2026-05-12T00:00:00Z", "team": "platform"},
        {"id": "3", "status": "resolved", "owner": None, "updatedAt": "2026-05-01T00:00:00Z", "team": "infra"},
        {"id": "4", "status": "open", "owner": "bob", "updatedAt": "2026-05-07T00:00:00Z", "team": "infra"},
    ]

    metrics = calculate_owner_routing_metrics(findings, now_iso="2026-05-12T06:00:00Z", stale_hours=48)

    assert metrics["openTotal"] == 3
    assert metrics["unownedOpen"] == 1
    assert metrics["assignedOpen"] == 2
    assert metrics["staleUnownedOpen"] == 1
    assert metrics["ownerCounts"] == {"alice": 1, "bob": 1}
    assert metrics["teamCounts"] == {"platform": 2, "infra": 1}
    assert [f["id"] for f in metrics["drilldown"]["staleUnowned"]] == ["1"]


def test_owner_routing_metrics_owner_filter() -> None:
    findings = [
        {"id": "1", "status": "open", "owner": "alice", "updatedAt": "2026-05-10T00:00:00Z"},
        {"id": "2", "status": "open", "owner": "bob", "updatedAt": "2026-05-10T00:00:00Z"},
    ]

    metrics = calculate_owner_routing_metrics(findings, owner="alice", now_iso="2026-05-12T06:00:00Z")

    assert metrics["openTotal"] == 1
    assert metrics["ownerCounts"] == {"alice": 1}
    
if __name__ == "__main__":
    unittest.main()

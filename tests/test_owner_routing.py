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

    def test_team_filter(self):
        view = build_owner_routing_view(self.findings, filters=OwnerRoutingFilters(team="alpha"), now=self.now)
        self.assertEqual(view["summary"]["unowned"], 1)
        self.assertEqual(len(view["rows"]), 2)


if __name__ == "__main__":
    unittest.main()

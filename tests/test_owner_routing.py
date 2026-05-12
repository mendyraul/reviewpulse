from src.reporting import calculate_owner_routing_metrics


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

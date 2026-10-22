from src.board import enrich_findings, build_owner_routing_view
from src.dashboard_routes import build_dashboard_routes
from src.risk_dashboard import build_pr_risk_panel
from src.workflow import transition_status, bulk_transition_findings, reopen_finding
import pytest


def test_generators_utc_boundaries_and_no_fabricated_risk():
    rows = [
        {"repo": "a", "riskScore": 70, "updatedAt": "2026-05-12T00:00:00"},
        {"repo": "a", "riskScore": 70, "updatedAt": "2026-05-05T00:00:00Z"},
        {"repo": "a", "riskScore": 99},
        {"repo": "a", "riskScore": 99, "updatedAt": "2026-05-14T00:00:00Z"},
        {"repo": "a", "updatedAt": "2026-05-12T00:00:00Z"},
    ]
    panel = build_pr_risk_panel(iter(rows), now_iso="2026-05-13T00:00:00")
    assert panel["highRiskCount"] == 1
    assert panel["highRiskTrend"] == 0
    assert panel["coverage"]["unknownScore"] == 1
    assert panel["coverage"]["missingTimestamp"] == 1
    assert panel["severityBreakdown"] == {"high": 1, "medium": 0, "low": 0}


def test_routes_materialize_and_agree_on_all_done_states():
    statuses = [
        "open",
        "acknowledged",
        "reopened",
        "resolved",
        "dismissed",
        "accepted_risk",
        "archived",
    ]
    rows = [{"status": s, "fingerprint": s} for s in statuses]
    payload = build_dashboard_routes(iter(rows), iter([]))
    assert payload["active"]["total"] == 3
    assert payload["done"]["total"] == 4
    routing = build_owner_routing_view(rows)
    assert len(routing["rows"]) == 3
    assert all(r["ageHours"] is None for r in routing["rows"])


def test_migration_preserves_all_legacy_audit_events():
    row = {
        "status": "acknowledged",
        "timeline": [{"event": "old1"}],
        "statusHistory": [{"event": "old2"}],
        "history": [{"event": "old3"}],
    }
    result = transition_status(
        row, "resolved", actor="tester", reason="verified", confirmed=True
    )
    assert result["status"] == "resolved"
    assert [e["event"] for e in result["history"][:3]] == ["old1", "old2", "old3"]
    assert result["history"][-1]["from"] == "acknowledged"
    reopened = reopen_finding(result, actor="tester", rationale="regression")
    assert reopened["status"] == "in_progress"
    assert "closedAt" not in reopened and "resolvedAt" not in reopened
    assert row["status"] == "acknowledged"


def test_bulk_close_never_supplies_implicit_confirmation_or_rationale():
    row = {"status": "triaged"}
    assert bulk_transition_findings([row], "close", actor="tester")["updated"] == 0
    with pytest.raises(ValueError, match="missing_actor"):
        transition_status(row, "in_progress", actor=" ")
    for status in ("new", "triaged", "in_progress", "open", "acknowledged", "reopened"):
        with pytest.raises(ValueError):
            reopen_finding({"status": status}, actor="tester", rationale="test")


def test_missing_and_future_dates_do_not_become_stale():
    rows = enrich_findings(
        [{}, {"firstSeenAt": "2026-05-14T00:00:00"}], now_iso="2026-05-13T00:00:00"
    )
    assert rows[0]["ageHours"] is None
    assert rows[1]["ageHours"] == 0
    assert not any(r["isStale"] for r in rows)

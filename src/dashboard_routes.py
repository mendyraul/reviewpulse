from __future__ import annotations

from typing import Any, Dict, Iterable, List, Optional

from .board import enrich_findings
from .risk_dashboard import build_pr_risk_panel

ACTIVE_STATUSES = {"new", "triaged", "in_progress"}
DONE_STATUSES = {"resolved", "archived"}


def _timeline_summary(row: Dict[str, Any]) -> Dict[str, Optional[str]]:
    """Return the latest traceable event for a done-state row."""
    timeline = list(row.get("timeline") or row.get("history") or [])
    if not timeline:
        return {"lastEvent": None, "lastActor": None, "lastAt": None}

    ordered = sorted(timeline, key=lambda entry: entry.get("at", ""))
    latest = ordered[-1]
    return {
        "lastEvent": latest.get("event") or latest.get("to") or latest.get("state"),
        "lastActor": latest.get("actor"),
        "lastAt": latest.get("at"),
    }


def build_active_dashboard_payload(
    findings: Iterable[Dict[str, Any]],
    *,
    now_iso: Optional[str] = None,
    stale_after_hours: int = 24,
) -> Dict[str, Any]:
    """Build the payload for the active findings dashboard route."""
    rows = [
        row
        for row in enrich_findings(findings, now_iso=now_iso, stale_after_hours=stale_after_hours)
        if row.get("status") in ACTIVE_STATUSES
    ]
    return {
        "route": "/dashboard/active",
        "rows": rows,
        "total": len(rows),
        "empty": len(rows) == 0,
    }


def build_done_dashboard_payload(
    findings: Iterable[Dict[str, Any]],
    *,
    now_iso: Optional[str] = None,
    stale_after_hours: int = 24,
) -> Dict[str, Any]:
    """Build the payload for completed findings with timeline metadata."""
    rows: List[Dict[str, Any]] = []
    for row in enrich_findings(findings, now_iso=now_iso, stale_after_hours=stale_after_hours):
        if row.get("status") not in DONE_STATUSES:
            continue
        enriched = dict(row)
        enriched["timelineSummary"] = _timeline_summary(enriched)
        enriched["doneState"] = True
        rows.append(enriched)

    rows.sort(key=lambda row: (row.get("closedAt") or row.get("resolvedAt") or "", row.get("fingerprint", "")), reverse=True)
    return {
        "route": "/dashboard/done",
        "rows": rows,
        "total": len(rows),
        "empty": len(rows) == 0,
    }


def build_dashboard_routes(
    findings: Iterable[Dict[str, Any]],
    pr_rows: Iterable[Dict[str, Any]],
    *,
    now_iso: Optional[str] = None,
    stale_after_hours: int = 24,
    pr_window_days: int = 7,
) -> Dict[str, Any]:
    """Compose the active, done, and risk dashboard payloads."""
    return {
        "active": build_active_dashboard_payload(findings, now_iso=now_iso, stale_after_hours=stale_after_hours),
        "done": build_done_dashboard_payload(findings, now_iso=now_iso, stale_after_hours=stale_after_hours),
        "risk": build_pr_risk_panel(pr_rows, days=pr_window_days, now_iso=now_iso),
    }

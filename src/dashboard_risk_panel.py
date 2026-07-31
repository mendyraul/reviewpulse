from __future__ import annotations

from collections import Counter
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Iterable, List
from urllib.parse import urlencode

from src.pr_risk_summary import summarize_pr_row


def _parse_iso(ts: str | None) -> datetime | None:
    """Parse an optional ISO timestamp for merged-at filtering."""
    if not ts:
        return None
    try:
        return datetime.fromisoformat(ts.replace("Z", "+00:00"))
    except ValueError:
        return None


def _window_start(days: int, now: datetime | None = None) -> datetime:
    """Compute the inclusive start timestamp for a dashboard window."""
    now = now or datetime.now(timezone.utc)
    return now - timedelta(days=days)


def _filter_window(pr_rows: Iterable[Dict[str, Any]], days: int, now: datetime | None = None) -> List[Dict[str, Any]]:
    """Return PR rows merged inside the requested rolling window."""
    start = _window_start(days, now=now)
    out: List[Dict[str, Any]] = []
    for row in pr_rows:
        merged = _parse_iso(row.get("mergedAt"))
        if merged and merged >= start:
            out.append(row)
    return out


def _link(path: str, **params: Any) -> str:
    """Create a relative dashboard URL with encoded query parameters."""
    return f"/{path}?{urlencode(params)}"


def build_pr_risk_dashboard(pr_rows: Iterable[Dict[str, Any]], window: str = "7d", now: datetime | None = None) -> Dict[str, Any]:
    """Build the dashboard card that highlights recent high-risk PRs."""
    days = 7 if window == "7d" else 30
    selected = _filter_window(pr_rows, days=days, now=now)

    summarized = [summarize_pr_row(pr) for pr in selected]
    high_risk = [r for r in summarized if r["recommendation"] == "block_pending"]

    previous = _filter_window(pr_rows, days=days * 2, now=now)
    previous_summarized = [summarize_pr_row(pr) for pr in previous if pr not in selected]
    previous_high = sum(1 for r in previous_summarized if r["recommendation"] == "block_pending")

    trend = "flat"
    if len(high_risk) > previous_high:
        trend = "up"
    elif len(high_risk) < previous_high:
        trend = "down"

    hot = Counter(pr.get("repo", "unknown") for pr in selected if summarize_pr_row(pr)["recommendation"] == "block_pending")

    return {
        "window": window,
        "highRiskCount": len(high_risk),
        "highRiskTrend": trend,
        "hotRepositories": [{"repo": name, "count": count} for name, count in hot.most_common(3)],
        "links": {
            "highRiskPrs": _link("dashboard/prs", window=window, risk="high"),
            "findings": _link("dashboard/findings", window=window, risk="high"),
            "hotRepositories": _link("dashboard/repos", window=window, sort="risk"),
        },
    }

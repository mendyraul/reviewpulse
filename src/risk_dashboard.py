from __future__ import annotations

from collections import Counter
from datetime import datetime, timedelta, timezone
from typing import Dict, Iterable, List, Optional
from urllib.parse import urlencode


def _parse_iso(ts: Optional[str]) -> Optional[datetime]:
    """Parse an ISO timestamp and return `None` for missing or invalid values."""
    if not ts:
        return None
    try:
        return datetime.fromisoformat(ts.replace("Z", "+00:00"))
    except ValueError:
        return None


def _link(base: str, params: Dict[str, str]) -> str:
    """Build a deterministic dashboard link with encoded query params."""
    return f"{base}?{urlencode(params)}"


def build_pr_risk_panel(pr_rows: Iterable[Dict], *, days: int = 7, now_iso: Optional[str] = None) -> Dict:
    """Summarize high-risk PR activity for the selected reporting window."""
    if days not in (7, 30):
        raise ValueError("days must be 7 or 30")

    now = _parse_iso(now_iso) if now_iso else datetime.now(timezone.utc)
    if now is None:
        now = datetime.now(timezone.utc)
    cutoff = now - timedelta(days=days)

    rows = []
    for row in pr_rows:
        updated = _parse_iso(row.get("updatedAt"))
        if updated and updated >= cutoff:
            rows.append(row)

    high = [r for r in rows if int(r.get("riskScore", 0)) >= 70]
    prev_cutoff = cutoff - timedelta(days=days)
    prev = [r for r in pr_rows if (_parse_iso(r.get("updatedAt")) or datetime.min.replace(tzinfo=timezone.utc)) >= prev_cutoff and (_parse_iso(r.get("updatedAt")) or datetime.min.replace(tzinfo=timezone.utc)) < cutoff]
    prev_high = [r for r in prev if int(r.get("riskScore", 0)) >= 70]

    trend = len(high) - len(prev_high)
    repo_counts = Counter(r.get("repo", "unknown") for r in high)
    hot_repos = [{"repo": repo, "count": count} for repo, count in repo_counts.most_common(3)]

    return {
        "windowDays": days,
        "highRiskCount": len(high),
        "highRiskTrend": trend,
        "hotRepositories": hot_repos,
        "links": {
            "highRisk": _link("/dashboard/findings", {"risk": "high", "window": str(days)}),
            "prList": _link("/dashboard/prs", {"riskMin": "70", "window": str(days)}),
            "repos": [_link("/dashboard/prs", {"repo": item["repo"], "riskMin": "70", "window": str(days)}) for item in hot_repos],
        },
    }

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Dict, Iterable, List, Optional
from urllib.parse import urlencode

from src.pr_risk_summary import summarize_pr_row


@dataclass(frozen=True)
class TimeWindow:
    key: str
    days: int


WINDOWS = {
    "7d": TimeWindow(key="7d", days=7),
    "30d": TimeWindow(key="30d", days=30),
}


def _parse_iso(ts: str) -> datetime:
    return datetime.fromisoformat(ts.replace("Z", "+00:00")).astimezone(timezone.utc)


def _window_cutoff(window: str, now: Optional[datetime] = None) -> datetime:
    selected = WINDOWS.get(window)
    if not selected:
        raise ValueError(f"invalid_window:{window}")
    now_utc = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    return now_utc - timedelta(days=selected.days)


def _high_risk(score: int) -> bool:
    return score > 70


def build_pr_risk_summary_panel(pr_rows: Iterable[Dict], window: str = "7d", now: Optional[datetime] = None) -> Dict:
    cutoff = _window_cutoff(window, now=now)
    rows = [row for row in pr_rows if _parse_iso(row["updatedAt"]) >= cutoff]

    summaries = [summarize_pr_row(row) for row in rows]
    high_risk = [s for s in summaries if _high_risk(s["riskScore"])]

    repo_counts = Counter(str(row.get("repo", "")) for row in rows if row.get("repo"))
    hot_repositories = [
        {"repo": name, "count": count, "url": f"/dashboard/findings?{urlencode({'repo': name, 'window': window})}"}
        for name, count in sorted(repo_counts.items(), key=lambda item: (-item[1], item[0]))[:3]
    ]

    previous_cutoff_start = cutoff - (datetime.now(timezone.utc) - cutoff if now is None else (now - cutoff))
    previous_rows = [
        row for row in pr_rows if previous_cutoff_start <= _parse_iso(row["updatedAt"]) < cutoff
    ]
    previous_high_risk = len([1 for row in previous_rows if _high_risk(summarize_pr_row(row)["riskScore"])])

    trend = len(high_risk) - previous_high_risk

    return {
        "window": window,
        "highRiskPrCount": len(high_risk),
        "highRiskPrUrl": f"/dashboard/prs?{urlencode({'risk': 'high', 'window': window})}",
        "trend": {
            "delta": trend,
            "direction": "up" if trend > 0 else "down" if trend < 0 else "flat",
            "url": f"/dashboard/prs?{urlencode({'metric': 'trend', 'window': window})}",
        },
        "hotRepositories": hot_repositories,
    }

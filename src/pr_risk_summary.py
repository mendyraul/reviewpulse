from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Dict, Iterable, List, Optional
from uuid import uuid4
from urllib.parse import urlencode


WEIGHTS = {
    "test_delta": 20,
    "churn": 25,
    "ownership_hotspot": 25,
    "prior_defect_density": 30,
}


@dataclass(frozen=True)
class RiskSignal:
    name: str
    score: int
    evidence_url: Optional[str] = None


@dataclass(frozen=True)
class RiskSummary:
    risk_score: int
    confidence: str
    recommendation: str
    top_drivers: List[RiskSignal]


def _clamp(value: int, low: int = 0, high: int = 100) -> int:
    return max(low, min(high, value))


def compute_risk_score(signals: Dict[str, int]) -> int:
    weighted_sum = 0.0
    weight_total = 0
    for key, weight in WEIGHTS.items():
        raw = int(signals.get(key, 0))
        weighted_sum += _clamp(raw) * weight
        weight_total += weight

    if weight_total == 0:
        return 0

    return int(round(weighted_sum / weight_total))


def score_to_confidence(risk_score: int) -> str:
    if risk_score <= 25:
        return "high"
    if risk_score <= 60:
        return "medium"
    return "low"


def recommendation_for_score(risk_score: int) -> str:
    if risk_score <= 30:
        return "safe_to_merge"
    if risk_score <= 70:
        return "review_required"
    return "block_pending"


def build_risk_summary(
    signals: Dict[str, int],
    evidence_by_signal: Optional[Dict[str, str]] = None,
    top_n: int = 3,
) -> RiskSummary:
    evidence_by_signal = evidence_by_signal or {}
    normalized: List[RiskSignal] = [
        RiskSignal(name=name, score=_clamp(int(signals.get(name, 0))), evidence_url=evidence_by_signal.get(name))
        for name in WEIGHTS.keys()
    ]
    top_drivers = sorted(normalized, key=lambda s: (-s.score, s.name))[:top_n]

    risk_score = compute_risk_score(signals)
    confidence = score_to_confidence(risk_score)
    recommendation = recommendation_for_score(risk_score)

    return RiskSummary(
        risk_score=risk_score,
        confidence=confidence,
        recommendation=recommendation,
        top_drivers=top_drivers,
    )


def evidence_link(pr_number: int, signal_name: str) -> str:
    return f"/evidence?{urlencode({'pr': pr_number, 'signal': signal_name})}"


def summarize_pr_row(pr: Dict) -> Dict:
    pr_number = int(pr["number"])
    signals = pr.get("signals", {})
    summary = build_risk_summary(
        signals,
        evidence_by_signal={name: evidence_link(pr_number, name) for name in WEIGHTS.keys()},
    )

    return {
        "prNumber": pr_number,
        "title": pr.get("title", ""),
        "repo": pr.get("repo", ""),
        "createdAt": pr.get("createdAt"),
        "riskScore": summary.risk_score,
        "confidence": summary.confidence,
        "recommendation": summary.recommendation,
        "topDrivers": [
            {
                "signal": signal.name,
                "score": signal.score,
                "evidenceUrl": signal.evidence_url,
            }
            for signal in summary.top_drivers
        ],
    }


def _parse_iso(ts: Optional[str]) -> Optional[datetime]:
    if not ts:
        return None
    try:
        return datetime.fromisoformat(ts.replace("Z", "+00:00"))
        dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
        return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def build_dashboard_summary(pr_rows: Iterable[Dict], *, window_days: int = 7, now_iso: Optional[str] = None) -> Dict:
    now = _parse_iso(now_iso) if now_iso else datetime.now(timezone.utc)
    if now is None:
        now = datetime.now(timezone.utc)
    cutoff = now - timedelta(days=window_days)

    normalized = [summarize_pr_row(row) for row in pr_rows]
    in_window = [row for row, raw in zip(normalized, pr_rows) if (_parse_iso(raw.get("mergedAt") or raw.get("updatedAt")) or now) >= cutoff]

    high_risk = [row for row in in_window if row["riskScore"] >= 70]
    prev_cutoff = cutoff - timedelta(days=window_days)
    prev_window = [
        summarize_pr_row(raw)
        for raw in pr_rows
        if prev_cutoff <= ((_parse_iso(raw.get("mergedAt") or raw.get("updatedAt")) or now)) < cutoff
    ]
    prev_high = len([row for row in prev_window if row["riskScore"] >= 70])

    trend_delta = len(high_risk) - prev_high
    hot_repositories: Dict[str, int] = {}
    for row in high_risk:
        repo = row.get("repo") or "unknown"
        hot_repositories[repo] = hot_repositories.get(repo, 0) + 1

    top_hot = sorted(hot_repositories.items(), key=lambda kv: (-kv[1], kv[0]))[:3]
    query = urlencode({"minRisk": 70, "windowDays": window_days})
    return {
        "windowDays": window_days,
        "highRiskPrCount": len(high_risk),
        "highRiskTrendDelta": trend_delta,
        "hotRepositories": [{"repo": repo, "count": count, "link": f"/findings?repo={repo}&minRisk=70&windowDays={window_days}"} for repo, count in top_hot],
        "links": {
            "highRiskPrs": f"/prs?{query}",
            "highRiskFindings": f"/findings?{query}",
def _severity_for_score(score: int) -> str:
    if score >= 70:
        return "high"
    if score >= 40:
        return "medium"
    return "low"


def build_pr_risk_panel(pr_rows: Iterable[Dict], window_days: int = 7, now_iso: Optional[str] = None) -> Dict:
    now = _parse_iso(now_iso) if now_iso else datetime.now(tz=timezone.utc)
    if now is None:
        now = datetime.now(tz=timezone.utc)

    window_start = now - timedelta(days=window_days)
    previous_start = window_start - timedelta(days=window_days)

    current, previous = [], []
    for row in pr_rows:
        created = _parse_iso(row.get("createdAt"))
        if not created:
            continue
        if created >= window_start:
            current.append(row)
        elif created >= previous_start:
            previous.append(row)

    current_high = sum(1 for row in current if int(row.get("riskScore", 0)) >= 70)
    previous_high = sum(1 for row in previous if int(row.get("riskScore", 0)) >= 70)

    repo_counts: Dict[str, int] = {}
    severity_breakdown = {"high": 0, "medium": 0, "low": 0}
    top_driver_counts: Dict[str, int] = {}
    for row in current:
        score = int(row.get("riskScore", 0))
        severity_breakdown[_severity_for_score(score)] += 1
        if score >= 70:
            repo = row.get("repo") or "unknown"
            repo_counts[repo] = repo_counts.get(repo, 0) + 1

        for driver in row.get("topDrivers", []):
            signal = driver.get("signal")
            if signal:
                top_driver_counts[signal] = top_driver_counts.get(signal, 0) + 1

    hot_repos = [{"repo": repo, "highRiskCount": count} for repo, count in sorted(repo_counts.items(), key=lambda x: (-x[1], x[0]))[:3]]
    top_contributors = [
        {"signal": signal, "count": count, "link": f"/findings?signal={signal}&window={window_days}d"}
        for signal, count in sorted(top_driver_counts.items(), key=lambda x: (-x[1], x[0]))[:3]
    ]

    base_q = f"window={window_days}d"
    return {
        "window": f"{window_days}d",
        "highRiskPrCount": current_high,
        "trend": current_high - previous_high,
        "severityBreakdown": severity_breakdown,
        "topContributors": top_contributors,
        "hotRepositories": hot_repos,
        "links": {
            "highRiskPrs": f"/prs?risk=high&{base_q}",
            "findings": f"/findings?severity=high&{base_q}",
        },
    }


def build_risk_cta(action: str, repo: str, pr_number: int, actor: str, now_iso: Optional[str] = None) -> Dict:
    action_map = {
        "request_review": {
            "eventType": "pr.risk.request_review",
            "update": {"reviewRequested": True, "reviewRequestedBy": actor},
        },
        "assign_owner": {
            "eventType": "pr.risk.assign_owner",
            "update": {"owner": actor, "ownerAssignedAt": now_iso},
        },
        "open_mitigation_task": {
            "eventType": "pr.risk.open_mitigation_task",
            "update": {"mitigationTaskRequested": True, "mitigationRequestedBy": actor},
        },
    }
    if action not in action_map:
        raise ValueError(f"Unsupported CTA action: {action}")

    event_time = now_iso or datetime.now(tz=timezone.utc).isoformat()
    payload = action_map[action]
    return {
        "trackingEvent": {
            "id": f"evt_{uuid4().hex[:12]}",
            "type": payload["eventType"],
            "repo": repo,
            "prNumber": int(pr_number),
            "actor": actor,
            "at": event_time,
        },
        "backendUpdate": {
            "repo": repo,
            "prNumber": int(pr_number),
            "fields": payload["update"],
            "updatedAt": event_time,
        },
    }

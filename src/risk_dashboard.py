from collections import Counter
from dataclasses import dataclass
from datetime import timedelta
from typing import Dict, Iterable, List, Optional
from urllib.parse import urlencode
from uuid import uuid4
from .time_utils import parse_iso, utc_now

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
        RiskSignal(
            name=name,
            score=_clamp(int(signals.get(name, 0))),
            evidence_url=evidence_by_signal.get(name),
        )
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


def evidence_link(pr_number: int, signal_name: str, repo=None) -> str:
    return "/evidence?" + urlencode(
        {"pr": pr_number, "signal": signal_name, **({"repo": repo} if repo else {})}
    )


def summarize_pr_row(pr: Dict) -> Dict:
    pr_number = int(pr["number"])
    signals = pr.get("signals", {})
    summary = build_risk_summary(
        signals,
        evidence_by_signal={
            name: evidence_link(pr_number, name, pr.get("repo"))
            for name in WEIGHTS.keys()
        },
    )

    return {
        "prNumber": pr_number,
        "title": pr.get("title", ""),
        "repo": pr.get("repo", ""),
        "createdAt": pr.get("createdAt"),
        "updatedAt": pr.get("updatedAt"),
        "mergedAt": pr.get("mergedAt"),
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


def normalize_pr_row(row):
    result = dict(row)
    if result.get("riskScore") is None and result.get("signals"):
        result.update(summarize_pr_row(row))
    score = result.get("riskScore")
    if score is not None:
        if (
            isinstance(score, bool)
            or not isinstance(score, (int, float))
            or not 0 <= score <= 100
        ):
            raise ValueError("riskScore must be a number between 0 and 100")
    result["riskScore"] = score
    return result


def pr_timestamp(row):
    return parse_iso(
        row.get("updatedAt") or row.get("mergedAt") or row.get("createdAt")
    )


def window_pr_rows(pr_rows, *, days=7, now_iso=None):
    if days not in (7, 30):
        raise ValueError("days must be 7 or 30")
    now = utc_now(now_iso)
    cutoff = now - timedelta(days=days)
    rows = [normalize_pr_row(row) for row in pr_rows]
    return [r for r in rows if pr_timestamp(r) and cutoff <= pr_timestamp(r) <= now]


def build_pr_risk_panel(pr_rows: Iterable[Dict], *, days=7, now_iso=None):
    raw = list(pr_rows)
    now = utc_now(now_iso)
    rows = window_pr_rows(raw, days=days, now_iso=now.isoformat())
    cutoff = now - timedelta(days=days)
    previous = [
        normalize_pr_row(r)
        for r in raw
        if pr_timestamp(r) and cutoff - timedelta(days=days) <= pr_timestamp(r) < cutoff
    ]
    high = [r for r in rows if r.get("riskScore") is not None and r["riskScore"] >= 70]
    previous_high = [
        r for r in previous if r.get("riskScore") is not None and r["riskScore"] >= 70
    ]
    repos = Counter(r.get("repo") or "unknown" for r in high)
    hot = [
        {"repo": repo, "count": count}
        for repo, count in sorted(repos.items(), key=lambda pair: (-pair[1], pair[0]))[
            :3
        ]
    ]
    severity = {"high": 0, "medium": 0, "low": 0}
    contributors = Counter()
    for row in rows:
        score = row.get("riskScore")
        if score is not None:
            severity["high" if score >= 70 else "medium" if score >= 40 else "low"] += 1
        contributors.update(
            {d["signal"] for d in row.get("topDrivers", []) if d.get("signal")}
        )

    def link(base, **params):
        return base + "?" + urlencode(params)

    return {
        "windowDays": days,
        "highRiskCount": len(high),
        "highRiskTrend": len(high) - len(previous_high),
        "hotRepositories": hot,
        "severityBreakdown": severity,
        "topContributors": [
            {
                "signal": key,
                "count": count,
                "link": link("/dashboard/findings", signal=key, window=days),
            }
            for key, count in sorted(
                contributors.items(), key=lambda pair: (-pair[1], pair[0])
            )[:3]
        ],
        "coverage": {
            "total": len(raw),
            "inWindow": len(rows),
            "unknownScore": sum(r.get("riskScore") is None for r in rows),
            "missingTimestamp": sum(pr_timestamp(r) is None for r in raw),
        },
        "links": {
            "highRisk": link("/dashboard/findings", risk="high", window=days),
            "prList": link("/dashboard/prs", riskMin=70, window=days),
            "repos": [
                link("/dashboard/prs", repo=r["repo"], riskMin=70, window=days)
                for r in hot
            ],
        },
    }


def build_risk_cta(
    action: str, repo: str, pr_number: int, actor: str, now_iso: Optional[str] = None
) -> Dict:
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

    event_time = now_iso or utc_now().isoformat()
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

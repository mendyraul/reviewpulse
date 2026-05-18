from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Iterable, List, Optional
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

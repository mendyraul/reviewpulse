from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Dict, List, Optional

DONE_STATES = {"resolved", "dismissed", "accepted_risk"}


@dataclass(frozen=True)
class DoneDecision:
    state: str
    rationale: str
    actor: str
    confirmation: bool = False


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def apply_done_decision(finding: Dict, decision: DoneDecision, *, now_iso: Optional[str] = None) -> Dict:
    if decision.state not in DONE_STATES:
        raise ValueError(f"invalid_done_state:{decision.state}")
    if not decision.rationale.strip():
        raise ValueError("missing_rationale")
    if not decision.actor.strip():
        raise ValueError("missing_actor")
    if not decision.confirmation:
        raise ValueError("confirmation_required")

    current_state = str(finding.get("status") or "").strip()
    if current_state in DONE_STATES and current_state != decision.state:
        raise ValueError("invalid_transition:done_to_done")

    now = now_iso or _now_iso()
    updated = dict(finding)
    updated["status"] = decision.state
    updated["closedAt"] = now

    history: List[Dict] = list(updated.get("history") or [])
    history.append(
        {
            "at": now,
            "actor": decision.actor,
            "event": "done_state_set",
            "state": decision.state,
            "rationale": decision.rationale,
        }
    )
    updated["history"] = history
    updated["closeRationale"] = decision.rationale
    return updated


def done_timeline(finding: Dict) -> List[Dict]:
    history = list(finding.get("history") or [])
    return sorted(history, key=lambda e: e.get("at", ""))

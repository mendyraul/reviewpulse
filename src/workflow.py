from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

DONE_STATES = {"resolved", "dismissed", "accepted_risk"}


def _now_iso(now_iso: Optional[str] = None) -> str:
    if now_iso:
        return now_iso
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def transition_finding_state(
    finding: Dict[str, Any],
    *,
    actor: str,
    to_state: str,
    rationale: str,
    now_iso: Optional[str] = None,
) -> Dict[str, Any]:
    state = to_state.strip().lower()
    if state not in DONE_STATES:
        raise ValueError(f"Unsupported done state: {to_state}")
    if not rationale.strip():
        raise ValueError("Rationale is required for done-state transitions")

    updated = dict(finding)
    history: List[Dict[str, Any]] = list(updated.get("history") or [])
    transition_at = _now_iso(now_iso)

    previous_status = str(updated.get("status") or "open")
    updated["status"] = state
    updated["resolvedAt"] = transition_at
    updated["resolution"] = {"state": state, "rationale": rationale.strip(), "actor": actor}

    history.append(
        {
            "at": transition_at,
            "actor": actor,
            "from": previous_status,
            "to": state,
            "rationale": rationale.strip(),
        }
    )
    updated["history"] = history
    return updated

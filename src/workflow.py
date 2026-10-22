"""Canonical finding lifecycle and audit operations."""

from dataclasses import dataclass
from typing import Any, Dict, List, Iterable
from .time_utils import parse_iso, utc_now

ACTIVE_STATUSES = {"new", "triaged", "in_progress"}
DONE_STATUSES = {"resolved", "dismissed", "accepted_risk", "archived"}
DONE_STATES = DONE_STATUSES - {"archived"}
ALIASES = {
    "open": "new",
    "acknowledged": "triaged",
    "reopened": "in_progress",
    "closed": "resolved",
    "fixed": "resolved",
}
ALLOWED_TRANSITIONS = {
    "new": {"triaged"},
    "triaged": {"in_progress", *DONE_STATES},
    "in_progress": {"triaged", *DONE_STATES},
    **{state: {"archived", "in_progress"} for state in DONE_STATES},
    "archived": {"in_progress"},
}


def normalize_status(value):
    state = str(value or "new").strip().lower()
    return ALIASES.get(state, state)


def audit_history(finding):
    # Preserve distinct legacy events, even when multiple historical fields exist.
    events = []
    for key in ("timeline", "statusHistory", "history"):
        for event in finding.get(key) or []:
            if event not in events:
                events.append(dict(event))
    return sorted(
        events,
        key=lambda e: (
            parse_iso(e.get("at")) is not None,
            parse_iso(e.get("at")) or utc_now("0001-01-01"),
        ),
    )


def transition_status(
    finding, to_status, *, actor, at_iso=None, reason=None, confirmed=False
):
    previous = finding.get("status") or "new"
    current, target = normalize_status(previous), normalize_status(to_status)
    if not actor or not actor.strip():
        raise ValueError("missing_actor")
    if target not in ALLOWED_TRANSITIONS.get(current, set()):
        if current in DONE_STATUSES and target in DONE_STATES:
            raise ValueError("invalid_transition:done_to_done")
        raise ValueError(f"invalid_transition:{current}->{target}")
    reopening = current in DONE_STATUSES and target == "in_progress"
    if target in DONE_STATUSES or reopening:
        if not reason or not reason.strip():
            raise ValueError("Rationale is required")
        if target in DONE_STATUSES and not confirmed:
            raise ValueError("confirmation_required")
    at = at_iso if at_iso is not None else utc_now().isoformat()
    utc_now(at)  # validate before writing audit data
    row = dict(finding)
    history = audit_history(finding)
    event = {
        "event": "done_state_set" if target in DONE_STATUSES else "status_transition",
        "from": previous,
        "to": target,
        "state": target,
        "actor": actor.strip(),
        "at": at,
        "rationale": (reason or "").strip(),
    }
    history.append(event)
    row.update(status=target, history=history, updatedAt=at)
    # Legacy events are now in canonical history; never maintain divergent logs.
    row.pop("timeline", None)
    row.pop("statusHistory", None)
    if target in DONE_STATUSES:
        row.update(closedAt=at, closeRationale=reason.strip())
        if target == "archived":
            row["archivedAt"] = at
        else:
            row["resolvedAt"] = at
        row["resolution"] = {
            "state": target,
            "rationale": reason.strip(),
            "actor": actor.strip(),
        }
    elif reopening:
        row["reopenedAt"] = at
        for key in (
            "resolvedAt",
            "closedAt",
            "archivedAt",
            "resolution",
            "closeRationale",
        ):
            row.pop(key, None)
    return row


def transition_finding_state(
    finding, *, actor, to_state, rationale, now_iso=None, confirmed=False
):
    return transition_status(
        finding,
        to_state,
        actor=actor,
        reason=rationale,
        at_iso=now_iso,
        confirmed=confirmed,
    )


def reopen_finding(finding, *, actor, rationale, now_iso=None):
    if normalize_status(finding.get("status")) not in DONE_STATUSES:
        raise ValueError("Finding is already open")
    return transition_status(
        finding, "in_progress", actor=actor, reason=rationale, at_iso=now_iso
    )


@dataclass(frozen=True)
class DoneDecision:
    state: str
    rationale: str
    actor: str
    confirmation: bool = False


def apply_done_decision(finding, decision, *, now_iso=None):
    if decision.state not in DONE_STATES:
        raise ValueError(f"invalid_done_state:{decision.state}")
    return transition_status(
        finding,
        decision.state,
        actor=decision.actor,
        reason=decision.rationale,
        confirmed=decision.confirmation,
        at_iso=now_iso,
    )


def done_timeline(finding):
    return audit_history(finding)


def build_done_state_confirmation(
    finding: Dict[str, Any],
    *,
    actor: str,
    to_state: str,
    rationale: str,
) -> Dict[str, Any]:
    state = to_state.strip().lower()
    if state not in DONE_STATES:
        raise ValueError(f"Unsupported done state: {to_state}")
    if not rationale.strip():
        raise ValueError("Rationale is required for done-state transitions")

    previous_status = str(finding.get("status") or "open").lower()
    return {
        "findingId": finding.get("id"),
        "actor": actor,
        "from": previous_status,
        "to": state,
        "rationale": rationale.strip(),
        "requiresConfirmation": True,
        "title": f"Close finding as {state.replace('_', ' ')}?",
        "message": "This action records a permanent done-state transition in the audit timeline.",
    }


def render_history_timeline(finding: Dict[str, Any]) -> List[str]:
    lines: List[str] = []
    history: List[Dict[str, Any]] = audit_history(finding)

    for entry in history:
        at = entry.get("at", "unknown-time")
        actor = entry.get("actor", "unknown")
        from_state = entry.get("from", "unknown")
        to_state = entry.get("to", "unknown")
        rationale = str(entry.get("rationale", "")).strip()
        rationale_part = f" — {rationale}" if rationale else ""
        lines.append(f"{at} | {actor} | {from_state} -> {to_state}{rationale_part}")

    return lines


BULK_ACTION_TO_STATUS = {
    "acknowledge": "triaged",
    "snooze": "in_progress",
    "close": "resolved",
}


def bulk_transition_findings(
    findings: Iterable[Dict[str, Any]],
    action: str,
    *,
    actor: str,
    reason=None,
    confirmed=False,
) -> Dict[str, Any]:
    if action not in BULK_ACTION_TO_STATUS:
        raise ValueError(f"invalid_bulk_action:{action}")

    target = BULK_ACTION_TO_STATUS[action]
    updated_rows: List[Dict[str, Any]] = []
    skipped = 0
    failures: List[Dict[str, str]] = []

    for finding in findings:
        try:
            kwargs = {"actor": actor, "reason": reason, "confirmed": confirmed}
            updated_rows.append(transition_status(finding, target, **kwargs))
        except ValueError as exc:
            skipped += 1
            failures.append(
                {
                    "fingerprint": str(finding.get("fingerprint", "")),
                    "error": str(exc),
                }
            )

    return {
        "action": action,
        "targetStatus": target,
        "updated": len(updated_rows),
        "skipped": skipped,
        "rows": updated_rows,
        "failures": failures,
    }

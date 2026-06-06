from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List, Optional

ACTIVE_STATUSES = {"new", "triaged", "in_progress"}
DONE_STATUSES = {"resolved", "archived"}
ALLOWED_TRANSITIONS = {
    "new": {"triaged"},
    "triaged": {"in_progress", "resolved"},
    "in_progress": {"resolved"},
    "resolved": {"archived"},
    "archived": set(),
}


def _parse_iso(ts: Optional[str]) -> Optional[datetime]:
    if not ts:
        return None
    try:
        return datetime.fromisoformat(ts.replace("Z", "+00:00"))
    except ValueError:
        return None


def _age_hours(first_seen_at: Optional[str], now: datetime) -> Optional[float]:
    seen = _parse_iso(first_seen_at)
    if not seen:
        return None
    if seen.tzinfo is None:
        seen = seen.replace(tzinfo=timezone.utc)
    return round((now - seen).total_seconds() / 3600, 2)


def enrich_findings(
    findings: Iterable[Dict[str, Any]],
    *,
    now_iso: Optional[str] = None,
    stale_after_hours: int = 24,
) -> List[Dict[str, Any]]:
    now = _parse_iso(now_iso) if now_iso else datetime.now(tz=timezone.utc)
    if now is None:
        now = datetime.now(tz=timezone.utc)

    enriched: List[Dict[str, Any]] = []
    for finding in findings:
        row = dict(finding)
        status = str(row.get("status", "new")).lower()
        age = _age_hours(row.get("firstSeenAt"), now)

        owner = row.get("owner")
        escalation = row.get("escalation") or "none"
        unassigned = owner in (None, "", "unassigned")

        stale = status in ACTIVE_STATUSES and age is not None and age >= stale_after_hours
        row.update(
            {
                "status": status,
                "owner": "unassigned" if unassigned else owner,
                "escalation": escalation,
                "ageHours": age,
                "isStale": stale,
                "sla": "breached" if stale else "ok",
                "doneState": status in DONE_STATUSES,
            }
        )
        enriched.append(row)

    return enriched


def filter_findings(
    findings: Iterable[Dict[str, Any]],
    *,
    severity: Optional[str] = None,
    owner: Optional[str] = None,
    status: Optional[str] = None,
    repo: Optional[str] = None,
) -> List[Dict[str, Any]]:
    rows = list(findings)

    def _matches(row: Dict[str, Any]) -> bool:
        if severity and str(row.get("severity", "")).lower() != severity.lower():
            return False
        if owner and str(row.get("owner", "")).lower() != owner.lower():
            return False
        if status and str(row.get("status", "")).lower() != status.lower():
            return False
        if repo and str(row.get("repo", "")).lower() != repo.lower():
            return False
        return True

    return [row for row in rows if _matches(row)]


def transition_status(
    finding: Dict[str, Any],
    to_status: str,
    *,
    actor: str,
    at_iso: str,
) -> Dict[str, Any]:
    row = dict(finding)
    from_status = str(row.get("status", "new")).lower()
    to_status = to_status.lower()

    allowed = ALLOWED_TRANSITIONS.get(from_status, set())
    if to_status not in allowed:
        raise ValueError(f"invalid transition: {from_status} -> {to_status}")

    timeline = list(row.get("timeline", []))
    timeline.append(
        {
            "event": "status_transition",
            "from": from_status,
            "to": to_status,
            "actor": actor,
            "at": at_iso,
        }
    )

    row["status"] = to_status
    row["timeline"] = timeline
    if to_status == "resolved":
        row["resolvedAt"] = at_iso
    if to_status == "archived":
        row["archivedAt"] = at_iso
    return row


def split_active_and_archive(findings: Iterable[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
    active: List[Dict[str, Any]] = []
    archive: List[Dict[str, Any]] = []
    for row in findings:
        status = str(row.get("status", "new")).lower()
        if status == "archived":
            archive.append(row)
        else:
            active.append(row)
    return {"active": active, "archive": archive}

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Dict, Iterable, List, Optional
from urllib.parse import parse_qs, urlencode

SEVERITY_ORDER = {"critical": 0, "high": 1, "medium": 2, "low": 3, "info": 4}
ACTIVE_STATUSES = {"new", "triaged", "in_progress"}
ALL_STATUSES = ACTIVE_STATUSES | {"resolved"}
VALID_STATUS_TRANSITIONS = {
    "new": {"triaged"},
    "triaged": {"in_progress", "resolved"},
    "in_progress": {"resolved", "triaged"},
    "resolved": set(),
}


@dataclass(frozen=True)
class BoardFilters:
    severity: Optional[str] = None
    owner: Optional[str] = None
    status: Optional[str] = None
    repo: Optional[str] = None


def _parse_iso8601(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    return parsed.astimezone(timezone.utc)


def compute_age_hours(first_seen_at: str, now: Optional[datetime] = None) -> float:
    now_utc = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    first_seen = _parse_iso8601(first_seen_at)
    seconds = max(0.0, (now_utc - first_seen).total_seconds())
    return round(seconds / 3600.0, 2)


def _matches_filters(finding: Dict, filters: BoardFilters) -> bool:
    if filters.severity and finding.get("severity") != filters.severity:
        return False
    if filters.owner and finding.get("owner") != filters.owner:
        return False
    if filters.status and finding.get("status") != filters.status:
        return False
    if filters.repo and finding.get("repo") != filters.repo:
        return False
    return True


def build_active_findings_board(
    findings: Iterable[Dict],
    filters: BoardFilters = BoardFilters(),
    now: Optional[datetime] = None,
) -> List[Dict]:
    filtered: List[Dict] = []
    for item in findings:
        status = item.get("status", "new")
        if status not in ACTIVE_STATUSES:
            continue
        if not _matches_filters(item, filters):
            continue
        enriched = dict(item)
        enriched["ageHours"] = compute_age_hours(enriched["firstSeenAt"], now=now)
        filtered.append(enriched)

    return sorted(
        filtered,
        key=lambda f: (
            SEVERITY_ORDER.get(f.get("severity", "info"), 99),
            -f.get("ageHours", 0.0),
            f.get("fingerprint", ""),
        ),
    )


def transition_status(finding: Dict, target_status: str) -> Dict:
    if target_status not in ALL_STATUSES:
        raise ValueError(f"invalid_status:{target_status}")

    current = finding.get("status", "new")
    if current not in ALL_STATUSES:
        raise ValueError(f"invalid_current_status:{current}")

    allowed = VALID_STATUS_TRANSITIONS[current]
    if target_status not in allowed:
        raise ValueError(f"invalid_transition:{current}->{target_status}")

    updated = dict(finding)
    updated["status"] = target_status
    if target_status == "resolved":
        updated["resolvedAt"] = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    return updated


def filters_to_query(filters: BoardFilters) -> str:
    payload = {
        "severity": filters.severity,
        "owner": filters.owner,
        "status": filters.status,
        "repo": filters.repo,
    }
    compact = {k: v for k, v in payload.items() if v}
    return urlencode(compact)


def filters_from_query(query_string: str) -> BoardFilters:
    parsed = parse_qs(query_string.lstrip("?"), keep_blank_values=False)

    def first(name: str) -> Optional[str]:
        values = parsed.get(name)
        return values[0] if values else None

    return BoardFilters(
        severity=first("severity"),
        owner=first("owner"),
        status=first("status"),
        repo=first("repo"),
    )

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Dict, Iterable, List, Optional


@dataclass(frozen=True)
class OwnerRoutingFilters:
    owner: Optional[str] = None
    team: Optional[str] = None


def _parse_iso8601(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    return parsed.astimezone(timezone.utc)


def _age_hours(value: str, now: datetime) -> float:
    dt = _parse_iso8601(value)
    return round(max(0.0, (now - dt).total_seconds()) / 3600.0, 2)


def build_owner_routing_view(
    findings: Iterable[Dict],
    filters: OwnerRoutingFilters = OwnerRoutingFilters(),
    now: Optional[datetime] = None,
) -> Dict:
    now_utc = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    rows: List[Dict] = []
    owner_counts: Dict[str, int] = defaultdict(int)
    unowned = 0
    stale_unowned = 0

    for finding in findings:
        owner = finding.get("owner")
        team = finding.get("team")
        status = finding.get("status", "new")
        if status == "resolved":
            continue
        if filters.owner and owner != filters.owner:
            continue
        if filters.team and team != filters.team:
            continue

        age_hours = _age_hours(finding.get("firstSeenAt", "1970-01-01T00:00:00Z"), now_utc)
        is_unowned = not owner
        is_stale_unowned = is_unowned and age_hours > 48

        row = dict(finding)
        row["owner"] = owner or "unassigned"
        row["ageHours"] = age_hours
        row["isUnowned"] = is_unowned
        row["isStaleUnowned"] = is_stale_unowned
        row["routingStatus"] = "stale_unassigned" if is_stale_unowned else ("unassigned" if is_unowned else "owned")
        row["assignmentAction"] = "pending_backend" if is_unowned else "assigned"
        rows.append(row)

        if is_unowned:
            unowned += 1
            if is_stale_unowned:
                stale_unowned += 1
        else:
            owner_counts[row["owner"]] += 1

    rows.sort(key=lambda r: (not r["isStaleUnowned"], not r["isUnowned"], -r.get("ageHours", 0)))

    return {
        "summary": {
            "unowned": unowned,
            "staleUnowned": stale_unowned,
            "owners": dict(sorted(owner_counts.items(), key=lambda kv: (-kv[1], kv[0]))),
        },
        "rows": rows,
        "drilldown": [r for r in rows if r["isUnowned"]],
        "filters": {"owner": filters.owner, "team": filters.team},
    }

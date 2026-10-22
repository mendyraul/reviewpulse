from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List, Optional

from .time_utils import parse_iso as _parse_iso, utc_now
from .workflow import ACTIVE_STATUSES, DONE_STATUSES, normalize_status


def _age_hours(first_seen_at, now):
    seen = _parse_iso(first_seen_at)
    return round(max(0, (now - seen).total_seconds()) / 3600, 2) if seen else None


def enrich_findings(
    findings: Iterable[Dict[str, Any]],
    *,
    now_iso: Optional[str] = None,
    stale_after_hours: int = 24,
) -> List[Dict[str, Any]]:
    now = utc_now(now_iso)

    enriched: List[Dict[str, Any]] = []
    for finding in findings:
        row = dict(finding)
        status = normalize_status(row.get("status"))
        age = _age_hours(row.get("firstSeenAt"), now)

        owner = str(row.get("owner") or "").strip()
        escalation = row.get("escalation") or "none"
        unassigned = owner in (None, "", "unassigned")

        stale = (
            status in ACTIVE_STATUSES and age is not None and age >= stale_after_hours
        )
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


def split_active_and_archive(
    findings: Iterable[Dict[str, Any]],
) -> Dict[str, List[Dict[str, Any]]]:
    active: List[Dict[str, Any]] = []
    archive: List[Dict[str, Any]] = []
    for row in findings:
        status = normalize_status(row.get("status"))
        if status == "archived":
            archive.append(row)
        else:
            active.append(row)
    return {"active": active, "archive": archive}


from dataclasses import dataclass
from collections import defaultdict
from urllib.parse import parse_qs, urlencode, quote

SEVERITY_ORDER = {"critical": 0, "high": 1, "medium": 2, "low": 3, "info": 4}


@dataclass(frozen=True)
class BoardFilters:
    severity: Optional[str] = None
    owner: Optional[str] = None
    status: Optional[str] = None
    repo: Optional[str] = None


def build_active_findings_board(
    findings: Iterable[Dict],
    filters: BoardFilters = BoardFilters(),
    now: Optional[datetime] = None,
) -> List[Dict]:
    filtered: List[Dict] = []
    for item in enrich_findings(findings, now_iso=now.isoformat() if now else None):
        status = item.get("status", "new")
        if status not in ACTIVE_STATUSES:
            continue
        if not filter_findings([item], **vars(filters)):
            continue
        enriched = dict(item)
        fid = enriched.get("fingerprint") or enriched.get("id")
        enriched["cta"] = (
            f"/findings/{quote(str(fid), safe='')}" if fid else "/dashboard/findings"
        )
        filtered.append(enriched)

    return sorted(
        filtered,
        key=lambda f: (
            SEVERITY_ORDER.get(f.get("severity", "info"), 99),
            -(f.get("ageHours") or 0.0),
            f.get("fingerprint", ""),
        ),
    )


def build_active_findings_view(
    findings: Iterable[Dict[str, Any]],
    *,
    filters: BoardFilters = BoardFilters(),
    sort_by: str = "risk",
    page: int = 1,
    page_size: int = 25,
    now: Optional[datetime] = None,
) -> Dict[str, Any]:
    rows = build_active_findings_board(findings, filters=filters, now=now)
    if sort_by == "updated":
        rows.sort(
            key=lambda r: _parse_iso(r.get("updatedAt")) or utc_now("1970-01-01"),
            reverse=True,
        )
    else:
        rows.sort(
            key=lambda r: (
                r.get("riskScore") is not None,
                r.get("riskScore") or 0,
                r.get("ageHours") or 0,
            ),
            reverse=True,
        )

    safe_page = max(1, int(page))
    safe_size = max(1, min(100, int(page_size)))
    start = (safe_page - 1) * safe_size
    end = start + safe_size
    sliced = rows[start:end]

    return {
        "rows": sliced,
        "total": len(rows),
        "hasMore": end < len(rows),
        "states": {"loading": False, "error": None, "empty": len(rows) == 0},
        "filters": {
            "severity": filters.severity,
            "owner": filters.owner,
            "status": filters.status,
            "repo": filters.repo,
            "sortBy": sort_by,
            "page": safe_page,
            "pageSize": safe_size,
        },
    }


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


@dataclass(frozen=True)
class OwnerRoutingFilters:
    owner: Optional[str] = None
    team: Optional[str] = None


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

    for finding in enrich_findings(findings, now_iso=now_utc.isoformat()):
        owner = finding.get("owner")
        team = finding.get("team")
        status = finding.get("status", "new")
        if status not in ACTIVE_STATUSES:
            continue
        if filters.owner and owner != filters.owner:
            continue
        if filters.team and team != filters.team:
            continue

        age_hours = finding["ageHours"]
        is_unowned = owner == "unassigned"
        is_stale_unowned = is_unowned and age_hours is not None and age_hours > 48

        row = dict(finding)
        row["owner"] = owner or "unassigned"
        row["ageHours"] = age_hours
        row["isUnowned"] = is_unowned
        row["isStaleUnowned"] = is_stale_unowned
        row["routingStatus"] = (
            "stale_unassigned"
            if is_stale_unowned
            else ("unassigned" if is_unowned else "owned")
        )
        row["assignmentAction"] = "pending_backend" if is_unowned else "assigned"
        rows.append(row)

        if is_unowned:
            unowned += 1
            if is_stale_unowned:
                stale_unowned += 1
        else:
            owner_counts[row["owner"]] += 1

    rows.sort(
        key=lambda r: (
            not r["isStaleUnowned"],
            not r["isUnowned"],
            -(r.get("ageHours") or 0),
        )
    )

    return {
        "summary": {
            "unowned": unowned,
            "staleUnowned": stale_unowned,
            "owners": dict(
                sorted(owner_counts.items(), key=lambda kv: (-kv[1], kv[0]))
            ),
        },
        "rows": rows,
        "drilldown": [r for r in rows if r["isUnowned"]],
        "filters": {"owner": filters.owner, "team": filters.team},
    }

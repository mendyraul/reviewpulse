from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List, Optional

SEVERITY_ORDER = ["critical", "high", "medium", "low"]
SEVERITY_RANK = {name: idx for idx, name in enumerate(SEVERITY_ORDER)}


def _sort_key(finding: Dict[str, Any]) -> tuple:
    severity = str(finding.get("severity", "medium")).lower()
    return (
        SEVERITY_RANK.get(severity, len(SEVERITY_ORDER)),
        str(finding.get("path", "")),
        int(finding.get("lineStart", 0)),
        str(finding.get("ruleId", "")),
        str(finding.get("fingerprint", "")),
    )


def _bucketed(findings: Iterable[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
    buckets: Dict[str, List[Dict[str, Any]]] = {sev: [] for sev in SEVERITY_ORDER}
    for finding in findings:
        sev = str(finding.get("severity", "medium")).lower()
        if sev in buckets:
            buckets[sev].append(finding)
    for sev in buckets:
        buckets[sev].sort(key=_sort_key)
    return buckets


def _format_finding(finding: Dict[str, Any]) -> str:
    path = finding.get("path", "")
    line_start = finding.get("lineStart", "?")
    line_end = finding.get("lineEnd", line_start)
    rule = finding.get("ruleId", "unknown.rule")
    msg = str(finding.get("message", "")).strip()
    if line_end != line_start:
        line = f"{line_start}-{line_end}"
    else:
        line = f"{line_start}"
    return f"- `{path}:{line}` [{rule}] {msg}"


def render_pr_summary(findings: Iterable[Dict[str, Any]]) -> str:
    ordered = sorted(list(findings), key=_sort_key)
    buckets = _bucketed(ordered)

    lines: List[str] = ["## ReviewPulse Summary", ""]
    for severity in SEVERITY_ORDER:
        title = severity.capitalize()
        items = buckets[severity]
        lines.append(f"### {title} ({len(items)})")
        if items:
            lines.extend(_format_finding(item) for item in items)
        else:
            lines.append("- None")
        lines.append("")

    lines.append("### Next Actions")
    if ordered:
        lines.append("1. Fix Critical and High findings first.")
        lines.append("2. Re-run checks and verify no regressions.")
        lines.append("3. Resolve remaining Medium/Low findings or document deferrals.")
    else:
        lines.append("1. No findings detected; keep CI green and monitor new review input.")

    return "\n".join(lines).strip() + "\n"


def _parse_iso(ts: Optional[str]) -> Optional[datetime]:
    if not ts:
        return None
    normalized = ts.replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(normalized)
    except ValueError:
        return None


def _normalize_owner(raw: Any) -> Optional[str]:
    owner = str(raw or "").strip()
    return owner if owner else None


def _is_open_status(status: Any) -> bool:
    return str(status or "open").lower() not in {"resolved", "closed", "fixed"}


def calculate_owner_routing_metrics(
    findings: Iterable[Dict[str, Any]],
    *,
    owner: Optional[str] = None,
    team: Optional[str] = None,
    stale_hours: int = 48,
    now_iso: Optional[str] = None,
) -> Dict[str, Any]:
    rows = list(findings)
    owner_filter = _normalize_owner(owner)
    team_filter = str(team).strip().lower() if team else None

    now_dt = _parse_iso(now_iso) if now_iso else datetime.now(timezone.utc)
    if now_dt is None:
        now_dt = datetime.now(timezone.utc)

    filtered: List[Dict[str, Any]] = []
    for row in rows:
        row_owner = _normalize_owner(row.get("owner"))
        row_team = str(row.get("team", "")).strip().lower() or None
        if owner_filter and row_owner != owner_filter:
            continue
        if team_filter and row_team != team_filter:
            continue
        filtered.append(row)

    open_rows = [row for row in filtered if _is_open_status(row.get("status"))]
    unowned_open = [row for row in open_rows if not _normalize_owner(row.get("owner"))]
    assigned_open = [row for row in open_rows if _normalize_owner(row.get("owner"))]

    stale_unowned: List[Dict[str, Any]] = []
    for row in unowned_open:
        updated = _parse_iso(row.get("updatedAt") or row.get("firstSeenAt"))
        if not updated:
            stale_unowned.append(row)
            continue
        age_hours = (now_dt - updated).total_seconds() / 3600
        if age_hours >= stale_hours:
            stale_unowned.append(row)

    owner_counts: Dict[str, int] = {}
    team_counts: Dict[str, int] = {}
    for row in open_rows:
        row_owner = _normalize_owner(row.get("owner"))
        row_team = str(row.get("team", "")).strip().lower() or "unscoped"
        if row_owner:
            owner_counts[row_owner] = owner_counts.get(row_owner, 0) + 1
        team_counts[row_team] = team_counts.get(row_team, 0) + 1

    return {
        "openTotal": len(open_rows),
        "unownedOpen": len(unowned_open),
        "assignedOpen": len(assigned_open),
        "staleUnownedOpen": len(stale_unowned),
        "ownerCounts": dict(sorted(owner_counts.items(), key=lambda item: item[0])),
        "teamCounts": dict(sorted(team_counts.items(), key=lambda item: item[0])),
        "drilldown": {
            "unowned": unowned_open,
            "staleUnowned": stale_unowned,
            "assigned": assigned_open,
        },
    }


def calculate_baseline_metrics(findings: Iterable[Dict[str, Any]]) -> Dict[str, Any]:
    rows = list(findings)
    open_count = 0
    resolved_count = 0

    first_seen: Optional[datetime] = None
    latest_resolved: Optional[datetime] = None

    for finding in rows:
        status = str(finding.get("status", "open")).lower()
        if status in {"resolved", "closed", "fixed"}:
            resolved_count += 1
        else:
            open_count += 1

        seen = _parse_iso(finding.get("firstSeenAt"))
        resolved_at = _parse_iso(finding.get("resolvedAt"))

        if seen and (first_seen is None or seen < first_seen):
            first_seen = seen
        if resolved_at and (latest_resolved is None or resolved_at > latest_resolved):
            latest_resolved = resolved_at

    time_to_green_hours: Optional[float] = None
    if rows and open_count == 0 and first_seen and latest_resolved:
        delta = latest_resolved - first_seen
        time_to_green_hours = round(delta.total_seconds() / 3600, 2)

    return {
        "openFindings": open_count,
        "resolvedFindings": resolved_count,
        "timeToGreenHours": time_to_green_hours,
    }

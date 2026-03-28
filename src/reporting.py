from __future__ import annotations

from datetime import datetime
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

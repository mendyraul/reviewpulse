from __future__ import annotations

import hashlib
import re
from typing import Any, Dict, Iterable, List, Optional

SEVERITY_ORDER = ["critical", "high", "medium", "low", "info"]
SEVERITY_RANK = {name: idx for idx, name in enumerate(SEVERITY_ORDER)}


def _norm_space(value: str) -> str:
    """Collapse repeated whitespace and trim leading/trailing spaces."""
    return re.sub(r"\s+", " ", value.strip())


def _cluster_payload(finding: Dict[str, Any]) -> str:
    """Build canonical payload string used for deterministic cluster hashing."""
    return "|".join(
        [
            str(finding.get("repo", "")),
            str(finding.get("prNumber", "")),
            str(finding.get("path", "")),
            str(finding.get("lineStart", "")),
            str(finding.get("lineEnd", finding.get("lineStart", ""))),
            str(finding.get("ruleId", "")).lower(),
            str(finding.get("severity", "medium")).lower(),
            _norm_space(str(finding.get("message", ""))),
        ]
    )


def compute_cluster_key(finding: Dict[str, Any]) -> str:
    """Return stable SHA-256 cluster key for a finding."""
    payload = _cluster_payload(finding)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _source_finding_id(finding: Dict[str, Any]) -> Optional[str]:
    """Extract normalized source finding identifier from top-level/metadata keys."""
    metadata = finding.get("metadata") or {}
    candidate = (
        finding.get("sourceFindingId")
        or finding.get("sourceId")
        or finding.get("id")
        or metadata.get("sourceFindingId")
        or metadata.get("id")
    )
    if candidate is None:
        return None
    value = str(candidate).strip()
    return value or None


def _cluster_sort_key(cluster: Dict[str, Any]) -> tuple:
    """Produce deterministic ordering tuple for ranked cluster output."""
    severity = str(cluster.get("severity", "medium")).lower()
    return (
        SEVERITY_RANK.get(severity, len(SEVERITY_ORDER)),
        str(cluster.get("path", "")),
        int(cluster.get("lineStart", 0)),
        str(cluster.get("ruleId", "")),
        str(cluster.get("clusterKey", "")),
    )


def rank_findings(findings: Iterable[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Deduplicate findings into deterministic clusters ordered by severity/location."""
    grouped: Dict[str, Dict[str, Any]] = {}

    for finding in findings:
        cluster_key = compute_cluster_key(finding)
        source_id = _source_finding_id(finding)

        if cluster_key not in grouped:
            grouped[cluster_key] = {
                "clusterKey": cluster_key,
                "severity": str(finding.get("severity", "medium")).lower(),
                "repo": finding.get("repo"),
                "prNumber": finding.get("prNumber"),
                "path": finding.get("path"),
                "lineStart": finding.get("lineStart"),
                "lineEnd": finding.get("lineEnd", finding.get("lineStart")),
                "ruleId": str(finding.get("ruleId", "")).lower(),
                "message": _norm_space(str(finding.get("message", ""))),
                "fingerprints": [],
                "sourceFindingIds": [],
                "sources": [],
                "count": 0,
            }

        cluster = grouped[cluster_key]
        cluster["count"] += 1

        fingerprint = finding.get("fingerprint")
        if fingerprint and fingerprint not in cluster["fingerprints"]:
            cluster["fingerprints"].append(fingerprint)

        source = str(finding.get("source", "")).lower()
        if source and source not in cluster["sources"]:
            cluster["sources"].append(source)

        if source_id and source_id not in cluster["sourceFindingIds"]:
            cluster["sourceFindingIds"].append(source_id)

    ordered = list(grouped.values())
    for cluster in ordered:
        cluster["fingerprints"].sort()
        cluster["sourceFindingIds"].sort()
        cluster["sources"].sort()

    ordered.sort(key=_cluster_sort_key)
    return ordered

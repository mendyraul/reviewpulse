from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable

ROOT = Path(__file__).resolve().parents[1]
SCHEMA_PATH = ROOT / "schema" / "finding.schema.json"


def _norm_space(value: str) -> str:
    return re.sub(r"\s+", " ", value.strip())


def _fingerprint_payload(f: Dict[str, Any]) -> str:
    return "|".join(
        [
            f["source"].lower(),
            f["repo"],
            str(f["prNumber"]),
            f["path"],
            str(f["lineStart"]),
            str(f["lineEnd"]),
            f["ruleId"].lower(),
            f["severity"].lower(),
            _norm_space(f["message"]),
        ]
    )


def compute_fingerprint(finding: Dict[str, Any]) -> str:
    payload = _fingerprint_payload(finding)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def normalize_finding(raw: Dict[str, Any]) -> Dict[str, Any]:
    now = datetime.now(timezone.utc).replace(microsecond=0).isoformat()

    finding = {
        "source": str(raw["source"]).lower(),
        "repo": str(raw["repo"]),
        "prNumber": int(raw["prNumber"]),
        "path": str(raw["path"]),
        "lineStart": int(raw["lineStart"]),
        "lineEnd": int(raw.get("lineEnd", raw["lineStart"])),
        "ruleId": str(raw["ruleId"]).lower(),
        "severity": str(raw.get("severity", "medium")).lower(),
        "message": _norm_space(str(raw["message"])),
        "firstSeenAt": raw.get("firstSeenAt", now),
        "lastSeenAt": raw.get("lastSeenAt", now),
        "metadata": dict(raw.get("metadata", {})),
    }
    finding["fingerprint"] = compute_fingerprint(finding)
    return finding


def validate_finding(finding: Dict[str, Any]) -> Iterable[str]:
    errors = []
    required = [
        "source",
        "repo",
        "prNumber",
        "path",
        "lineStart",
        "lineEnd",
        "ruleId",
        "severity",
        "message",
        "fingerprint",
        "firstSeenAt",
        "lastSeenAt",
    ]
    for key in required:
        if key not in finding:
            errors.append(f"missing:{key}")

    if finding.get("lineStart", 0) < 1:
        errors.append("lineStart<1")
    if finding.get("lineEnd", 0) < finding.get("lineStart", 1):
        errors.append("lineEnd<lineStart")
    if finding.get("severity") not in {"critical", "high", "medium", "low", "info"}:
        errors.append("invalid:severity")
    if finding.get("source") not in {"github_review", "coderabbit"}:
        errors.append("invalid:source")

    return errors


def load_schema() -> Dict[str, Any]:
    return json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))

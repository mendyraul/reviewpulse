"""Read and validate a complete local snapshot before importing any rows."""

import json
import re
from datetime import timedelta
from pathlib import Path

from .risk_dashboard import normalize_pr_row
from .time_utils import parse_iso, utc_now
from .workflow import ACTIVE_STATUSES, DONE_STATUSES, normalize_status


class ArtifactError(ValueError):
    pass


def read_list(path):
    try:
        rows = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise ArtifactError(f"Cannot load {path}: {exc}") from exc
    if not isinstance(rows, list) or any(not isinstance(r, dict) for r in rows):
        raise ArtifactError(f"{path} must contain a JSON array of objects")
    return rows


def load_snapshot(artifacts_dir, pr_data=None):
    path = Path(artifacts_dir) / "normalized-findings.json"
    rows = read_list(path)
    seen = {}
    for row in rows:
        fid = row.get("fingerprint")
        if not isinstance(fid, str) or not re.fullmatch(r"[A-Za-z0-9_-]{1,128}", fid):
            raise ArtifactError(
                "Each finding needs a stable fingerprint (letters, digits, _ or -)"
            )
        for field in ("repo", "path", "message", "severity"):
            if not isinstance(row.get(field), str):
                raise ArtifactError(f"Finding {fid}: {field} must be text")
        if (
            not isinstance(row.get("prNumber"), int)
            or isinstance(row["prNumber"], bool)
            or row["prNumber"] < 1
        ):
            raise ArtifactError(f"Finding {fid}: prNumber must be a positive integer")
        if row["severity"] not in {"critical", "high", "medium", "low", "info"}:
            raise ArtifactError(f"Finding {fid}: invalid severity")
        if normalize_status(row.get("status")) not in ACTIVE_STATUSES | DONE_STATUSES:
            raise ArtifactError(f"Finding {fid}: unsupported status")
        for field in ("firstSeenAt", "lastSeenAt", "updatedAt"):
            if row.get(field) and parse_iso(row[field]) is None:
                raise ArtifactError(f"Finding {fid}: invalid {field}")
        for field in ("history", "timeline", "statusHistory"):
            events = row.get(field, [])
            if not isinstance(events, list) or any(
                not isinstance(e, dict) for e in events
            ):
                raise ArtifactError(
                    f"Finding {fid}: {field} must contain event objects"
                )
        # Pipeline repeats can share fingerprints. Keep one stable source identity.
        seen[fid] = row
    prs = read_list(pr_data) if pr_data else []
    try:
        for pr in prs:
            if (
                not isinstance(pr.get("repo"), str)
                or not isinstance(pr.get("number"), int)
                or isinstance(pr["number"], bool)
                or pr["number"] < 1
            ):
                raise ValueError("Each PR needs repo and a positive integer number")
            for field in ("updatedAt", "mergedAt", "createdAt"):
                if pr.get(field) and parse_iso(pr[field]) is None:
                    raise ValueError(f"PR {pr['number']}: invalid {field}")
            signals = pr.get("signals", {})
            if not isinstance(signals, dict) or any(
                not isinstance(v, (int, float))
                or isinstance(v, bool)
                or not 0 <= v <= 100
                for v in signals.values()
            ):
                raise ValueError(
                    "signals must map names to numeric scores from 0 to 100"
                )
            drivers = pr.get("topDrivers", [])
            if not isinstance(drivers, list) or any(
                not isinstance(d, dict) or not isinstance(d.get("signal"), str)
                for d in drivers
            ):
                raise ValueError("topDrivers must contain objects with signal names")
            normalize_pr_row(pr)
    except (ValueError, TypeError, KeyError, AttributeError, OverflowError) as exc:
        raise ArtifactError(f"Invalid PR data: {exc}") from exc
    return list(seen.values()), prs, str(path.resolve())


def demo_snapshot():
    now = utc_now()
    rows = [
        {
            "fingerprint": "demo-retry",
            "repo": "demo/reviewpulse",
            "prNumber": 42,
            "path": "src/retry.py",
            "lineStart": 18,
            "message": "Retrying a non-idempotent operation can create duplicate records. Add an idempotency key before retrying.",
            "severity": "high",
            "status": "new",
            "firstSeenAt": (now - timedelta(hours=52)).isoformat(),
            "lastSeenAt": now.isoformat(),
            "ruleId": "reliability/idempotency",
            "source": "github_review",
        },
        {
            "fingerprint": "demo-cache",
            "repo": "demo/reviewpulse",
            "prNumber": 42,
            "path": "src/cache.py",
            "lineStart": 30,
            "message": "Invalidate cached findings after applying a local status change.",
            "severity": "medium",
            "owner": "alex",
            "status": "triaged",
            "firstSeenAt": (now - timedelta(hours=8)).isoformat(),
            "lastSeenAt": now.isoformat(),
        },
        {
            "fingerprint": "demo-escape",
            "repo": "demo/dashboard",
            "prNumber": 17,
            "path": "templates/finding.html",
            "lineStart": 12,
            "message": "Keep external review text escaped: <script>alert('example')</script>",
            "severity": "critical",
            "status": "resolved",
            "owner": "sam",
            "firstSeenAt": (now - timedelta(days=2)).isoformat(),
            "resolvedAt": now.isoformat(),
            "history": [
                {
                    "at": now.isoformat(),
                    "actor": "demo",
                    "from": "triaged",
                    "to": "resolved",
                    "rationale": "Escaping verified in regression tests",
                }
            ],
        },
    ]
    prs = [
        {
            "repo": "demo/reviewpulse",
            "number": 42,
            "title": "Reliable local triage",
            "updatedAt": now.isoformat(),
            "riskScore": 82,
            "topDrivers": [{"signal": "churn", "score": 90}],
        },
        {
            "repo": "demo/dashboard",
            "number": 17,
            "title": "Escape review text",
            "updatedAt": now.isoformat(),
            "riskScore": 25,
        },
    ]
    return rows, prs, "Built-in demo fixtures"

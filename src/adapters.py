from __future__ import annotations

from typing import Any, Dict

SEVERITY_MAP = {
    "critical": "critical",
    "high": "high",
    "medium": "medium",
    "low": "low",
    "info": "info",
    "warning": "medium",
    "warn": "medium",
    "error": "high",
}


def _to_int(value: Any, fallback: int) -> int:
    try:
        out = int(value)
        return out if out > 0 else fallback
    except (TypeError, ValueError):
        return fallback


def _normalize_severity(value: Any, default: str = "medium") -> str:
    if value is None:
        return default
    return SEVERITY_MAP.get(str(value).strip().lower(), default)


def adapt_github_review_comment(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Map a GitHub review comment payload into the FindingDraft shape."""
    repo = payload.get("repository") or payload.get("repo") or {}
    pr = payload.get("pull_request") or payload.get("pr") or {}

    path = str(payload.get("path") or payload.get("file_path") or "")
    if not path:
        raise KeyError("path")

    line_start = _to_int(
        payload.get("line")
        or payload.get("start_line")
        or payload.get("original_line")
        or payload.get("position"),
        1,
    )
    line_end = _to_int(payload.get("end_line") or payload.get("original_end_line"), line_start)

    body = payload.get("body")
    if body is None:
        raise KeyError("body")

    rule_id = (
        payload.get("rule_id")
        or payload.get("rule")
        or payload.get("category")
        or payload.get("tag")
        or "github.review.comment"
    )

    return {
        "source": "github_review",
        "repo": str(repo.get("full_name") if isinstance(repo, dict) else repo),
        "prNumber": int(pr.get("number") if isinstance(pr, dict) else pr or payload.get("pr_number")),
        "path": path,
        "lineStart": line_start,
        "lineEnd": line_end,
        "ruleId": str(rule_id).lower(),
        "severity": _normalize_severity(payload.get("severity"), default="medium"),
        "message": str(body),
        "metadata": {
            "githubCommentId": payload.get("id"),
            "githubNodeId": payload.get("node_id"),
        },
    }


def adapt_coderabbit_finding(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Map a CodeRabbit finding payload into the FindingDraft shape."""
    repo = payload.get("repo") or payload.get("repository") or {}
    pr = payload.get("pr") or payload.get("pull_request") or {}

    path = payload.get("path") or payload.get("file")
    if not path:
        raise KeyError("path")

    message = payload.get("message") or payload.get("text")
    if message is None:
        raise KeyError("message")

    line_start = _to_int(payload.get("lineStart") or payload.get("line") or payload.get("startLine"), 1)
    line_end = _to_int(payload.get("lineEnd") or payload.get("endLine"), line_start)

    rule_id = payload.get("ruleId") or payload.get("checkId") or payload.get("check") or "coderabbit.finding"

    return {
        "source": "coderabbit",
        "repo": str(repo.get("full_name") if isinstance(repo, dict) else repo),
        "prNumber": int(pr.get("number") if isinstance(pr, dict) else pr),
        "path": str(path),
        "lineStart": line_start,
        "lineEnd": line_end,
        "ruleId": str(rule_id).lower(),
        "severity": _normalize_severity(payload.get("severity"), default="medium"),
        "message": str(message),
        "metadata": {
            "codeRabbitFindingId": payload.get("id"),
            "codeRabbitSource": payload.get("source"),
        },
    }

from __future__ import annotations

from typing import Any, Dict


class AdapterValidationError(ValueError):
    def __init__(self, code: str, detail: str):
        self.code = code
        self.detail = detail
        super().__init__(f"{code}: {detail}")


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


def _require_positive_int(value: Any, *, code: str, detail: str) -> int:
    try:
        out = int(value)
    except (TypeError, ValueError):
        raise AdapterValidationError(code, detail)
    if out < 1:
        raise AdapterValidationError(code, detail)
    return out


def _pick_first_present(payload: Dict[str, Any], keys: list[str]) -> Any:
    for key in keys:
        if key in payload and payload[key] is not None:
            return payload[key]
    return None


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
        raise AdapterValidationError("ERR_GH_PATH_REQUIRED", "GitHub payload missing path/file_path")

    line_start_raw = _pick_first_present(payload, ["line", "start_line", "original_line", "position"])
    if line_start_raw is None:
        raise AdapterValidationError("ERR_GH_LINE_REQUIRED", "GitHub payload missing line/start_line/original_line")
    line_start = _require_positive_int(
        line_start_raw,
        code="ERR_GH_LINE_INVALID",
        detail="GitHub line/start_line/original_line must be >= 1",
    )

    line_end_raw = _pick_first_present(payload, ["end_line", "original_end_line"])
    line_end = (
        _require_positive_int(
            line_end_raw,
            code="ERR_GH_LINE_END_INVALID",
            detail="GitHub end_line/original_end_line must be >= 1",
        )
        if line_end_raw is not None
        else line_start
    )

    body = payload.get("body")
    if body is None:
        raise AdapterValidationError("ERR_GH_BODY_REQUIRED", "GitHub payload missing body")

    rule_id = (
        payload.get("rule_id")
        or payload.get("rule")
        or payload.get("category")
        or payload.get("tag")
        or "github.review.comment"
    )

    pr_raw = pr.get("number") if isinstance(pr, dict) else pr or payload.get("pr_number")
    pr_number = _require_positive_int(
        pr_raw,
        code="ERR_GH_PR_REQUIRED",
        detail="GitHub payload missing valid pull request number",
    )

    return {
        "source": "github_review",
        "repo": str(repo.get("full_name") if isinstance(repo, dict) else repo),
        "prNumber": pr_number,
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
        raise AdapterValidationError("ERR_CR_PATH_REQUIRED", "CodeRabbit payload missing path/file")

    message = payload.get("message") or payload.get("text")
    if message is None:
        raise AdapterValidationError("ERR_CR_MESSAGE_REQUIRED", "CodeRabbit payload missing message/text")

    line_start_raw = _pick_first_present(payload, ["lineStart", "line", "startLine"])
    if line_start_raw is None:
        raise AdapterValidationError("ERR_CR_LINE_REQUIRED", "CodeRabbit payload missing lineStart/line/startLine")
    line_start = _require_positive_int(
        line_start_raw,
        code="ERR_CR_LINE_INVALID",
        detail="CodeRabbit lineStart/line/startLine must be >= 1",
    )

    line_end_raw = _pick_first_present(payload, ["lineEnd", "endLine"])
    line_end = (
        _require_positive_int(
            line_end_raw,
            code="ERR_CR_LINE_END_INVALID",
            detail="CodeRabbit lineEnd/endLine must be >= 1",
        )
        if line_end_raw is not None
        else line_start
    )

    rule_id = payload.get("ruleId") or payload.get("checkId") or payload.get("check") or "coderabbit.finding"

    pr_raw = pr.get("number") if isinstance(pr, dict) else pr
    pr_number = _require_positive_int(
        pr_raw,
        code="ERR_CR_PR_REQUIRED",
        detail="CodeRabbit payload missing valid pull request number",
    )

    return {
        "source": "coderabbit",
        "repo": str(repo.get("full_name") if isinstance(repo, dict) else repo),
        "prNumber": pr_number,
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

import pytest

from src.workflow import (
    build_done_state_confirmation,
    reopen_finding,
    render_history_timeline,
    transition_finding_state,
)


def test_done_state_transition_writes_resolution_and_history() -> None:
    finding = {"id": "F-1", "status": "open"}

    updated = transition_finding_state(
        finding,
        actor="rico",
        to_state="resolved",
        rationale="Fix merged in PR #35",
        now_iso="2026-05-12T06:30:00Z",
    )

    assert updated["status"] == "resolved"
    assert updated["resolvedAt"] == "2026-05-12T06:30:00Z"
    assert updated["resolution"]["rationale"] == "Fix merged in PR #35"
    assert updated["history"][0]["from"] == "open"
    assert updated["history"][0]["to"] == "resolved"


def test_done_state_requires_rationale() -> None:
    with pytest.raises(ValueError, match="Rationale is required"):
        transition_finding_state({"status": "open"}, actor="rico", to_state="dismissed", rationale="  ")


def test_reopen_clears_resolution_timestamp_and_appends_history() -> None:
    finding = {
        "id": "F-2",
        "status": "resolved",
        "resolvedAt": "2026-05-12T06:00:00Z",
        "history": [],
    }

    updated = reopen_finding(
        finding,
        actor="rico",
        rationale="Regression detected in follow-up review",
        now_iso="2026-05-12T07:30:00Z",
    )

    assert updated["status"] == "reopened"
    assert "resolvedAt" not in updated
    assert updated["reopenedAt"] == "2026-05-12T07:30:00Z"
    assert updated["history"][-1]["from"] == "resolved"
    assert updated["history"][-1]["to"] == "reopened"


def test_reopen_requires_done_state() -> None:
    with pytest.raises(ValueError, match="already open"):
        reopen_finding({"status": "open"}, actor="rico", rationale="Still under investigation")


def test_done_state_confirmation_payload_is_explicit() -> None:
    finding = {"id": "F-3", "status": "open"}

    confirmation = build_done_state_confirmation(
        finding,
        actor="rico",
        to_state="accepted_risk",
        rationale="Legacy dependency accepted for this release window",
    )

    assert confirmation["findingId"] == "F-3"
    assert confirmation["from"] == "open"
    assert confirmation["to"] == "accepted_risk"
    assert confirmation["requiresConfirmation"] is True
    assert "audit timeline" in confirmation["message"]


def test_history_timeline_renders_readable_entries() -> None:
    finding = {
        "history": [
            {
                "at": "2026-05-12T06:30:00Z",
                "actor": "rico",
                "from": "open",
                "to": "dismissed",
                "rationale": "False positive confirmed in tests",
            }
        ]
    }

    lines = render_history_timeline(finding)

    assert len(lines) == 1
    assert "rico" in lines[0]
    assert "open -> dismissed" in lines[0]
    assert "False positive confirmed in tests" in lines[0]

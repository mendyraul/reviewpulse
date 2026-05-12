import pytest

from src.workflow import transition_finding_state


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

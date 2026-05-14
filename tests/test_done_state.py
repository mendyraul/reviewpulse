from src.done_state import DoneDecision, apply_done_decision, done_timeline


def test_apply_done_decision_requires_confirmation():
    finding = {"id": "f-1", "status": "in_progress"}
    decision = DoneDecision(
        state="resolved",
        rationale="Fixed by PR #12",
        actor="rico",
        confirmation=False,
    )

    try:
        apply_done_decision(finding, decision, now_iso="2026-05-12T19:10:00+00:00")
        assert False, "expected confirmation_required"
    except ValueError as err:
        assert str(err) == "confirmation_required"


def test_apply_done_decision_records_traceable_rationale_and_history():
    finding = {"id": "f-1", "status": "in_progress", "history": []}
    decision = DoneDecision(
        state="dismissed",
        rationale="False positive: test fixture-only path",
        actor="rico",
        confirmation=True,
    )

    updated = apply_done_decision(finding, decision, now_iso="2026-05-12T19:10:00+00:00")

    assert updated["status"] == "dismissed"
    assert updated["closeRationale"] == "False positive: test fixture-only path"
    assert updated["closedAt"] == "2026-05-12T19:10:00+00:00"
    assert updated["history"][-1]["event"] == "done_state_set"
    assert updated["history"][-1]["state"] == "dismissed"


def test_done_timeline_sorts_history():
    finding = {
        "history": [
            {"at": "2026-05-12T19:12:00+00:00", "event": "done_state_set"},
            {"at": "2026-05-12T19:11:00+00:00", "event": "status_changed"},
        ]
    }
    timeline = done_timeline(finding)
    assert timeline[0]["event"] == "status_changed"

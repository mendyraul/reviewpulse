import json
import re
import sqlite3
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from src.server import create_app
from src.pipeline import run_pipeline
from src.local_store import ConflictError, LocalStore


@pytest.fixture
def source(tmp_path):
    artifacts = tmp_path / "artifacts"
    artifacts.mkdir()
    row = {
        "fingerprint": "stable-1",
        "repo": "owner/repo",
        "prNumber": 7,
        "path": "src/one.py",
        "message": '<script>alert("unsafe")</script> & broken retries',
        "severity": "high",
        "firstSeenAt": "2026-01-01T00:00:00Z",
        "metadata": {"body": "<img src=x onerror=alert(1)>"},
    }
    (artifacts / "normalized-findings.json").write_text(json.dumps([row]))
    return artifacts, row


def client_for(tmp_path, source, **kwargs):
    app = create_app(
        artifacts_dir=source[0],
        state_dir=tmp_path / "state",
        actor="local-tester",
        allowed_hosts=("testserver",),
        **kwargs,
    )
    return TestClient(app)


def headers(client):
    page = client.get("/dashboard/active")
    token = re.search(r'name="csrf-token" content="([^"]+)"', page.text)[1]
    return {"origin": "http://testserver", "x-csrf-token": token}


def action(client, name, revision, **kwargs):
    return client.post(
        "/api/findings/stable-1/actions",
        headers=headers(client),
        json={"action": name, "revision": revision, **kwargs},
    )


def test_pages_escape_review_text_and_all_navigation_works(tmp_path, source):
    client = client_for(tmp_path, source)
    for path in [
        "/dashboard/active",
        "/dashboard/done",
        "/dashboard/risk",
        "/dashboard/findings",
        "/dashboard/prs",
        "/findings/stable-1",
    ]:
        page = client.get(path)
        assert page.status_code == 200, page.text
        assert "<script>alert(" not in page.text
        assert page.headers["x-content-type-options"] == "nosniff"
        assert "frame-ancestors 'none'" in page.headers["content-security-policy"]
    detail = client.get("/findings/stable-1").text
    assert "&lt;script&gt;" in detail
    assert "https://github.com/owner/repo/pull/7" in detail
    assert "No live GitHub synchronization" in detail
    assert client.get("/dashboard/nope").status_code == 404
    assert client.get("/findings/unknown").status_code == 404
    assert (
        client.get("/evidence?repo=owner%2Frepo&pr=7&signal=churn").status_code == 200
    )


def test_assignment_status_audit_restart_and_immutable_artifact(tmp_path, source):
    client = client_for(tmp_path, source)
    original = (source[0] / "normalized-findings.json").read_bytes()
    result = action(client, "assign", 0, owner="sam")
    assert result.status_code == 200, result.text
    assert result.json()["revision"] == 1
    assert action(client, "acknowledge", 1).status_code == 200
    assert action(client, "resolved", 2, rationale="verified").status_code == 400
    closed = action(client, "resolved", 2, rationale="verified", confirmed=True)
    assert closed.status_code == 200, closed.text
    assert closed.json()["history"][-1]["actor"] == "local-tester"
    assert client.get("/api/dashboard/active").json()["rows"] == []
    assert len(client.get("/api/dashboard/done").json()["rows"]) == 1
    restarted = client_for(tmp_path, source)
    row = restarted.app.state.store.get("stable-1")
    assert row["status"] == "resolved" and row["owner"] == "sam"
    assert len(row["history"]) == 3
    reopened = action(restarted, "reopen", row["revision"], rationale="regression")
    assert reopened.status_code == 200
    assert reopened.json()["status"] == "in_progress"
    assert "resolvedAt" not in reopened.json()
    assert (source[0] / "normalized-findings.json").read_bytes() == original
    with sqlite3.connect(tmp_path / "state/triage.sqlite3") as db:
        assert db.execute("SELECT count(*) FROM audit").fetchone()[0] == 4


def test_refresh_retains_absent_findings_and_rejects_stale_revision(tmp_path, source):
    client = client_for(tmp_path, source)
    assert action(client, "assign", 0, owner="sam").status_code == 200
    path = source[0] / "normalized-findings.json"
    path.write_text("[]")
    assert (
        client.post("/api/refresh", headers=headers(client), json={}).status_code == 200
    )
    row = client.app.state.store.get("stable-1")
    assert not row["presentInSnapshot"] and row["owner"] == "sam"
    assert action(client, "acknowledge", 1).status_code == 409
    assert "Absent from latest snapshot" in client.get("/dashboard/active").text
    source[1]["message"] = "Updated evidence"
    path.write_text(json.dumps([source[1]]))
    assert (
        client.post("/api/refresh", headers=headers(client), json={}).status_code == 200
    )
    row = client.app.state.store.get("stable-1")
    assert (
        row["presentInSnapshot"]
        and row["message"] == "Updated evidence"
        and row["owner"] == "sam"
    )


def test_missing_or_malformed_artifacts_never_fall_back_to_demo(tmp_path, source):
    path = source[0] / "normalized-findings.json"
    for content in [
        None,
        "{}",
        '[{"fingerprint":"partial"}]',
        "[false]",
        "invalid json",
    ]:
        if content is None:
            path.unlink()
        else:
            path.write_text(content)
        client = client_for(tmp_path, source)
        page = client.get("/dashboard/active")
        assert page.status_code == 503
        assert "Source needs attention" in page.text
        assert "DEMO MODE" not in page.text
        assert client.get("/api/dashboard/active").status_code == 503
    demo = TestClient(
        create_app(
            demo=True, state_dir=tmp_path / "state", allowed_hosts=("testserver",)
        )
    )
    assert "DEMO MODE" in demo.get("/dashboard/active").text
    assert demo.app.state.store.path.name == "demo.sqlite3"


def test_failed_refresh_is_atomic_and_pauses_edits(tmp_path, source):
    client = client_for(tmp_path, source)
    source[1]["prNumber"] = "invalid"
    (source[0] / "normalized-findings.json").write_text(json.dumps([source[1]]))
    assert (
        client.post("/api/refresh", headers=headers(client), json={}).status_code == 503
    )
    assert client.app.state.store.get("stable-1")["revision"] == 0
    assert action(client, "assign", 0, owner="a").status_code == 503


def test_local_boundary_csrf_and_strict_action_validation(tmp_path, source):
    client = client_for(tmp_path, source)
    body = {"action": "assign", "revision": 0, "owner": "sam"}
    url = "/api/findings/stable-1/actions"
    assert client.post(url, json=body).status_code == 403
    good = headers(client)
    assert (
        client.post(
            url, headers={**good, "origin": "https://evil.example"}, json=body
        ).status_code
        == 403
    )
    assert (
        client.post(
            url, headers={**good, "x-csrf-token": "forged"}, json=body
        ).status_code
        == 403
    )
    assert (
        client.get("/dashboard/active", headers={"host": "evil.example"}).status_code
        == 400
    )
    for changes in [
        {"revision": True},
        {"confirmed": "true"},
        {"actor": "spoof"},
        {"owner": "x" * 101},
    ]:
        assert (
            client.post(url, headers=good, json={**body, **changes}).status_code == 422
        )
    assert client.post(url, headers=good, json=body).status_code == 200


def test_concurrent_clients_cannot_overwrite_triage(tmp_path, source):
    client = client_for(tmp_path, source)
    store = LocalStore(client.app.state.store.path)

    def save(owner):
        try:
            store.action(
                "stable-1", action="assign", actor="tester", revision=0, owner=owner
            )
            return "saved"
        except ConflictError:
            return "conflict"

    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sorted(pool.map(save, ["one", "two"])) == ["conflict", "saved"]


def test_filters_pagination_pr_join_and_risk_drilldowns(tmp_path, source):
    from src.time_utils import utc_now

    now = utc_now().isoformat()
    rows = [
        {
            **source[1],
            "fingerprint": f"finding-{n}",
            "severity": "high" if n % 2 else "low",
            "prNumber": 7 if n % 2 else 8,
        }
        for n in range(30)
    ]
    (source[0] / "normalized-findings.json").write_text(json.dumps(rows))
    prs = tmp_path / "prs.json"
    prs.write_text(
        json.dumps(
            [
                {
                    "repo": "owner/repo",
                    "number": 7,
                    "updatedAt": now,
                    "riskScore": 70,
                    "topDrivers": [{"signal": "churn"}],
                }
            ]
        )
    )
    client = client_for(tmp_path, source, pr_data=prs)
    assert len(client.get("/api/dashboard/active?severity=high").json()["rows"]) == 15
    assert "Next →" in client.get("/dashboard/active").text
    assert "Previous" in client.get("/dashboard/active?page=2").text
    risk = client.get("/api/dashboard/risk").json()
    assert risk["highRiskCount"] == 1 and risk["coverage"]["missingTimestamp"] == 1
    assert (
        len(
            client.get(
                risk["links"]["highRisk"].replace("/dashboard/", "/api/dashboard/")
            ).json()["rows"]
        )
        == 15
    )
    assert (
        len(client.get("/api/dashboard/findings?signal=churn&window=7").json()["rows"])
        == 15
    )
    assert client.get("/dashboard/risk?window=14").status_code == 400
    assert client.get("/dashboard/active?page=no").status_code == 400
    assert client.get("/dashboard/prs?riskMin=nan").status_code == 400


def test_pipeline_emits_lossless_dashboard_snapshot(tmp_path):
    run_pipeline([Path("fixtures/adapter_github_review_payload.json")], tmp_path)
    rows = json.loads((tmp_path / "normalized-findings.json").read_text())
    assert rows and rows[0]["fingerprint"] and rows[0]["firstSeenAt"]
    client = TestClient(
        create_app(
            artifacts_dir=tmp_path,
            state_dir=tmp_path / "state",
            allowed_hosts=("testserver",),
        )
    )
    assert client.get("/dashboard/active").status_code == 200
    assert len(client.get("/api/dashboard/active").json()["rows"]) == len(rows)


def test_done_api_preserves_composer_contract_and_reopen_clears_imported_closure(
    tmp_path, source
):
    source[1].update(
        status="resolved",
        resolvedAt="2026-01-02T00:00:00Z",
        closedAt="2026-01-02T00:00:00Z",
        history=[{"at": "2026-01-02T00:00:00Z", "actor": "imported", "to": "resolved"}],
    )
    (source[0] / "normalized-findings.json").write_text(json.dumps([source[1]]))
    client = client_for(tmp_path, source)
    data = client.get("/api/dashboard/done").json()
    assert (
        data["route"] == "/dashboard/done" and data["total"] == 1 and not data["empty"]
    )
    assert data["rows"][0]["timelineSummary"]["lastActor"] == "imported"
    assert action(client, "reopen", 0, rationale="regression").status_code == 200
    row = client.app.state.store.get("stable-1")
    assert "resolvedAt" not in row and "closedAt" not in row
    assert (
        client.post("/api/refresh", headers=headers(client), json={}).status_code == 200
    )
    row = client.app.state.store.get("stable-1")
    assert row["status"] == "in_progress" and "resolvedAt" not in row


@pytest.mark.parametrize("bad_date", [{"invalid": True}, "not-a-date", 0])
def test_malformed_completion_dates_are_a_source_error(tmp_path, source, bad_date):
    source[1].update(status="resolved", closedAt=bad_date)
    (source[0] / "normalized-findings.json").write_text(json.dumps([source[1]]))
    client = client_for(tmp_path, source)
    page = client.get("/dashboard/done")
    assert page.status_code == 503
    assert "invalid closedAt" in page.text

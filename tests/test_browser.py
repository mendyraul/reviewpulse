"""Opt-in real browser acceptance: RUN_BROWSER_TESTS=1 python -m pytest tests/test_browser.py."""

import json
import os
import socket
import threading
import time

import pytest

pytestmark = pytest.mark.skipif(
    os.environ.get("RUN_BROWSER_TESTS") != "1",
    reason="Set RUN_BROWSER_TESTS=1 after installing Playwright Chromium",
)


def test_browser_local_triage_drilldowns_and_mobile(tmp_path):
    import uvicorn
    from playwright.sync_api import expect, sync_playwright
    from src.server import create_app
    from src.time_utils import utc_now

    now = utc_now().isoformat()
    artifacts = tmp_path / "artifacts"
    artifacts.mkdir()
    row = {
        "fingerprint": "browser-finding",
        "repo": "owner/repo",
        "prNumber": 42,
        "path": "src/retry.py",
        "lineStart": 12,
        "message": "Prevent duplicate retries <script>alert(1)</script>",
        "severity": "high",
        "firstSeenAt": now,
        "lastSeenAt": now,
    }
    (artifacts / "normalized-findings.json").write_text(json.dumps([row]))
    prs = tmp_path / "prs.json"
    prs.write_text(
        json.dumps(
            [
                {
                    "repo": "owner/repo",
                    "number": 42,
                    "title": "Reliable retries",
                    "updatedAt": now,
                    "riskScore": 82,
                    "topDrivers": [{"signal": "churn"}],
                }
            ]
        )
    )
    app = create_app(
        artifacts_dir=artifacts,
        state_dir=tmp_path / "state",
        pr_data=prs,
        actor="browser-tester",
    )
    sock = socket.socket()
    sock.bind(("127.0.0.1", 0))
    port = sock.getsockname()[1]
    server = uvicorn.Server(
        uvicorn.Config(
            app, host="127.0.0.1", port=port, log_level="error", proxy_headers=False
        )
    )
    thread = threading.Thread(target=lambda: server.run(sockets=[sock]), daemon=True)
    thread.start()
    try:
        deadline = time.monotonic() + 15
        while not server.started and time.monotonic() < deadline:
            time.sleep(0.05)
        assert server.started
        base = f"http://127.0.0.1:{port}"
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch()
            page = browser.new_page(viewport={"width": 1440, "height": 1000})
            errors = []
            page.on("pageerror", lambda error: errors.append(str(error)))
            page.goto(base + "/dashboard/active")
            expect(
                page.get_by_role("heading", name="Your active review queue")
            ).to_be_visible()
            page.get_by_label("Search", exact=True).fill("not-found")
            page.get_by_role("button", name="Apply filters").click()
            expect(
                page.get_by_role("heading", name="No matching findings")
            ).to_be_visible()
            page.get_by_role("link", name="Clear", exact=True).click()
            page.get_by_role("link", name="Triage & evidence").click()
            expect(page.locator(".evidence")).to_contain_text(
                "<script>alert(1)</script>"
            )
            page.get_by_label("Owner label").fill("sam")
            page.get_by_role("button", name="Save assignment").click()
            expect(page.get_by_label("Owner label")).to_have_value("sam")
            expect(page.locator(".timeline")).to_contain_text("Owner: unassigned → sam")
            page.get_by_role("button", name="Apply status change").click()
            expect(page.locator("dd").first).to_have_text("triaged")
            page.get_by_label("Action", exact=True).select_option("resolved")
            page.get_by_role("button", name="Apply status change").click()
            expect(page.get_by_role("alert")).to_contain_text("Confirm")
            page.get_by_label("Rationale").fill("Verified retry idempotency")
            page.get_by_role("checkbox").check()
            page.get_by_role("button", name="Apply status change").click()
            expect(page.locator("dd").first).to_have_text("resolved")
            page.get_by_role("link", name="Done & archive").click()
            expect(page.get_by_role("link", name="Triage & evidence")).to_be_visible()
            page.get_by_role("link", name="Triage & evidence").click()
            page.get_by_label("Rationale").fill("Regression found")
            page.get_by_role("button", name="Apply status change").click()
            expect(page.locator("dd").first).to_have_text("in progress")
            page.get_by_role("link", name="PR risk overview").click()
            page.get_by_role("link", name="High risk PRs").click()
            expect(page.get_by_role("heading", name="Reliable retries")).to_be_visible()
            page.get_by_role("link", name="View findings & evidence").click()
            expect(page.get_by_role("link", name="Triage & evidence")).to_be_visible()
            page.set_viewport_size({"width": 390, "height": 844})
            page.goto(base + "/findings/browser-finding")
            expect(page.get_by_label("Owner label")).to_have_value("sam")
            assert page.evaluate(
                "document.documentElement.scrollWidth <= window.innerWidth"
            )
            if os.environ.get("REVIEWPULSE_SCREENSHOT"):
                page.screenshot(
                    path=os.environ["REVIEWPULSE_SCREENSHOT"], full_page=True
                )
            (artifacts / "normalized-findings.json").write_text("malformed")
            page.get_by_role("button", name="Refresh snapshot").click()
            expect(page.get_by_role("alert")).to_contain_text("Cannot load")
            page.reload()
            expect(
                page.get_by_role("heading", name="Source needs attention")
            ).to_be_visible()
            expect(page.get_by_role("button", name="Save assignment")).to_be_disabled()
            assert errors == []
            browser.close()
    finally:
        server.should_exit = True
        thread.join(timeout=10)
        sock.close()

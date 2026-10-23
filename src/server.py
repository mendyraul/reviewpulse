"""Run with python -m src.server --artifacts-dir artifacts/pipeline-run."""

import argparse
import getpass
import hashlib
import hmac
import re
import secrets
import threading
from pathlib import Path
from urllib.parse import urlencode, urlsplit

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, ConfigDict, Field, StrictBool, StrictInt

from .artifact_source import ArtifactError, demo_snapshot, load_snapshot
from .board import enrich_findings, filter_findings, SEVERITY_ORDER
from .dashboard_routes import build_dashboard_routes
from .local_store import ConflictError, LocalStore
from .risk_dashboard import build_pr_risk_panel, normalize_pr_row, window_pr_rows
from .time_utils import parse_iso, utc_now
from .workflow import audit_history

ROOT = Path(__file__).resolve().parent


class FindingAction(BaseModel):
    model_config = ConfigDict(extra="forbid")
    action: str = Field(max_length=30)
    revision: StrictInt = Field(ge=0)
    owner: str | None = Field(default=None, max_length=100)
    rationale: str | None = Field(default=None, max_length=4000)
    confirmed: StrictBool = False


def create_app(
    *,
    artifacts_dir="artifacts/pipeline-run",
    state_dir=None,
    pr_data=None,
    demo=False,
    actor=None,
    allowed_hosts=("127.0.0.1", "localhost", "::1"),
):
    actor = actor or getpass.getuser()
    state_dir = (
        Path(state_dir) if state_dir else Path.home() / ".local/state/reviewpulse"
    )
    store = LocalStore(state_dir / ("demo.sqlite3" if demo else "triage.sqlite3"))
    app = FastAPI(title="ReviewPulse local dashboard", docs_url=None, redoc_url=None)
    app.state.store = store
    app.state.load_error = None
    app.state.pr_rows = []
    app.state.last_refresh = None
    app.state.source = str(Path(artifacts_dir) / "normalized-findings.json")
    lock = threading.RLock()
    secret = secrets.token_bytes(32)
    templates = Jinja2Templates(directory=str(ROOT / "templates"))
    app.mount("/static", StaticFiles(directory=str(ROOT / "static")), name="static")

    def reload_snapshot():
        with lock:
            try:
                rows, prs, source = (
                    demo_snapshot() if demo else load_snapshot(artifacts_dir, pr_data)
                )
                store.import_snapshot(rows)
            except ArtifactError as exc:
                app.state.load_error = str(exc)
                return False
            app.state.pr_rows, app.state.source = prs, source
            app.state.last_refresh = utc_now().isoformat()
            app.state.load_error = None
            return True

    reload_snapshot()

    def valid_token(token):
        if not token or not re.fullmatch(r"[a-f0-9]{48}\.[a-f0-9]{64}", token):
            return False
        nonce, signature = token.rsplit(".", 1)
        return hmac.compare_digest(
            signature, hmac.new(secret, nonce.encode(), hashlib.sha256).hexdigest()
        )

    def new_token():
        nonce = secrets.token_hex(24)
        return (
            nonce + "." + hmac.new(secret, nonce.encode(), hashlib.sha256).hexdigest()
        )

    @app.middleware("http")
    async def local_boundary(request: Request, call_next):
        try:
            host = urlsplit("http://" + request.headers.get("host", ""))
            authority = (
                f"[{host.hostname}]"
                if host.hostname and ":" in host.hostname
                else host.hostname
            )
            if host.port is not None:
                authority = f"{authority}:{host.port}"
            valid_host = (
                host.hostname in allowed_hosts
                and host.netloc.lower() == authority
                and not host.path
                and not host.query
                and not host.fragment
            )
        except ValueError:
            valid_host = False
        if not valid_host:
            return JSONResponse(
                {"detail": "This dashboard accepts local hosts only"}, status_code=400
            )
        token = request.cookies.get("reviewpulse_csrf", "")
        if request.method not in ("GET", "HEAD", "OPTIONS"):
            origin = request.headers.get("origin")
            expected_origin = str(request.base_url).rstrip("/")
            if (
                origin != expected_origin
                or not valid_token(token)
                or not hmac.compare_digest(
                    request.headers.get("x-csrf-token", "").encode(), token.encode()
                )
            ):
                return JSONResponse(
                    {
                        "detail": "Reload this local page before saving (origin or CSRF check failed)"
                    },
                    status_code=403,
                )
        request.state.csrf = token if valid_token(token) else new_token()
        response = await call_next(request)
        response.set_cookie(
            "reviewpulse_csrf", request.state.csrf, httponly=True, samesite="strict"
        )
        response.headers.update(
            {
                "Cache-Control": "no-store",
                "X-Content-Type-Options": "nosniff",
                "Content-Security-Policy": "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'",
                "Referrer-Policy": "no-referrer",
            }
        )
        return response

    def days_from(request):
        try:
            days = int(request.query_params.get("window", "7").removesuffix("d"))
            if days not in (7, 30):
                raise ValueError()
            return days
        except ValueError:
            raise HTTPException(400, "Reporting window must be 7 or 30 days")

    def pr_rows():
        rows = {
            (r["repo"], r["number"]): normalize_pr_row(r) for r in app.state.pr_rows
        }
        for finding in store.rows():
            key = (finding["repo"], finding["prNumber"])
            rows.setdefault(
                key,
                {
                    "repo": key[0],
                    "number": key[1],
                    "title": "PR from imported findings",
                    "riskScore": None,
                },
            )
        return list(rows.values())

    def filtered_prs(request, days):
        rows = pr_rows()
        q = request.query_params
        if q.get("window"):
            rows = window_pr_rows(rows, days=days)
        if q.get("riskMin") or q.get("risk") == "high":
            try:
                threshold = float(q.get("riskMin", "70"))
                if not 0 <= threshold <= 100:
                    raise ValueError()
            except ValueError:
                raise HTTPException(400, "Risk threshold must be between 0 and 100")
            rows = [
                r
                for r in rows
                if r.get("riskScore") is not None and r["riskScore"] >= threshold
            ]
        for field in ("repo", "signal", "pr"):
            value = q.get(field)
            if not value:
                continue
            if field == "repo":
                rows = [r for r in rows if r["repo"] == value]
            elif field == "pr":
                rows = [r for r in rows if str(r["number"]) == value]
            else:
                rows = [
                    r
                    for r in rows
                    if any(d.get("signal") == value for d in r.get("topDrivers", []))
                    or value in (r.get("signals") or {})
                ]
        return rows

    def finding_rows(request, view, days):
        if view in ("active", "done"):
            rows = build_dashboard_routes(store.rows(), [], pr_window_days=days)[view][
                "rows"
            ]
        else:
            rows = enrich_findings(store.rows())
        q = request.query_params
        rows = filter_findings(
            rows, **{key: q.get(key) for key in ("severity", "owner", "status", "repo")}
        )
        if any(q.get(k) for k in ("risk", "riskMin", "signal", "pr", "window")):
            keys = {(r["repo"], r["number"]) for r in filtered_prs(request, days)}
            rows = [r for r in rows if (r["repo"], r["prNumber"]) in keys]
        query = q.get("q", "").casefold()
        if query:
            rows = [
                r
                for r in rows
                if query
                in " ".join(
                    str(r.get(k, "")) for k in ("message", "path", "repo", "ruleId")
                ).casefold()
            ]
        if q.get("sort") == "updated":
            rows.sort(
                key=lambda r: (
                    parse_iso(r.get("updatedAt") or r.get("lastSeenAt"))
                    or utc_now("0001-01-01")
                ),
                reverse=True,
            )
        else:
            rows.sort(
                key=lambda r: (
                    SEVERITY_ORDER.get(r["severity"], 99),
                    -(r["ageHours"] or 0),
                    r["fingerprint"],
                )
            )
        return rows

    def render(request, view, **extra):
        with lock:
            days = days_from(request)
            rows = (
                finding_rows(request, view, days)
                if view in ("active", "done", "findings")
                else []
            )
            total = len(rows)
            try:
                page = max(1, int(request.query_params.get("page", "1")))
            except ValueError:
                raise HTTPException(400, "Page must be an integer")
            params = dict(request.query_params)

            def page_url(number):
                return request.url.path + "?" + urlencode({**params, "page": number})

            context = {
                "view": view,
                "demo": demo,
                "actor": actor,
                "error": app.state.load_error,
                "source": app.state.source,
                "refreshed": app.state.last_refresh,
                "csrf": request.state.csrf,
                "rows": rows[(page - 1) * 25 : page * 25],
                "total": total,
                "page": page,
                "previous": page_url(page - 1) if page > 1 else None,
                "next": page_url(page + 1) if page * 25 < total else None,
                "prs": filtered_prs(request, days) if view == "prs" else [],
                "risk": build_pr_risk_panel(pr_rows(), days=days),
                "days": days,
                "query": params,
                **extra,
            }
            return templates.TemplateResponse(
                request=request,
                name="dashboard.html",
                context=context,
                status_code=503 if app.state.load_error else 200,
            )

    @app.get("/", include_in_schema=False)
    def index():
        return RedirectResponse("/dashboard/active")

    @app.get("/dashboard/{view}", response_class=HTMLResponse)
    def dashboard(request: Request, view: str):
        if view not in ("active", "done", "risk", "findings", "prs"):
            raise HTTPException(404, "Page not found")
        return render(request, view)

    @app.get("/findings/{fingerprint}", response_class=HTMLResponse)
    def detail(request: Request, fingerprint: str):
        try:
            row = enrich_findings([store.get(fingerprint)])[0]
        except KeyError:
            raise HTTPException(404, "Finding not found")
        repo_parts = row["repo"].split("/")
        github_url = (
            f"https://github.com/{row['repo']}/pull/{row['prNumber']}"
            if len(repo_parts) == 2
            and all(
                re.fullmatch(r"[A-Za-z0-9_.-]+", part) and part not in (".", "..")
                for part in repo_parts
            )
            else None
        )
        return render(
            request,
            "detail",
            finding=row,
            history=audit_history(row),
            github_url=github_url,
        )

    @app.get("/evidence")
    def evidence(request: Request):
        # Query is preserved: PR, repository and signal drill into matching evidence.
        return RedirectResponse(
            "/dashboard/findings?" + urlencode(dict(request.query_params))
        )

    @app.get("/api/dashboard/{view}")
    def api_dashboard(request: Request, view: str):
        with lock:
            if app.state.load_error:
                raise HTTPException(503, app.state.load_error)
            days = days_from(request)
            if view in ("active", "done", "findings"):
                rows = finding_rows(request, view, days)
                payload = {
                    "route": f"/dashboard/{view}",
                    "rows": rows,
                    "total": len(rows),
                    "empty": not rows,
                }
            elif view == "prs":
                payload = {"rows": filtered_prs(request, days)}
            elif view == "risk":
                payload = build_dashboard_routes(
                    store.rows(), pr_rows(), pr_window_days=days
                )["risk"]
            else:
                raise HTTPException(404, "Page not found")
            return {
                **payload,
                "demo": demo,
                "source": app.state.source,
                "lastRefresh": app.state.last_refresh,
            }

    @app.post("/api/refresh")
    def refresh():
        if not reload_snapshot():
            raise HTTPException(503, app.state.load_error)
        return {"lastRefresh": app.state.last_refresh}

    @app.post("/api/findings/{fingerprint}/actions")
    def action(fingerprint: str, body: FindingAction):
        with lock:
            if app.state.load_error:
                raise HTTPException(
                    503, "Fix the source error and refresh before editing"
                )
            try:
                return store.action(fingerprint, actor=actor, **body.model_dump())
            except ConflictError as exc:
                raise HTTPException(409, str(exc))
            except KeyError:
                raise HTTPException(404, "Finding not found")
            except ValueError as exc:
                raise HTTPException(400, str(exc))

    return app


def main():
    parser = argparse.ArgumentParser(description="ReviewPulse local dashboard")
    parser.add_argument("--artifacts-dir", default="artifacts/pipeline-run")
    parser.add_argument("--pr-data", help="Optional JSON array of PR risk rows")
    parser.add_argument(
        "--state-dir",
        help="SQLite overlay directory (default ~/.local/state/reviewpulse)",
    )
    parser.add_argument(
        "--actor",
        default=getpass.getuser(),
        help="Local audit label; not a GitHub identity",
    )
    parser.add_argument(
        "--demo",
        action="store_true",
        help="Explicitly load labeled demo fixtures into a separate database",
    )
    parser.add_argument(
        "--host", choices=("127.0.0.1", "localhost"), default="127.0.0.1"
    )
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()
    import uvicorn

    app = create_app(
        artifacts_dir=args.artifacts_dir,
        state_dir=args.state_dir,
        pr_data=args.pr_data,
        demo=args.demo,
        actor=args.actor,
    )
    print(
        f"ReviewPulse: http://{args.host}:{args.port}/dashboard/active — {'DEMO' if args.demo else 'local artifacts'}; actor: {args.actor}"
    )
    uvicorn.run(app, host=args.host, port=args.port, proxy_headers=False)


if __name__ == "__main__":
    main()

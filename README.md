# ReviewPulse

Turn local GitHub/CodeRabbit review payloads into a findings queue, PR risk views and an auditable triage workflow.

## Install and launch

Requires Python 3.10 or newer.

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[dev]'
python -m src.pipeline YOUR_REVIEW_PAYLOAD.json --output-dir artifacts/pipeline-run
python -m src.server --artifacts-dir artifacts/pipeline-run
```

Open **http://127.0.0.1:8000/dashboard/active**. Stop the server with Ctrl-C.
The installed `reviewpulse` command accepts the same options as `python -m src.server`.

For a tour with clearly labeled sample data and a separate demo database:

```bash
python -m src.server --demo
```

The pipeline's no-argument command uses the repository's `fixtures/` examples;
pass your own payload files for real review data. The server loads real artifacts
by default and shows setup/error details if they are missing or malformed.
It never substitutes demo data automatically.

## Use the dashboard

- **Active findings:** search, filter severity/owner/status/repository, sort and page the queue. Open **Triage & evidence** for the source message and file location.
- **Local triage:** save an owner label, acknowledge a new finding, then start work or resolve/dismiss/accept risk. Completion and archiving require a rationale and checked confirmation. Reopen done findings with a rationale.
- **Done & archive:** inspect completed findings and their audit timeline, archive or reopen them.
- **PR risk overview:** select a 7 or 30 day window, follow repository and driver links, and inspect matching PRs and findings.
- **Refresh snapshot:** import the latest pipeline output. Local assignments, status, and audit survive refreshes and server restarts. Findings missing from the latest snapshot remain visible with an absence label.

Edits stay on this computer. The actor defaults to your OS username; change it
with `--actor NAME`. This is a local audit label, not a verified GitHub identity.
The dashboard does not change GitHub reviews, assignments or issues, and does not
synchronize live GitHub data. External PR links open GitHub separately.

SQLite state lives at `~/.local/state/reviewpulse/triage.sqlite3` (demo uses
`demo.sqlite3`). Use `--state-dir PATH` for a separate project or dataset. Back up
this database to retain local triage. Source JSON files remain unchanged. Stale
edits return a conflict rather than overwriting another tab's changes; reload
before retrying. After a server restart, reload existing tabs to refresh CSRF tokens.
The server binds to loopback and accepts same-origin local edits.

## PR risk data

The pipeline does not infer PR risk from finding severity. To supply scores:

```bash
python -m src.server --artifacts-dir artifacts/pipeline-run --pr-data prs.json
```

`prs.json` is an array of objects:

```json
[
  {
    "repo": "owner/repository",
    "number": 42,
    "title": "Improve retry behavior",
    "updatedAt": "2026-10-22T12:00:00Z",
    "riskScore": 82,
    "topDrivers": [{"signal": "churn", "score": 90}]
  }
]
```

You can supply `signals` instead of `riskScore`: `test_delta`, `churn`,
`ownership_hotspot`, and `prior_defect_density` have weights 20/25/25/30.
Scores are 0–100. Missing scores remain unknown. Timestamps use `updatedAt`,
then `mergedAt`, then `createdAt`; naive timestamps are UTC. Missing and future
dates do not enter reporting windows. High risk is **>=70**. Trend is the count
difference versus the previous equal window using only supplied PR records;
it does not reconstruct a historical score series. Coverage is displayed.
PRs referenced by findings appear in the PR list even without supplied risk data.

## Pipeline artifacts

```bash
python -m src.pipeline fixtures/adapter_github_review_payload.json fixtures/adapter_coderabbit_payload.json --output-dir /tmp/reviewpulse-run
```

Outputs include `normalized-findings.json` (full records with timestamps and stable
fingerprints for the dashboard), `ranked-findings.json` (deduplicated clusters),
`pr-summary.md`, `metrics.json`, `invalid-findings.json`, `dead-letter.jsonl`
(for terminal failures), `reliability-metrics.json` and `reliability-events.json`.
Rerun the current pipeline if you only have older ranked artifacts.

```bash
python -m src.replay_dlq --dry-run
python -m src.replay_dlq
```

## Verification

```bash
ruff check src tests scripts
python -m pytest -q
python -m playwright install chromium
RUN_BROWSER_TESTS=1 python -m pytest tests/test_browser.py -q
python -m build
python scripts/smoke_wheel.py
```

Browser acceptance exercises real artifact loading, filtering, local assignment,
confirmation, closure/reopening, risk drilldowns, error recovery and mobile layout.
The wheel smoke installs into a fresh environment and verifies pages, assets
and schema outside the checkout. CI runs Python 3.10/3.12 and Chromium acceptance.

See [dashboard domain contract](docs/dashboard-domain.md),
[finding schema](docs/finding-schema.md), [summary contract](docs/pr-summary-contract.md),
[idempotency contract](docs/idempotency-contract.md) and
[reliability runbook](docs/reliability-runbook.md). Earlier UX docs describe design
proposals; the domain contract and this guide describe the implemented dashboard.

# reviewpulse
Open-source PR review-to-fix loop automation for GitHub + CodeRabbit

## Quickstart (one-command MVP flow)
Run deterministic intake -> normalize -> dedupe/rank -> PR summary artifact generation:

```bash
python3 -m src.pipeline
```

Artifacts are written to `artifacts/pipeline-run/`:
- `ranked-findings.json`
- `pr-summary.md`
- `metrics.json`
- `invalid-findings.json`
- `dead-letter.jsonl` (terminal failures with payload + reason metadata)
- `reliability-metrics.json`
- `reliability-events.json`

You can also pass explicit payload files and custom output path:

```bash
python3 -m src.pipeline fixtures/adapter_github_review_payload.json fixtures/adapter_coderabbit_payload.json --output-dir /tmp/reviewpulse-run
```

Replay tooling (safe by default):

```bash
# Preview replay plan without mutating replay ledger
python3 -m src.replay_dlq --dry-run

# Mark entries replayed (idempotent; already replayed entries are skipped)
python3 -m src.replay_dlq
```

## Current foundation docs
- `docs/finding-schema.md` — canonical deterministic finding schema and fingerprint formula
- `docs/slice-b-ingest-handoff.md` — handoff contract for next ingest adapter slices
- `docs/pr-summary-contract.md` — deterministic PR summary + baseline metrics contract
- `docs/reliability-runbook.md` — reliability metrics/log outputs + DLQ triage/replay procedure

# Reliability Metrics + Replay Runbook

## Signals produced per pipeline run

`python3 -m src.pipeline` now emits deterministic reliability artifacts in `artifacts/pipeline-run/`:

- `reliability-metrics.json`
  - `processed`
  - `retried`
  - `deadLettered`
  - `replayed`
- `reliability-events.json`
  - one event per payload handled in the run, with:
    - `timestamp`
    - `event`
    - `payloadFile`
    - `attempts`
    - optional `reason`

## Triage checklist

1. Run pipeline:
   - `python3 -m src.pipeline`
2. Open reliability metrics:
   - `cat artifacts/pipeline-run/reliability-metrics.json`
3. If `deadLettered > 0`, inspect failed payloads:
   - `jq '.[] | select(.event=="dead_lettered")' artifacts/pipeline-run/reliability-events.json`
4. Cross-check detailed validation failures:
   - `cat artifacts/pipeline-run/invalid-findings.json`

## Replay procedure (minimal)

For any dead-lettered payload path from `reliability-events.json`:

1. Fix payload or adapter mapping issue.
2. Re-run pipeline on the specific payload:
   - `python3 -m src.pipeline <payload-file-path> --output-dir /tmp/reviewpulse-replay`
3. Confirm replay output:
   - `cat /tmp/reviewpulse-replay/reliability-metrics.json`
   - Expect `deadLettered: 0` for that corrected payload.

## Notes

- `retried` and `replayed` counters are instrumentation-ready for upcoming retry/DLQ slices.
- This runbook intentionally stays deterministic and file-artifact-based for automation compatibility.

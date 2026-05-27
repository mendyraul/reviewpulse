# Done-State UX Regression Checklist

Issue: #54

## Done-state UI treatment
- Done findings must be visually distinct from active findings (`doneState=true` in board payload).
- Done statuses are limited to `resolved` and `archived` in board flows.
- Done rows must include timeline events that show who performed the state transition and when.

## Completion confirmation patterns
- Single-item close requires valid transition path (`new -> triaged -> in_progress -> resolved`).
- Bulk close from active findings returns `updated`, `skipped`, and `errors` so users can confirm outcomes.
- Transition action appends timeline entry with `event=status_transition` for traceability.

## Dashboard regression checks
1. `/dashboard/active` only includes actionable findings.
2. `/dashboard/done` only includes completed findings.
3. Owner route and stale flags remain unchanged for non-done records.
4. PR risk summary still renders with no schema or key changes.

## Quick verification commands
```bash
python -m unittest tests/test_board.py
python -m unittest tests/test_active_findings_board.py
python -m unittest tests/test_dashboard_routes.py
python -m unittest tests/test_pr_risk_summary.py
```

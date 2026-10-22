# Dashboard domain contract

`board.py` owns enrichment, filters, sorting, paging and owner routing.
`risk_dashboard.py` owns scoring and the single `build_pr_risk_panel` aggregate.
`workflow.py` owns transitions and audit history. `dashboard_routes.py` composes public route payloads.
The former active_findings_board, owner_routing, done_state, pr_risk_summary,
dashboard_risk_panel and dashboard_risk_summary modules have been removed;
callers import their retained helpers from the owners above.

Active states: new, triaged, in_progress.
Done states: resolved, dismissed, accepted_risk, archived.
Legacy open/acknowledged/reopened inputs map to new/triaged/in_progress.
Historical events retain their original labels. New events use history, merging
legacy timeline/statusHistory entries without losing distinct events.

New findings must be triaged before work or closure. Triaged and in-progress
findings can be completed; completion and archive require an actor, rationale
and explicit confirmation. Completed findings can be archived or reopened to
in_progress; reopening requires an actor and rationale. Bulk actions follow
the same rules and never supply implicit confirmation.

Risk aggregates accept only 7 or 30 days and treat scores >=70 as high risk.
The recommendation threshold remains separate: a score of 70 requires review,
while >70 recommends blocking. Timestamps use updatedAt, then mergedAt, then
createdAt, interpreted as UTC if naive. Future and missing timestamps do not
enter a reporting window. Missing scores remain unknown; finding severity is
never converted into a PR score. Generator inputs behave like lists.

Run all regressions with `python -m pytest -q`.
Earlier UX documents are design proposals; this contract describes implemented behavior.

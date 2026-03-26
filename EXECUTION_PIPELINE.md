# Execution Pipeline (Start-to-Finish)

## 1) Discover
Input: PR comments, CodeRabbit findings, issue feedback
Output: candidate tasks with deterministic keys

## 2) Decide
Score by severity, merge-blocking risk, and fix effort
Output: prioritized execution queue

## 3) Build
- Implement smallest safe slice
- Add tests + fixtures for failure classes
- Keep changes replay-safe and deterministic

## 4) Validate
- Unit + integration tests
- Dry-run on fixture PR payloads
- Live run on one pilot repo PR

## 5) Ship
- Feature branch + PR to dev/main workflow
- CI checks must pass
- Release notes with user-facing impact

## 6) Learn
- Track time-to-green and unresolved findings age
- Capture top failure patterns
- Feed back into backlog weekly

## Guardrails
- No direct push to main/master
- Every feature must map to user pain and success metric
- If integration blocked (token/webhook/auth), mark blocked immediately with exact unblock path

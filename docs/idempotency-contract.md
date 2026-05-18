# Idempotency Contract (Slice A)

## Goal
Prevent duplicate FindingDraft creation when the same inbound review event is replayed.

## Normalization helper
`src/idempotency.py::normalize_idempotency_key(payload)` applies deterministic normalization:

1. Preferred keys (in order):
   - `idempotency_key`
   - `idempotencyKey`
   - `event_id`
2. If no explicit key exists, derive one from a canonical JSON SHA-256 hash of the payload.
3. Final key is trimmed and lowercased.

## Persistence adapter contract
`IdempotencyStore` protocol:
- `seen(key: str) -> bool`
- `remember(key: str, fingerprint: str) -> None`

First implementation: `InMemoryIdempotencyStore` for deterministic local tests.

## FindingDraft ingest behavior
`src/intake.py::ingest_finding_event(...)` behavior:
- Normalize finding
- Check idempotency key
- **First write**: accepted (`True`) and finding persisted to `FindingDraftStore`
- **Replay duplicate**: rejected (`False`) and no additional finding persisted

## Test evidence
`tests/test_idempotency.py` validates:
- key normalization (`EVT-123` -> `evt-123`)
- first-write acceptance
- duplicate replay rejection
- exactly one FindingDraft entry created for duplicate replays

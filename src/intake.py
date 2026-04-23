from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Protocol

from src.idempotency import IdempotencyStore, check_and_remember
from src.normalize import normalize_finding


class FindingDraftStore(Protocol):
    def add(self, finding: Dict[str, Any]) -> None: ...


@dataclass
class InMemoryFindingDraftStore:
    findings: List[Dict[str, Any]]

    def __init__(self) -> None:
        self.findings = []

    def add(self, finding: Dict[str, Any]) -> None:
        self.findings.append(finding)


def ingest_finding_event(
    payload: Dict[str, Any],
    *,
    idempotency_store: IdempotencyStore,
    finding_store: FindingDraftStore,
) -> bool:
    """Returns True when accepted/created, False when rejected as replay duplicate."""
    finding = normalize_finding(payload)
    accepted = check_and_remember(payload, store=idempotency_store, fingerprint=finding["fingerprint"])
    if not accepted:
        return False
    finding_store.add(finding)
    return True

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any, Dict, Optional, Protocol


class IdempotencyStore(Protocol):
    """Persistence adapter contract for idempotency keys."""

    def seen(self, key: str) -> bool: ...

    def remember(self, key: str, fingerprint: str) -> None: ...


@dataclass
class InMemoryIdempotencyStore:
    """Deterministic in-memory adapter for local tests/first implementation."""

    _keys: Dict[str, str]

    def __init__(self) -> None:
        self._keys = {}

    def seen(self, key: str) -> bool:
        return key in self._keys

    def remember(self, key: str, fingerprint: str) -> None:
        self._keys[key] = fingerprint


def _stable_payload_hash(payload: Dict[str, Any]) -> str:
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def normalize_idempotency_key(payload: Dict[str, Any]) -> str:
    """Normalize explicit keys, else derive one from deterministic payload hash."""
    candidate = payload.get("idempotency_key") or payload.get("idempotencyKey") or payload.get("event_id")
    if candidate is None:
        candidate = _stable_payload_hash(payload)
    return str(candidate).strip().lower()


def check_and_remember(
    payload: Dict[str, Any],
    *,
    store: IdempotencyStore,
    fingerprint: Optional[str] = None,
) -> bool:
    """Return True for first-write acceptance, False for duplicate replay rejection."""
    key = normalize_idempotency_key(payload)
    if store.seen(key):
        return False
    store.remember(key, fingerprint or "")
    return True

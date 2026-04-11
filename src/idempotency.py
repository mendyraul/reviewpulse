from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from threading import Lock
from typing import Any, Dict, Optional, Protocol


class IdempotencyStore(Protocol):
    """Persistence adapter contract for idempotency keys."""

    def remember_if_absent(self, key: str, fingerprint: str) -> bool: ...


@dataclass
class InMemoryIdempotencyStore:
    """Deterministic in-memory adapter for local tests/first implementation."""

    _keys: Dict[str, str]
    _lock: Lock

    def __init__(self) -> None:
        self._keys = {}
        self._lock = Lock()

    def remember_if_absent(self, key: str, fingerprint: str) -> bool:
        with self._lock:
            if key in self._keys:
                return False
            self._keys[key] = fingerprint
            return True


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
    return store.remember_if_absent(key, fingerprint or "")

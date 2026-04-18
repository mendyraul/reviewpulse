from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple, Type


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


@dataclass(frozen=True)
class RetryPolicy:
    max_attempts: int = 3
    base_delay_seconds: float = 0.5
    max_delay_seconds: float = 5.0

    def delay_for_attempt(self, attempt: int) -> float:
        # attempt is 1-indexed (attempt=1 means first retry wait after initial failure)
        bounded_attempt = max(1, attempt)
        delay = self.base_delay_seconds * (2 ** (bounded_attempt - 1))
        return min(delay, self.max_delay_seconds)


RETRYABLE_EXCEPTIONS: Tuple[Type[BaseException], ...] = (TimeoutError, ConnectionError)


def is_retryable_error(error: BaseException) -> bool:
    return isinstance(error, RETRYABLE_EXCEPTIONS)


def _stable_json(payload: Dict[str, Any]) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"))


def _payload_hash(payload: Dict[str, Any]) -> str:
    return hashlib.sha256(_stable_json(payload).encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class DeadLetterEntry:
    payload_file: str
    reason: str
    payload: Dict[str, Any]
    attempts: int = 1
    created_at: str = field(default_factory=_utc_now_iso)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "version": 1,
            "id": f"dlq-{_payload_hash(self.payload)}",
            "createdAt": self.created_at,
            "payloadFile": self.payload_file,
            "reason": self.reason,
            "attempts": self.attempts,
            "payloadHash": _payload_hash(self.payload),
            "payload": self.payload,
        }


class DeadLetterQueue:
    def __init__(self, path: Path) -> None:
        self.path = path

    def write(self, entry: DeadLetterEntry) -> Dict[str, Any]:
        record = entry.to_dict()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, sort_keys=True) + "\n")
        return record

    def read_entries(self) -> List[Dict[str, Any]]:
        if not self.path.exists():
            return []

        entries: List[Dict[str, Any]] = []
        for line in self.path.read_text(encoding="utf-8").splitlines():
            raw = line.strip()
            if not raw:
                continue
            entries.append(json.loads(raw))
        return entries


class ReplayLedger:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def _load(self) -> Dict[str, Any]:
        if not self.path.exists():
            return {"replayedIds": []}
        return json.loads(self.path.read_text(encoding="utf-8"))

    def _save(self, state: Dict[str, Any]) -> None:
        self.path.write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")

    def has_replayed(self, entry_id: str) -> bool:
        state = self._load()
        return entry_id in state.get("replayedIds", [])

    def mark_replayed(self, entry_id: str) -> None:
        state = self._load()
        ids = list(state.get("replayedIds", []))
        if entry_id not in ids:
            ids.append(entry_id)
            state["replayedIds"] = sorted(ids)
            self._save(state)


@dataclass
class ReliabilityTracker:
    processed: int = 0
    retried: int = 0
    dead_lettered: int = 0
    replayed: int = 0
    events: List[Dict[str, Any]] = field(default_factory=list)

    def _record(self, event: str, payload_file: str, *, reason: Optional[str] = None, attempts: int = 1) -> None:
        item: Dict[str, Any] = {
            "timestamp": _utc_now_iso(),
            "event": event,
            "payloadFile": payload_file,
            "attempts": attempts,
        }
        if reason:
            item["reason"] = reason
        self.events.append(item)

    def record_processed(self, payload_file: str) -> None:
        self.processed += 1
        self._record("processed", payload_file)

    def record_retry(self, payload_file: str, *, reason: str, attempts: int) -> None:
        self.retried += 1
        self._record("retried", payload_file, reason=reason, attempts=attempts)

    def record_dead_letter(self, payload_file: str, *, reason: str, attempts: int = 1) -> None:
        self.dead_lettered += 1
        self._record("dead_lettered", payload_file, reason=reason, attempts=attempts)

    def record_replay(self, payload_file: str) -> None:
        self.replayed += 1
        self._record("replayed", payload_file)

    def metrics(self) -> Dict[str, int]:
        return {
            "processed": self.processed,
            "retried": self.retried,
            "deadLettered": self.dead_lettered,
            "replayed": self.replayed,
        }


def replay_dead_letters(
    entries: Iterable[Dict[str, Any]],
    *,
    ledger: ReplayLedger,
    dry_run: bool = True,
    tracker: Optional[ReliabilityTracker] = None,
) -> Dict[str, int]:
    reliability = tracker or ReliabilityTracker()
    attempted = 0
    skipped = 0

    for entry in entries:
        entry_id = str(entry.get("id", ""))
        payload_file = str(entry.get("payloadFile", "<unknown>"))
        if not entry_id:
            skipped += 1
            continue

        if ledger.has_replayed(entry_id):
            skipped += 1
            continue

        attempted += 1
        reliability.record_replay(payload_file)
        if not dry_run:
            ledger.mark_replayed(entry_id)

    return {
        "attempted": attempted,
        "skipped": skipped,
        "replayed": reliability.replayed,
    }

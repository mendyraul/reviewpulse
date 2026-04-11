from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple, Type


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

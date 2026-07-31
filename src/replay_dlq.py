from __future__ import annotations

import argparse
import json
from pathlib import Path

from src.reliability import DeadLetterQueue, ReplayLedger, replay_dead_letters


def main() -> int:
    parser = argparse.ArgumentParser(description="Replay ReviewPulse dead-letter events with idempotency guardrails")
    parser.add_argument("--dlq", default="artifacts/pipeline-run/dead-letter.jsonl", help="Path to dead-letter JSONL file")
    parser.add_argument(
        "--ledger",
        default="artifacts/pipeline-run/replay-ledger.json",
        help="Path to replay ledger file",
    )
    parser.add_argument("--dry-run", action="store_true", help="Plan replay only; do not mark entries as replayed")
    args = parser.parse_args()

    dlq = DeadLetterQueue(Path(args.dlq))
    ledger = ReplayLedger(Path(args.ledger))
    report = replay_dead_letters(dlq.read_entries(), ledger=ledger, dry_run=args.dry_run)
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

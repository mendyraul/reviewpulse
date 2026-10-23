"""SQLite triage overlay. Imported artifacts are never modified."""

import json
import sqlite3
from contextlib import contextmanager
from pathlib import Path

from .workflow import audit_history, normalize_status, transition_status
from .time_utils import utc_now

TRIAGE_FIELDS = {
    "owner",
    "status",
    "history",
    "updatedAt",
    "closedAt",
    "closeRationale",
    "resolvedAt",
    "archivedAt",
    "reopenedAt",
    "resolution",
}


class ConflictError(ValueError):
    pass


class LocalStore:
    def __init__(self, path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as db:
            db.executescript("""
                CREATE TABLE IF NOT EXISTS findings (
                    fingerprint TEXT PRIMARY KEY, snapshot TEXT NOT NULL,
                    triage TEXT NOT NULL DEFAULT '{}', revision INTEGER NOT NULL DEFAULT 0,
                    present INTEGER NOT NULL DEFAULT 1);
                CREATE TABLE IF NOT EXISTS audit (
                    id INTEGER PRIMARY KEY, fingerprint TEXT NOT NULL,
                    event TEXT NOT NULL);
            """)

    @contextmanager
    def connect(self):
        db = sqlite3.connect(self.path, timeout=10)
        db.row_factory = sqlite3.Row
        try:
            with db:
                yield db
        finally:
            db.close()

    def import_snapshot(self, rows):
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            # Snapshot presence changes invalidate stale clients as well as edits.
            db.execute(
                "UPDATE findings SET present=0, revision=revision+1 WHERE present=1"
            )
            for row in rows:
                db.execute(
                    """INSERT INTO findings (fingerprint,snapshot) VALUES (?,?)
                    ON CONFLICT(fingerprint) DO UPDATE SET snapshot=excluded.snapshot,
                    present=1, revision=findings.revision+1""",
                    (row["fingerprint"], json.dumps(row)),
                )

    @staticmethod
    def compose(record):
        if record is None:
            raise KeyError("Finding not found")
        snapshot = json.loads(record["snapshot"])
        triage = json.loads(record["triage"])
        row = {**snapshot, **triage}
        for key, value in triage.items():
            if value is None:
                row.pop(key, None)
        row["history"] = audit_history(
            {"history": audit_history(snapshot), "timeline": triage.get("history", [])}
        )
        row["status"] = normalize_status(row.get("status"))
        row["revision"] = record["revision"]
        row["presentInSnapshot"] = bool(record["present"])
        return row

    def rows(self):
        with self.connect() as db:
            return [
                self.compose(r)
                for r in db.execute("SELECT * FROM findings ORDER BY fingerprint")
            ]

    def get(self, fingerprint):
        with self.connect() as db:
            return self.compose(
                db.execute(
                    "SELECT * FROM findings WHERE fingerprint=?", (fingerprint,)
                ).fetchone()
            )

    def action(
        self,
        fingerprint,
        *,
        action,
        actor,
        revision,
        owner=None,
        rationale=None,
        confirmed=False,
    ):
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            record = db.execute(
                "SELECT * FROM findings WHERE fingerprint=?", (fingerprint,)
            ).fetchone()
            row = self.compose(record)
            if row["revision"] != revision:
                raise ConflictError(
                    "This finding changed. Reload it before saving again."
                )
            at = utc_now().isoformat()
            if action == "assign":
                if not actor.strip() or not isinstance(owner, str) or len(owner) > 100:
                    raise ValueError(
                        "An actor and owner label (up to 100 characters) are required"
                    )
                event = {
                    "event": "owner_assigned",
                    "actor": actor,
                    "at": at,
                    "fromOwner": row.get("owner"),
                    "owner": owner.strip() or "unassigned",
                }
                updated = {
                    **row,
                    "owner": event["owner"],
                    "history": [*row["history"], event],
                    "updatedAt": at,
                }
            else:
                targets = {
                    "acknowledge": "triaged",
                    "start": "in_progress",
                    "reopen": "in_progress",
                    "resolved": "resolved",
                    "dismissed": "dismissed",
                    "accepted_risk": "accepted_risk",
                    "archive": "archived",
                }
                if action not in targets:
                    raise ValueError("Unknown local action")
                if action == "reopen" and row["status"] not in {
                    "resolved",
                    "dismissed",
                    "accepted_risk",
                    "archived",
                }:
                    raise ValueError("Only done findings can be reopened")
                updated = transition_status(
                    row,
                    targets[action],
                    actor=actor,
                    at_iso=at,
                    reason=rationale,
                    confirmed=confirmed,
                )
                event = updated["history"][-1]
            # Keep an append-only independent audit log in the same transaction.
            db.execute(
                "INSERT INTO audit(fingerprint,event) VALUES (?,?)",
                (fingerprint, json.dumps(event)),
            )
            overlay = {key: updated.get(key) for key in TRIAGE_FIELDS}
            db.execute(
                "UPDATE findings SET triage=?, revision=revision+1 WHERE fingerprint=?",
                (json.dumps(overlay), fingerprint),
            )
            return {**updated, "revision": row["revision"] + 1}

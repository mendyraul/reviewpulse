"""Shared UTC parsing: naive artifact timestamps are interpreted as UTC."""

from datetime import datetime, timezone


def parse_iso(value):
    if not isinstance(value, str) or not value:
        return None
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return (
            dt.replace(tzinfo=timezone.utc)
            if dt.tzinfo is None
            else dt.astimezone(timezone.utc)
        )
    except ValueError:
        return None


def utc_now(value=None):
    if value is None:
        return datetime.now(timezone.utc)
    parsed = parse_iso(value)
    if parsed is None:
        raise ValueError("Invalid reporting timestamp")
    return parsed

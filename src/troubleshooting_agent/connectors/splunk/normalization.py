
import re
from typing import Any


REDACTION_PATTERNS = [
    # Authorization headers and bearer tokens
    (
        re.compile(
            r"(?i)(authorization\s*[:=]\s*['\"]?\s*bearer\s+)"
            r"[^'\"\s,}]+"
        ),
        r"\1[REDACTED]",
    ),
    # Common named secrets
    (
        re.compile(
            r"(?i)((?:api[_-]?key|access[_-]?token|refresh[_-]?token|"
            r"secret[_-]?key|password|client[_-]?secret)\s*[:=]\s*"
            r"['\"])[^'\"]*(['\"])"
        ),
        r"\1[REDACTED]\2",
    ),
    # Common JSON token/password fields
    (
        re.compile(
            r'(?i)("(?:token|password|api_key|access_token|'
            r'refresh_token|client_secret)"\s*:\s*")[^"]*(")'
        ),
        r"\1[REDACTED]\2",
    ),
    # Email addresses
    (
        re.compile(
            r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b"
        ),
        "[EMAIL_REDACTED]",
    ),
    # Phone-number-like values (intentionally conservative)
    (
        re.compile(
            r"(?<!\w)(?:\+?1[-.\s]?)?"
            r"\(?\d{3}\)?[-.\s]\d{3}[-.\s]\d{4}(?!\w)"
        ),
        "[PHONE_REDACTED]",
    ),
]


def redact_text(value: str) -> str:
    """Redact common secrets and personal identifiers from text."""
    for pattern, replacement in REDACTION_PATTERNS:
        value = pattern.sub(replacement, value)
    return value


def _safe_value(value: Any) -> Any:
    """Recursively sanitize values while preserving JSON-compatible types."""
    if isinstance(value, str):
        return redact_text(value)

    if isinstance(value, dict):
        return {
            redact_text(str(key)): _safe_value(item)
            for key, item in value.items()
        }

    if isinstance(value, list):
        return [_safe_value(item) for item in value]

    if isinstance(value, (int, float, bool)) or value is None:
        return value

    return redact_text(str(value))


def normalize_log_event(event: dict) -> dict:
    """Return a sanitized, normalized representation of a Splunk event."""
    safe_event = _safe_value(event)

    if not isinstance(safe_event, dict):
        safe_event = {"message": str(safe_event)}

    # Splunk commonly wraps indexed event fields under "_raw".
    raw = safe_event.get("_raw")
    if isinstance(raw, str):
        safe_event["message"] = raw

    # Keep event data bounded before passing it to the LLM.
    for field in ("message", "_raw"):
        value = safe_event.get(field)
        if isinstance(value, str) and len(value) > 4000:
            safe_event[field] = value[:4000] + " [TRUNCATED]"

    return safe_event


def normalize_log_events(events: list[dict]) -> list[dict]:
    """Sanitize a collection of Splunk events."""
    return [normalize_log_event(event) for event in events]

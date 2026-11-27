"""Outbound privacy scanner: redacts user-typed PII and blocks PII elsewhere."""

import copy
import re
from typing import Any, Dict, List

PII_PATTERNS = [
    ("PHONE", re.compile(r"\b(?:\+91[\-\s]?)?[6-9]\d{9}\b")),
    ("EMAIL", re.compile(r"\b[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}\b")),
    ("METER_ID", re.compile(r"\bMTR-\d+\b", re.IGNORECASE)),
    ("ADDRESS", re.compile(r"\b\d{1,4}\s+[A-Za-z0-9\s]{2,25}\b(?:Layout|Street|St|Road|Rd|Avenue|Ave|Cross|Main)\b", re.IGNORECASE)),
]


class PrivacyViolationError(ValueError):
    """Raised when PII is detected in system, tool, or assistant messages."""


def _has_pii(text: str) -> bool:
    return any(pat.search(text) for _, pat in PII_PATTERNS)


def _redact(text: str) -> str:
    out = text
    for label, pat in PII_PATTERNS:
        out = pat.sub(f"[REDACTED_{label}]", out)
    return out


def scan(messages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Redact user-typed PII; raise PrivacyViolationError if PII appears anywhere else."""
    cleaned = copy.deepcopy(messages)
    for msg in cleaned:
        content = msg.get("content") or ""
        if not isinstance(content, str) or not content:
            continue
        if msg.get("role") == "user":
            msg["content"] = _redact(content)
        else:
            if _has_pii(content):
                raise PrivacyViolationError(
                    f"Blocked outbound LLM request: PII detected in '{msg.get('role')}' message."
                )
    return cleaned

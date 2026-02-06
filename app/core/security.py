"""
Security helpers (redaction/masking)
"""

from __future__ import annotations

import re
from typing import Any
from app.core.constants import SENSITIVE_FIELD_NAMES


_SENSITIVE_VALUE_PATTERNS = [
    re.compile(r"(?i)(api[_-]?key|token|password|cookie|authorization)\s*[:=]\s*([^\s,;]+)"),
    re.compile(r"(?i)bearer\s+([A-Za-z0-9\-._~+/]+=*)"),
]


def redact_sensitive(text: str) -> str:
    """Redact sensitive tokens from a string."""
    if not text:
        return text
    redacted = text
    for pattern in _SENSITIVE_VALUE_PATTERNS:
        redacted = pattern.sub(lambda m: f"{m.group(1)}=***", redacted)
    return redacted


def _should_mask_key(key: str) -> bool:
    key_lower = key.lower()
    return any(name in key_lower for name in SENSITIVE_FIELD_NAMES)


def mask_secret(value: str, prefix_len: int = 4, suffix_len: int = 4) -> str:
    """Mask a secret value, keeping only prefix/suffix characters visible."""
    if value is None:
        return ""
    text = str(value)
    if not text:
        return ""
    keep = prefix_len + suffix_len
    if len(text) <= keep:
        return "*" * len(text)
    return f"{text[:prefix_len]}{'*' * (len(text) - keep)}{text[-suffix_len:]}"


def mask_sensitive_data(data: Any) -> Any:
    """Recursively mask sensitive fields in dicts/lists."""
    if isinstance(data, dict):
        masked = {}
        for k, v in data.items():
            if isinstance(k, str) and _should_mask_key(k):
                if isinstance(v, str):
                    masked[k] = mask_secret(v)
                elif v is None:
                    masked[k] = ""
                else:
                    masked[k] = "***"
            else:
                masked[k] = mask_sensitive_data(v)
        return masked
    if isinstance(data, list):
        return [mask_sensitive_data(item) for item in data]
    if isinstance(data, str):
        return redact_sensitive(data)
    return data

from __future__ import annotations

import re
from collections.abc import Mapping


_EMBY_AUTHORIZATION_HEADER_KV_RE = re.compile(r'([A-Za-z][A-Za-z0-9]*)="([^"]*)"')


def parse_emby_authorization_header(header_value: str | None) -> dict[str, str]:
    text = str(header_value or "").strip()
    if not text:
        return {}

    scheme, _, _ = text.partition(" ")
    if scheme.lower() not in {"emby", "mediabrowser"}:
        return {}

    parsed: dict[str, str] = {}
    for match in _EMBY_AUTHORIZATION_HEADER_KV_RE.finditer(text):
        key = match.group(1).strip().lower()
        value = match.group(2).strip()
        if key and value:
            parsed[key] = value
    return parsed


def resolve_emby_authorization_context(headers: Mapping[str, str]) -> dict[str, str]:
    context: dict[str, str] = {}
    for header_name in ("X-Emby-Authorization", "Authorization"):
        for key, value in parse_emby_authorization_header(headers.get(header_name)).items():
            context.setdefault(key, value)
    return context


def resolve_emby_client_name(headers: Mapping[str, str], auth_context: dict[str, str] | None = None) -> str | None:
    return headers.get("X-Emby-Client") or (auth_context or {}).get("client")


def resolve_emby_device_name(headers: Mapping[str, str], auth_context: dict[str, str] | None = None) -> str | None:
    return headers.get("X-Emby-Device-Name") or (auth_context or {}).get("device")

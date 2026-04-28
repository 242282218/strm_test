"""
播放决策服务

统一收口以下判断：
1. 是否优先走直链
2. 哪些客户端强制走代理
3. 哪些上游 host 强制走代理
"""

from __future__ import annotations

from dataclasses import dataclass
from fnmatch import fnmatch
from urllib.parse import urlparse

from app.services.config_service import get_config_service
from app.services.playback_route_health_service import (
    PlaybackRouteHealthService,
    get_playback_route_health_service,
)


_WEB_CLIENT_HINTS = (
    "emby web",
    "jellyfin web",
    "web",
    "chrome",
    "edge",
    "firefox",
    "safari",
    "browser",
)


@dataclass(slots=True)
class PlaybackDecision:
    mode: str
    reason: str
    client_class: str


class PlaybackDecisionService:
    def __init__(self, config_getter=None, route_health_service: PlaybackRouteHealthService | None = None):
        self._config_getter = config_getter or (lambda: get_config_service().get_config())
        if route_health_service is None:
            route_health_service = get_playback_route_health_service()
            route_health_service._config_getter = self._config_getter
        self._route_health_service = route_health_service

    def decide_hook_mode(
        self,
        *,
        is_web_client: bool,
        client_name: str | None,
        device_name: str | None,
        user_agent: str | None,
        has_stable_url: bool,
    ) -> PlaybackDecision:
        client_class = self.classify_client(
            is_web_client=is_web_client,
            client_name=client_name,
            device_name=device_name,
            user_agent=user_agent,
        )
        if is_web_client:
            return PlaybackDecision(mode="emby_stream", reason="web_client", client_class=client_class)
        if self._should_force_proxy_by_client(client_class):
            return PlaybackDecision(mode="emby_stream", reason="force_proxy_client", client_class=client_class)
        if has_stable_url:
            return PlaybackDecision(mode="stable", reason="stable_entry", client_class=client_class)
        return PlaybackDecision(mode="legacy_redirect", reason="legacy_redirect", client_class=client_class)

    def decide_delivery_mode(
        self,
        *,
        client_name: str | None = None,
        device_name: str | None = None,
        user_agent: str | None = None,
        direct_url: str | None = None,
    ) -> PlaybackDecision:
        client_class = self.classify_client(
            is_web_client=self._looks_like_web_client(client_name, device_name, user_agent),
            client_name=client_name,
            device_name=device_name,
            user_agent=user_agent,
        )

        playback_cfg = getattr(self._config_getter(), "playback", None)
        direct_first = bool(getattr(playback_cfg, "direct_first", True))
        if not direct_first:
            return PlaybackDecision(mode="proxy", reason="direct_disabled", client_class=client_class)
        if self._should_force_proxy_by_client(client_class):
            return PlaybackDecision(mode="proxy", reason="force_proxy_client", client_class=client_class)
        if self._should_force_proxy_by_host(direct_url):
            return PlaybackDecision(mode="proxy", reason="force_proxy_host", client_class=client_class)
        if self._route_health_service.should_sticky_proxy(client_class=client_class, direct_url=direct_url):
            return PlaybackDecision(mode="proxy", reason="sticky_downgrade", client_class=client_class)
        return PlaybackDecision(mode="direct", reason="direct_first", client_class=client_class)

    def record_direct_failure(
        self,
        *,
        client_name: str | None,
        device_name: str | None,
        user_agent: str | None,
        direct_url: str | None,
        reason: str,
    ) -> None:
        client_class = self.classify_client(
            is_web_client=self._looks_like_web_client(client_name, device_name, user_agent),
            client_name=client_name,
            device_name=device_name,
            user_agent=user_agent,
        )
        self._route_health_service.record_direct_failure(
            client_class=client_class,
            direct_url=direct_url,
            reason=reason,
        )

    def reset_route_health(self) -> None:
        self._route_health_service.clear()

    def classify_client(
        self,
        *,
        is_web_client: bool,
        client_name: str | None,
        device_name: str | None,
        user_agent: str | None,
    ) -> str:
        if is_web_client:
            return "web-browser"

        parts = [client_name or "", device_name or "", user_agent or ""]
        normalized = " ".join(part.strip().lower() for part in parts if part and part.strip())
        return normalized or "unknown"

    def _should_force_proxy_by_client(self, client_class: str) -> bool:
        playback_cfg = getattr(self._config_getter(), "playback", None)
        force_proxy_clients = getattr(playback_cfg, "force_proxy_clients", []) or []
        normalized_class = (client_class or "").lower()
        return any(
            token.strip().lower() in normalized_class for token in force_proxy_clients if token and token.strip()
        )

    def _should_force_proxy_by_host(self, direct_url: str | None) -> bool:
        if not direct_url:
            return False
        host = (urlparse(direct_url).hostname or "").lower()
        if not host:
            return False
        playback_cfg = getattr(self._config_getter(), "playback", None)
        force_proxy_hosts = getattr(playback_cfg, "force_proxy_hosts", []) or []
        for pattern in force_proxy_hosts:
            normalized = (pattern or "").strip().lower()
            if not normalized:
                continue
            if fnmatch(host, normalized):
                return True
        return False

    def _looks_like_web_client(
        self,
        client_name: str | None,
        device_name: str | None,
        user_agent: str | None,
    ) -> bool:
        candidates = [client_name or "", device_name or "", user_agent or ""]
        normalized = " ".join(value.strip().lower() for value in candidates if value and value.strip())
        if not normalized:
            return False
        return any(hint in normalized for hint in _WEB_CLIENT_HINTS)

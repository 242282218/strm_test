"""
播放路由健康状态服务

负责记录“客户端类别 + 上游 host”的直链失败，并在一定时间内触发粘性代理降级。
"""

from __future__ import annotations

from dataclasses import dataclass
from threading import Lock
from time import monotonic
from urllib.parse import urlparse

from app.services.config_service import get_config_service


@dataclass(slots=True)
class RouteHealthState:
    failure_count: int = 0
    sticky_until: float = 0.0
    last_failure_at: float = 0.0
    last_reason: str = ""


class PlaybackRouteHealthService:
    def __init__(self, config_getter=None, time_getter=None):
        self._config_getter = config_getter or (lambda: get_config_service().get_config())
        self._time_getter = time_getter or monotonic
        self._states: dict[str, RouteHealthState] = {}
        self._lock = Lock()

    def should_sticky_proxy(self, *, client_class: str, direct_url: str | None) -> bool:
        policy = self._get_policy()
        if policy["threshold"] <= 0 or policy["ttl_sec"] <= 0:
            return False

        route_key = self._build_route_key(client_class=client_class, direct_url=direct_url)
        if route_key is None:
            return False

        now = self._time_getter()
        with self._lock:
            state = self._states.get(route_key)
            if state is None:
                return False
            if state.sticky_until > now:
                return True
            if state.sticky_until and state.sticky_until <= now:
                self._states.pop(route_key, None)
            return False

    def record_direct_failure(self, *, client_class: str, direct_url: str | None, reason: str) -> None:
        policy = self._get_policy()
        if policy["threshold"] <= 0 or policy["ttl_sec"] <= 0:
            return

        route_key = self._build_route_key(client_class=client_class, direct_url=direct_url)
        if route_key is None:
            return

        now = self._time_getter()
        ttl_sec = policy["ttl_sec"]
        threshold = policy["threshold"]

        with self._lock:
            state = self._states.get(route_key)
            if state is None or (state.last_failure_at and now - state.last_failure_at > ttl_sec):
                state = RouteHealthState()

            state.failure_count += 1
            state.last_failure_at = now
            state.last_reason = reason
            if state.failure_count >= threshold:
                state.sticky_until = now + ttl_sec
            self._states[route_key] = state

    def clear(self) -> None:
        with self._lock:
            self._states.clear()

    def _get_policy(self) -> dict[str, int]:
        playback_cfg = getattr(self._config_getter(), "playback", None)
        threshold = int(getattr(playback_cfg, "sticky_downgrade_threshold", 0) or 0)
        ttl_sec = int(getattr(playback_cfg, "sticky_downgrade_ttl_sec", 0) or 0)
        return {"threshold": max(0, threshold), "ttl_sec": max(0, ttl_sec)}

    def _build_route_key(self, *, client_class: str, direct_url: str | None) -> str | None:
        normalized_client = (client_class or "").strip().lower()
        host = (urlparse(direct_url or "").hostname or "").strip().lower()
        if not normalized_client or not host:
            return None
        return f"{normalized_client}::{host}"


_route_health_service_singleton = PlaybackRouteHealthService()


def get_playback_route_health_service() -> PlaybackRouteHealthService:
    return _route_health_service_singleton

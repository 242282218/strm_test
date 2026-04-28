from types import SimpleNamespace

from app.services.playback_decision_service import PlaybackDecisionService
from app.services.playback_route_health_service import PlaybackRouteHealthService


def _build_config(*, threshold: int = 1, ttl_sec: int = 3600):
    return SimpleNamespace(
        playback=SimpleNamespace(
            direct_first=True,
            force_proxy_clients=[],
            force_proxy_hosts=[],
            sticky_downgrade_threshold=threshold,
            sticky_downgrade_ttl_sec=ttl_sec,
        )
    )


def test_decide_delivery_mode_when_sticky_downgrade_active_then_returns_proxy():
    now = {"value": 1000.0}
    config = _build_config(threshold=1, ttl_sec=3600)
    route_health_service = PlaybackRouteHealthService(
        config_getter=lambda: config,
        time_getter=lambda: now["value"],
    )
    service = PlaybackDecisionService(
        config_getter=lambda: config,
        route_health_service=route_health_service,
    )

    service.record_direct_failure(
        client_name="Infuse",
        device_name=None,
        user_agent=None,
        direct_url="https://download.example/file1.mkv",
        reason="preflight_failed",
    )

    decision = service.decide_delivery_mode(
        client_name="Infuse",
        device_name=None,
        user_agent=None,
        direct_url="https://download.example/file2.mkv",
    )

    assert decision.mode == "proxy"
    assert decision.reason == "sticky_downgrade"


def test_decide_delivery_mode_when_sticky_downgrade_expired_then_returns_direct():
    now = {"value": 1000.0}
    config = _build_config(threshold=1, ttl_sec=30)
    route_health_service = PlaybackRouteHealthService(
        config_getter=lambda: config,
        time_getter=lambda: now["value"],
    )
    service = PlaybackDecisionService(
        config_getter=lambda: config,
        route_health_service=route_health_service,
    )

    service.record_direct_failure(
        client_name="Infuse",
        device_name=None,
        user_agent=None,
        direct_url="https://download.example/file1.mkv",
        reason="preflight_failed",
    )
    now["value"] += 31

    decision = service.decide_delivery_mode(
        client_name="Infuse",
        device_name=None,
        user_agent=None,
        direct_url="https://download.example/file2.mkv",
    )

    assert decision.mode == "direct"
    assert decision.reason == "direct_first"

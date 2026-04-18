from types import SimpleNamespace

from app.config.middleware import DEFAULT_CORS_ORIGINS, load_config_for_cors, resolve_cors_settings


def test_load_config_for_cors_allows_missing_service() -> None:
    assert load_config_for_cors(None) is None


def test_resolve_cors_settings_uses_config_values_when_available() -> None:
    app_config = SimpleNamespace(
        cors=SimpleNamespace(
            allow_credentials=False,
            allow_headers=["Authorization"],
            allow_methods=["GET"],
            allow_origins=["http://frontend.local"],
        )
    )

    settings = resolve_cors_settings(app_config, None)

    assert settings == {
        "allow_origins": ["http://frontend.local"],
        "allow_credentials": False,
        "allow_methods": ["GET"],
        "allow_headers": ["Authorization"],
    }
    assert settings["allow_origins"] != DEFAULT_CORS_ORIGINS


def test_resolve_cors_settings_when_config_uses_wildcards_then_falls_back_to_safe_defaults() -> None:
    app_config = SimpleNamespace(
        cors=SimpleNamespace(
            allow_credentials=True,
            allow_headers=["*"],
            allow_methods=["*"],
            allow_origins=["*"],
        )
    )

    settings = resolve_cors_settings(app_config, None)

    assert settings == {
        "allow_origins": DEFAULT_CORS_ORIGINS,
        "allow_credentials": True,
        "allow_methods": ["GET", "POST", "PUT", "DELETE", "OPTIONS", "PATCH"],
        "allow_headers": ["Authorization", "Content-Type", "X-Requested-With", "Accept", "Origin", "X-CSRF-Token"],
    }


def test_resolve_cors_settings_when_env_overrides_exist_then_prefers_env_values(monkeypatch) -> None:
    app_config = SimpleNamespace(
        cors=SimpleNamespace(
            allow_credentials=False,
            allow_headers=["Authorization"],
            allow_methods=["GET"],
            allow_origins=["http://frontend.local"],
        )
    )
    monkeypatch.setenv("CORS_ALLOW_ORIGINS", "https://a.example, https://b.example ")
    monkeypatch.setenv("CORS_ALLOW_CREDENTIALS", "true")

    settings = resolve_cors_settings(app_config, None)

    assert settings == {
        "allow_origins": ["https://a.example", "https://b.example"],
        "allow_credentials": True,
        "allow_methods": ["GET"],
        "allow_headers": ["Authorization"],
    }

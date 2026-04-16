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

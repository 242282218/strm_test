from __future__ import annotations

import importlib
import sys
import warnings
from unittest.mock import patch

import pytest


def _reload_error_handler_with_warning_capture() -> tuple[object, list[warnings.WarningMessage]]:
    sys.modules.pop("app.core.error_handler", None)

    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        module = importlib.import_module("app.core.error_handler")

    return module, caught


def test_error_handler_import_emits_deprecation_warning_and_exports_aliases() -> None:
    module, caught = _reload_error_handler_with_warning_capture()

    assert any(
        isinstance(item.message, DeprecationWarning)
        and "app.core.error_handler 已废弃" in str(item.message)
        for item in caught
    )
    assert module.ErrorCodeCompat is module.ErrorCode
    assert module.ErrorCode.__name__ == "ErrorCode"


def test_log_sanitizer_masks_sensitive_data_for_info_level() -> None:
    module, _ = _reload_error_handler_with_warning_capture()
    message = (
        "email user@example.com phone 13812345678 token eyJabc.def.ghi "
        "\"password\":\"secret\" api 0123456789abcdef0123456789abcdef ip 127.0.0.1"
    )

    sanitized = module.LogSanitizer.sanitize(message, level="info")

    assert "[EMAIL_MASKED]" in sanitized
    assert "[PHONE_MASKED]" in sanitized
    assert "[JWT_TOKEN_MASKED]" in sanitized
    assert "[PASSWORD_MASKED]" in sanitized
    assert "[API_KEY_MASKED]" in sanitized
    assert "[IP_ADDRESS_MASKED]" in sanitized


def test_log_sanitizer_debug_level_only_masks_critical_patterns() -> None:
    module, _ = _reload_error_handler_with_warning_capture()
    message = 'email user@example.com phone 13812345678 "password":"secret" token eyJabc.def.ghi'

    sanitized = module.LogSanitizer.sanitize(message, level="debug")

    assert "[PASSWORD_MASKED]" in sanitized
    assert "[JWT_TOKEN_MASKED]" in sanitized
    assert "[EMAIL_MASKED]" not in sanitized
    assert "[PHONE_MASKED]" not in sanitized


def test_log_sanitizer_dict_recursively_sanitizes_values() -> None:
    module, _ = _reload_error_handler_with_warning_capture()

    payload = {"user": "user@example.com", "meta": {"token": "eyJabc.def.ghi"}}
    sanitized = module.LogSanitizer.sanitize(payload, level="info")

    assert sanitized["user"] == "[EMAIL_MASKED]"
    assert sanitized["meta"]["token"] == "[JWT_TOKEN_MASKED]"


def test_log_sanitizer_logs_warning_when_pattern_substitution_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module, _ = _reload_error_handler_with_warning_capture()
    warnings_logged: list[str] = []
    monkeypatch.setattr(module.logger, "warning", lambda message: warnings_logged.append(message))

    def raise_re_error(*_args, **_kwargs):
        raise re_error

    re_error = RuntimeError("regex failed")
    with patch.object(module.re, "sub", side_effect=raise_re_error):
        module.LogSanitizer.sanitize("token eyJabc.def.ghi", level="info")

    assert any("Pattern sanitization failed" in message for message in warnings_logged)


def test_sanitize_headers_masks_known_sensitive_headers() -> None:
    module, _ = _reload_error_handler_with_warning_capture()

    result = module.LogSanitizer.sanitize_headers(
        {
            "Authorization": "Bearer abc",
            "Cookie": "session=xyz",
            "X-API-Key": "secret",
            "X-Auth-Token": "token",
            "X-Trace-Id": "trace-1",
        }
    )

    assert result["Authorization"] == "[HEADER_VALUE_MASKED]"
    assert result["Cookie"] == "[HEADER_VALUE_MASKED]"
    assert result["X-API-Key"] == "[HEADER_VALUE_MASKED]"
    assert result["X-Auth-Token"] == "[HEADER_VALUE_MASKED]"
    assert result["X-Trace-Id"] == "trace-1"


def test_create_success_response_uses_provided_request_id() -> None:
    module, _ = _reload_error_handler_with_warning_capture()
    fake_now = type("FakeNow", (), {"isoformat": lambda self: "2026-04-16T00:00:00"})()
    fake_datetime = type("FakeDatetime", (), {"utcnow": staticmethod(lambda: fake_now)})

    with patch.object(module, "datetime", fake_datetime):
        response = module.create_success_response(data={"ok": True}, message="done", request_id="req-1")

    assert response["success"] is True
    assert response["data"] == {"ok": True}
    assert response["message"] == "done"
    assert response["timestamp"] == "2026-04-16T00:00:00"
    assert response["request_id"] == "req-1"


def test_create_success_response_generates_request_id_when_missing() -> None:
    module, _ = _reload_error_handler_with_warning_capture()

    with patch.object(module.uuid, "uuid4", return_value="generated-id"):
        response = module.create_success_response()

    assert response["request_id"] == "generated-id"


def test_sanitize_log_delegates_to_log_sanitizer() -> None:
    module, _ = _reload_error_handler_with_warning_capture()

    with patch.object(module.LogSanitizer, "sanitize", return_value="sanitized") as mock_sanitize:
        result = module.sanitize_log("raw", level="debug")

    assert result == "sanitized"
    mock_sanitize.assert_called_once_with("raw", "debug")


def test_log_sanitizer_returns_non_string_input_unchanged() -> None:
    module, _ = _reload_error_handler_with_warning_capture()
    marker = object()
    assert module.LogSanitizer.sanitize(marker) is marker

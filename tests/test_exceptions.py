from __future__ import annotations

import pytest

from app.core.error_codes import ErrorCode
from app.core.exceptions import (
    AppException,
    AuthException,
    BusinessException,
    CookieInvalidException,
    ExternalServiceException,
    NetworkException,
    Open115Exception,
    QuarkAPIException,
    RateLimitException,
    RenameException,
    ScrapeException,
    ServiceUnavailableException,
    TaskTimeoutException,
    TimeoutException,
    convert_aiohttp_error,
    convert_http_exception,
)


def test_app_exception_to_dict_includes_optional_fields() -> None:
    exc = AppException(
        code=ErrorCode.EXTERNAL_TIMEOUT,
        message="timeout",
        detail="detail",
        data={"a": 1},
        retry_after=10,
    )

    payload = exc.to_dict()

    assert exc.status_code == 504
    assert payload["code"] == ErrorCode.EXTERNAL_TIMEOUT.value
    assert payload["error_code"] == ErrorCode.EXTERNAL_TIMEOUT.name
    assert payload["message"] == "timeout"
    assert payload["detail"] == "detail"
    assert payload["data"] == {"a": 1}
    assert payload["retry_after"] == 10


def test_app_exception_status_code_override() -> None:
    exc = AppException(code=ErrorCode.SYSTEM_INTERNAL_ERROR, status_code=409)
    assert exc.status_code == 409


def test_auth_exception_variants() -> None:
    unauthorized = AuthException()
    cookie_invalid = CookieInvalidException(service="夸克")

    assert unauthorized.code == ErrorCode.AUTH_UNAUTHORIZED
    assert unauthorized.status_code == 401
    assert "夸克登录已失效" in cookie_invalid.message


def test_external_exception_variants_messages() -> None:
    timeout_with_seconds = TimeoutException(service="TMDB", timeout=3.5)
    timeout_without_seconds = TimeoutException(service="TMDB")
    rate_limited = RateLimitException(service="TMDB", retry_after=15)
    unavailable = ServiceUnavailableException(service="TMDB", retry_after=20)
    quark_error = QuarkAPIException(message="bad request", error_code=123)
    open115_error = Open115Exception(error_code=456)
    network_error = NetworkException()

    assert "3.5秒" in timeout_with_seconds.message
    assert "3.5秒" not in timeout_without_seconds.message
    assert rate_limited.retry_after == 15
    assert unavailable.retry_after == 20
    assert quark_error.detail == "夸克错误码: 123"
    assert open115_error.detail == "115错误码: 456"
    assert network_error.message == "网络连接异常"


def test_business_exception_variants_messages() -> None:
    default_business = BusinessException()
    timeout = TaskTimeoutException(task_name="扫描任务")
    rename = RenameException(filename="a.mkv", reason="exists")
    rename_without_context = RenameException()
    scrape = ScrapeException(filename="b.mkv", reason="no match")
    scrape_without_context = ScrapeException()

    assert default_business.code == ErrorCode.BUSINESS_TASK_FAILED
    assert timeout.message == "扫描任务执行超时"
    assert "a.mkv" in rename.message
    assert "exists" in rename.message
    assert rename_without_context.message == "文件重命名失败"
    assert "b.mkv" in scrape.message
    assert "no match" in scrape.message
    assert scrape_without_context.message == "影片信息刮削失败"


@pytest.mark.parametrize(
    ("status_code", "expected_type", "expected_code"),
    [
        (429, RateLimitException, ErrorCode.EXTERNAL_RATE_LIMIT),
        (503, ServiceUnavailableException, ErrorCode.EXTERNAL_SERVICE_UNAVAILABLE),
        (504, TimeoutException, ErrorCode.EXTERNAL_TIMEOUT),
        (401, AuthException, ErrorCode.AUTH_UNAUTHORIZED),
        (403, AuthException, ErrorCode.AUTH_FORBIDDEN),
        (418, AppException, ErrorCode.EXTERNAL_API_ERROR),
    ],
)
def test_convert_http_exception_maps_to_expected_exception(
    status_code: int, expected_type: type[AppException], expected_code: ErrorCode
) -> None:
    exc = convert_http_exception(status_code=status_code, detail="detail text")
    assert isinstance(exc, expected_type)
    assert exc.code == expected_code


@pytest.mark.parametrize(
    ("error_text", "expected_type", "expected_code"),
    [
        ("request timeout", TimeoutException, ErrorCode.EXTERNAL_TIMEOUT),
        ("connection reset by peer", NetworkException, ErrorCode.EXTERNAL_NETWORK_ERROR),
        ("dns lookup failed", ExternalServiceException, ErrorCode.EXTERNAL_DNS_ERROR),
        ("ssl certificate error", ExternalServiceException, ErrorCode.EXTERNAL_SSL_ERROR),
        ("unknown boom", ExternalServiceException, ErrorCode.EXTERNAL_API_ERROR),
    ],
)
def test_convert_aiohttp_error_maps_to_expected_exception(
    error_text: str,
    expected_type: type[AppException],
    expected_code: ErrorCode,
) -> None:
    exc = convert_aiohttp_error(RuntimeError(error_text), service="TMDB")
    assert isinstance(exc, expected_type)
    assert exc.code == expected_code

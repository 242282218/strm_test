from __future__ import annotations

import json
from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from fastapi.exceptions import RequestValidationError

from app.core.constants import REQUEST_ID_HEADER
from app.core.error_codes import ErrorCode
from app.core.exception_handler import (
    app_exception_handler,
    exception_handler,
    http_exception_handler,
    input_validation_exception_handler,
    validation_exception_handler,
)
from app.core.exceptions import AppException, ExternalServiceException
from app.core.validators import InputValidationError


def _request(request_id: str | None = "rid-123") -> SimpleNamespace:
    state = SimpleNamespace()
    if request_id is not None:
        state.request_id = request_id
    return SimpleNamespace(state=state)


def _response_json(response) -> dict:
    return json.loads(response.body.decode("utf-8"))


@pytest.mark.asyncio
async def test_app_exception_handler_includes_retry_after_and_suggestions() -> None:
    exc = ExternalServiceException(
        code=ErrorCode.EXTERNAL_TIMEOUT,
        message="upstream timeout",
        detail="token=secret-value",
        retry_after=30,
    )

    response = await app_exception_handler(_request("rid-app"), exc)
    payload = _response_json(response)

    assert response.status_code == 504
    assert response.headers["Retry-After"] == "30"
    assert response.headers[REQUEST_ID_HEADER] == "rid-app"
    assert payload["request_id"] == "rid-app"
    assert payload["error_code"] == ErrorCode.EXTERNAL_TIMEOUT.name
    assert payload["suggestions"] == ["检查网络连接", "确认服务配置正确", "稍后重试"]


@pytest.mark.asyncio
async def test_http_exception_handler_client_error_redacts_detail() -> None:
    response = await http_exception_handler(
        _request("rid-http"),
        HTTPException(status_code=400, detail="api_key=very-secret"),
    )
    payload = _response_json(response)

    assert response.status_code == 400
    assert response.headers[REQUEST_ID_HEADER] == "rid-http"
    assert payload["message"] == "请求参数错误"
    assert payload["error_code"] == "ERR_BAD_REQUEST"
    assert payload["request_id"] == "rid-http"
    assert payload["detail"] == "api_key=***"


@pytest.mark.asyncio
async def test_http_exception_handler_server_error_hides_detail_and_header_is_optional() -> None:
    response = await http_exception_handler(
        _request(request_id=None),
        HTTPException(status_code=500, detail="internal details"),
    )
    payload = _response_json(response)

    assert response.status_code == 500
    assert REQUEST_ID_HEADER not in response.headers
    assert payload["message"] == "服务器内部错误"
    assert payload["detail"] is None
    assert payload["error_code"] == "ERR_INTERNAL"
    assert payload["request_id"] is None


@pytest.mark.asyncio
async def test_validation_exception_handler_returns_sanitized_errors() -> None:
    exc = RequestValidationError(
        [
            {
                "loc": ("body", "username"),
                "msg": "Field required",
                "type": "missing",
                "input": "",
            }
        ]
    )

    response = await validation_exception_handler(_request("rid-validate"), exc)
    payload = _response_json(response)

    assert response.status_code == 422
    assert response.headers[REQUEST_ID_HEADER] == "rid-validate"
    assert payload["message"] == "参数校验失败"
    assert payload["error_code"] == "ERR_VALIDATION"
    assert payload["request_id"] == "rid-validate"
    assert payload["errors"] == [{"loc": ["body", "username"], "msg": "Field required", "type": "missing"}]


@pytest.mark.asyncio
async def test_input_validation_exception_handler_redacts_sensitive_detail() -> None:
    response = await input_validation_exception_handler(
        _request("rid-input"),
        InputValidationError("password=plain-text"),
    )
    payload = _response_json(response)

    assert response.status_code == 400
    assert response.headers[REQUEST_ID_HEADER] == "rid-input"
    assert payload["message"] == "请求参数错误"
    assert payload["error_code"] == "ERR_BAD_REQUEST"
    assert payload["detail"] == "password=***"


@pytest.mark.asyncio
async def test_exception_handler_returns_internal_error_contract() -> None:
    response = await exception_handler(_request("rid-unhandled"), RuntimeError("boom"))
    payload = _response_json(response)

    assert response.status_code == 500
    assert response.headers[REQUEST_ID_HEADER] == "rid-unhandled"
    assert payload["code"] == 500
    assert payload["message"] == "服务器内部错误"
    assert payload["error_code"] == "ERR_INTERNAL"
    assert payload["request_id"] == "rid-unhandled"


@pytest.mark.asyncio
async def test_app_exception_handler_uses_custom_status_code_and_no_retry_header() -> None:
    exc = AppException(code=ErrorCode.BUSINESS_TASK_FAILED, message="failed", status_code=409)

    response = await app_exception_handler(_request("rid-custom"), exc)
    payload = _response_json(response)

    assert response.status_code == 409
    assert "Retry-After" not in response.headers
    assert payload["message"] == "failed"
    assert payload["request_id"] == "rid-custom"

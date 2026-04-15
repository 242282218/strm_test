from unittest.mock import patch

from app.core.response import ApiResponse, PaginationResponse, error_response, success_response


def test_api_response_sets_runtime_timestamp_and_payload() -> None:
    with patch("time.time", return_value=1713264000):
        response = ApiResponse(code=201, message="created", data={"id": 1})

    assert response.code == 201
    assert response.message == "created"
    assert response.data == {"id": 1}
    assert response.timestamp == 1713264000


def test_success_response_uses_default_message() -> None:
    with patch("time.time", return_value=1713265000):
        response = success_response(data=["a", "b"])

    assert response.code == 200
    assert response.message == "success"
    assert response.data == ["a", "b"]
    assert response.timestamp == 1713265000


def test_error_response_sets_detail_and_timestamp() -> None:
    with patch("time.time", return_value=1713266000):
        response = error_response(code=400, message="bad request", detail="missing field")

    assert response.code == 400
    assert response.message == "bad request"
    assert response.detail == "missing field"
    assert response.timestamp == 1713266000


def test_pagination_response_defaults_and_items() -> None:
    response = PaginationResponse(items=[1, 2, 3], total=12, page=2, page_size=3)

    assert response.items == [1, 2, 3]
    assert response.total == 12
    assert response.page == 2
    assert response.page_size == 3

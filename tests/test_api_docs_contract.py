from pathlib import Path


API_DOC_PATH = Path(__file__).resolve().parents[1] / "docs" / "api" / "README.md"


def test_api_docs_describe_dual_auth_contract() -> None:
    document = API_DOC_PATH.read_text(encoding="utf-8")

    assert "X-API-Key: <api-key>" in document
    assert "Authorization: Bearer <jwt-token>" in document
    assert "Authorization: Bearer <api-key>" in document
    assert "SMART_MEDIA_SECURITY_API_KEY" in document
    assert "security.api_key" in document


def test_api_docs_list_public_probes_and_monitoring_paths() -> None:
    document = API_DOC_PATH.read_text(encoding="utf-8")

    for path in (
        "/health",
        "/health/live",
        "/ready",
        "/health/ready",
        "/metrics",
        "/metrics/health",
        "/api/monitor/health",
        "/api/monitor/system/status",
        "/api/monitor/metrics",
        "/api/monitor/http-pool/health",
        "/api/monitor/db-pool/health",
    ):
        assert path in document


def test_api_docs_cover_current_auth_routes() -> None:
    document = API_DOC_PATH.read_text(encoding="utf-8")

    for path in (
        "/login",
        "/verify",
        "/status",
        "/init-admin",
        "/refresh",
        "/logout",
        "/change-password",
        "/me",
    ):
        assert path in document

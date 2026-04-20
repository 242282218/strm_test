from pathlib import Path


API_DOC_PATH = Path(__file__).resolve().parents[1] / "docs" / "api" / "README.md"


def test_api_docs_describe_dual_auth_contract() -> None:
    document = API_DOC_PATH.read_text(encoding="utf-8")

    assert "X-API-Key: <api-key>" in document
    assert "Authorization: Bearer <jwt-token>" in document
    assert "Authorization: Bearer <api-key>" in document
    assert "SMART_MEDIA_SECURITY_API_KEY" in document
    assert "SMART_MEDIA_API_KEY" in document
    assert "`API_KEY`" in document
    assert "security.api_key" in document
    assert "SMART_MEDIA_SECURITY_API_KEY` > `SMART_MEDIA_API_KEY` > `API_KEY` > `config.yaml" in document


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


def test_api_docs_define_canonical_and_compatibility_path_matrix() -> None:
    document = API_DOC_PATH.read_text(encoding="utf-8")

    for path in (
        "/api/v1/quark/*",
        "/api/quark/*",
        "/api/v1/api/quark/*",
        "/api/v1/strm/*",
        "/api/strm/*",
        "/api/v1/proxy/*",
        "/api/proxy/*",
        "/api/v1/emby/*",
        "/api/emby/*",
        "/api/v1/tasks/*",
        "/api/tasks/*",
        "/api/v1/scrape/*",
        "/api/scrape/*",
        "/api/v1/monitor/*",
        "/api/monitor/*",
    ):
        assert path in document

    assert "/api/v1/api/tasks/*" in document
    assert "当前不提供 `/api/v1/api/tasks/*`" in document
    assert "legacy-only: `/api/rename`" in document
    assert "legacy-only: `/api/notification`" in document

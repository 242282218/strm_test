from pathlib import Path

import yaml


PROJECT_ROOT = Path(__file__).resolve().parents[1]
APPLICATION_PATH = PROJECT_ROOT / "app" / "config" / "application.py"
DOCKERFILE_PATH = PROJECT_ROOT / "Dockerfile"
COMPOSE_PATH = PROJECT_ROOT / "docker-compose.yml"
OPS_DOC_PATH = PROJECT_ROOT / "docs" / "operations" / "README.md"
NGINX_SPA_CONFIG_PATH = PROJECT_ROOT / "docs" / "operations" / "nginx-spa.conf"


def test_backend_does_not_claim_fastapi_spa_hosting() -> None:
    application_source = APPLICATION_PATH.read_text(encoding="utf-8")
    operations_doc = OPS_DOC_PATH.read_text(encoding="utf-8")

    assert "StaticFiles" not in application_source
    assert "frontend-runtime" in operations_doc
    assert "不内置托管 Vue SPA" in operations_doc


def test_frontend_runtime_is_explicit_nginx_target() -> None:
    dockerfile = DOCKERFILE_PATH.read_text(encoding="utf-8")
    nginx_config = NGINX_SPA_CONFIG_PATH.read_text(encoding="utf-8")

    assert "FROM nginx:1.27-alpine AS frontend-runtime" in dockerfile
    assert "COPY --from=frontend-builder /build/dist /usr/share/nginx/html" in dockerfile
    assert "COPY docs/operations/nginx-spa.conf /etc/nginx/conf.d/default.conf" in dockerfile
    assert "COPY --from=frontend-builder /build/dist ./web/dist" not in dockerfile

    assert "try_files $uri $uri/ /index.html;" in nginx_config
    assert "proxy_pass http://quark-strm:8000" in nginx_config


def test_frontend_compose_profile_is_opt_in() -> None:
    compose = yaml.safe_load(COMPOSE_PATH.read_text(encoding="utf-8"))

    backend = compose["services"]["quark-strm"]
    frontend = compose["services"]["frontend"]

    assert "profiles" not in backend
    assert frontend["profiles"] == ["frontend"]
    assert frontend["depends_on"] == ["quark-strm"]
    assert frontend["build"]["target"] == "frontend-runtime"

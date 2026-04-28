import shlex
from pathlib import Path

import yaml


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DOCKERFILE_PATH = PROJECT_ROOT / "Dockerfile"
COMPOSE_PATH = PROJECT_ROOT / "docker-compose.yml"
ENV_EXAMPLE_PATH = PROJECT_ROOT / ".env.example"
GITIGNORE_PATH = PROJECT_ROOT / ".gitignore"
OPS_DOC_PATH = PROJECT_ROOT / "docs" / "operations" / "README.md"
NGINX_SPA_CONFIG_PATH = PROJECT_ROOT / "docs" / "operations" / "nginx-spa.conf"
DOCKER_DEPLOY_WORKFLOW_PATH = PROJECT_ROOT / ".github" / "workflows" / "docker-deploy-test.yml"
DOCKER_PUBLISH_WORKFLOW_PATH = PROJECT_ROOT / ".github" / "workflows" / "docker-publish.yml"


def _iter_local_copy_sources() -> list[str]:
    sources: list[str] = []
    for raw_line in DOCKERFILE_PATH.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line.startswith("COPY "):
            continue
        if "--from=" in line:
            continue
        tokens = shlex.split(line)
        if len(tokens) < 3:
            continue
        sources.extend(tokens[1:-1])
    return sources


def _parse_env_keys() -> set[str]:
    keys: set[str] = set()
    for raw_line in ENV_EXAMPLE_PATH.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _value = line.split("=", 1)
        keys.add(key)
    return keys


def test_dockerfile_copy_sources_exist() -> None:
    for source in _iter_local_copy_sources():
        matches = list(PROJECT_ROOT.glob(source))
        assert matches, f"Dockerfile COPY source does not exist: {source}"


def test_compose_mounts_and_env_example_match_runtime_contract() -> None:
    compose = yaml.safe_load(COMPOSE_PATH.read_text(encoding="utf-8"))
    service = compose["services"]["quark-strm"]
    env_keys = _parse_env_keys()

    for volume in service["volumes"]:
        host_path = volume.split(":", 1)[0].strip()
        if not host_path or host_path.startswith("${"):
            continue
        resolved = PROJECT_ROOT / host_path.removeprefix("./")
        assert resolved.exists(), f"Compose mount source does not exist: {host_path}"

    assert "QUARK_STRM_IMAGE" in env_keys
    assert "QUARK_STRM_FRONTEND_IMAGE" in env_keys
    assert "SMART_MEDIA_ENV" in env_keys
    assert "SMART_MEDIA_EMBY_PROXY_PORT" in env_keys
    assert "SMART_MEDIA_FRONTEND_PORT" in env_keys
    assert "SMART_MEDIA_LOG_FORMAT" in env_keys
    assert "TZ" in env_keys

    environment = "\n".join(service["environment"])
    assert "SMART_MEDIA_ENV=${SMART_MEDIA_ENV:-development}" in environment
    assert "SMART_MEDIA_LOG_FORMAT=${SMART_MEDIA_LOG_FORMAT:-json}" in environment
    assert "CONFIG_PATH=/app/config.yaml" in environment


def test_compose_frontend_profile_uses_nginx_runtime_image() -> None:
    compose = yaml.safe_load(COMPOSE_PATH.read_text(encoding="utf-8"))
    frontend = compose["services"]["frontend"]

    assert frontend["image"] == "${QUARK_STRM_FRONTEND_IMAGE:-quark-strm-frontend:local}"
    assert frontend["build"]["target"] == "frontend-runtime"
    assert "${SMART_MEDIA_FRONTEND_PORT:-18080}:80" in frontend["ports"]
    assert "frontend" in frontend["profiles"]
    assert "quark-strm" in frontend["depends_on"]

    backend = compose["services"]["quark-strm"]
    assert "frontend" not in backend.get("profiles", [])


def test_dockerfile_defaults_to_single_worker() -> None:
    dockerfile = DOCKERFILE_PATH.read_text(encoding="utf-8")

    assert "WEB_CONCURRENCY=1" in dockerfile
    assert '"--workers", "1"' in dockerfile
    assert "WEB_CONCURRENCY=2" not in dockerfile
    assert '"--workers", "2"' not in dockerfile
    assert "AS frontend-runtime" in dockerfile
    assert "docs/operations/nginx-spa.conf" in dockerfile


def test_nginx_spa_config_serves_frontend_and_proxies_backend_paths() -> None:
    config = NGINX_SPA_CONFIG_PATH.read_text(encoding="utf-8")

    assert "root /usr/share/nginx/html;" in config
    assert "try_files $uri $uri/ /index.html;" in config
    for location in ("location /api/", "location /ws/", "location = /ready", "location = /health"):
        assert location in config
    assert "proxy_pass http://quark-strm:8000" in config


def test_operations_doc_matches_bootstrap_contract() -> None:
    document = OPS_DOC_PATH.read_text(encoding="utf-8")

    assert "cp .env.example .env" in document
    assert "cp config.example.yaml config.yaml" in document
    assert "docker compose --profile monitoring up -d" in document
    assert "docker compose pull" in document
    assert "`/ready`" in document
    assert "CONFIG_PATH=/app/config.yaml" in document
    assert "SMART_MEDIA_ENV" in document
    assert "QUARK_STRM_FRONTEND_IMAGE" in document
    assert "SMART_MEDIA_SECURITY_API_KEY" in document
    assert "SMART_MEDIA_JWT_SECRET_KEY" in document
    assert "SMART_MEDIA_FRONTEND_PORT" in document
    assert "WEB_CONCURRENCY=1" in document
    assert "--workers 1" in document
    assert "--workers 4" not in document
    assert "Nginx/独立前端容器托管 SPA" in document
    assert "不内置托管 Vue SPA" in document
    assert "docker compose --profile frontend up -d" in document
    assert "frontend-runtime" in document
    assert "SQLite" in document
    assert "进程内任务" in document
    assert "内存缓存" in document
    assert "WebSocket" in document
    assert "npm ci" in document
    assert "npm run build" in document
    assert "pnpm install --frozen-lockfile" not in document


def test_gitignore_and_operations_doc_cover_local_runtime_artifacts() -> None:
    ignore_file = GITIGNORE_PATH.read_text(encoding="utf-8")
    document = OPS_DOC_PATH.read_text(encoding="utf-8")

    for pattern in (
        ".coverage*",
        "cache/",
        "output/",
        "target/",
        "tmp_wheel/",
        ".claude/",
        "playwright-report/",
        "test-results/",
    ):
        assert pattern in ignore_file

    for path_hint in (
        "`logs/`",
        "`strm/`",
        "`cache/`",
        "`output/`",
        "`target/`",
        "`tmp_wheel/`",
        "`web/playwright-report/`",
        "`web/test-results/`",
        "`.coverage*`",
        "`.claude/`",
    ):
        assert path_hint in document


def test_docker_workflows_deploy_the_intended_image() -> None:
    deploy_workflow = DOCKER_DEPLOY_WORKFLOW_PATH.read_text(encoding="utf-8")
    publish_workflow = DOCKER_PUBLISH_WORKFLOW_PATH.read_text(encoding="utf-8")

    assert "QUARK_STRM_IMAGE=quark-strm:test" in deploy_workflow
    assert "QUARK_STRM_FRONTEND_IMAGE=quark-strm-frontend:test" in deploy_workflow
    assert "docker compose --profile frontend up --pull never -d" in deploy_workflow
    assert "http://127.0.0.1:8000/ready" in deploy_workflow
    assert "http://127.0.0.1:18080/" in deploy_workflow
    assert "http://127.0.0.1:18080/login" in deploy_workflow
    assert "http://127.0.0.1:18080/ready" in deploy_workflow

    assert (
        "QUARK_STRM_IMAGE=${{ env.REGISTRY }}/${{ env.IMAGE_NAME }}:${{ needs.build-and-push.outputs.version }}"
        in publish_workflow
    )
    assert (
        "QUARK_STRM_FRONTEND_IMAGE=${{ env.REGISTRY }}/${{ env.FRONTEND_IMAGE_NAME }}:${{ needs.build-and-push.outputs.version }}"
        in publish_workflow
    )
    assert "docker compose --profile frontend up --pull never -d" in publish_workflow
    assert "http://127.0.0.1:8000/ready" in publish_workflow
    assert "http://127.0.0.1:18080/" in publish_workflow
    assert "http://127.0.0.1:18080/login" in publish_workflow
    assert "http://127.0.0.1:18080/ready" in publish_workflow

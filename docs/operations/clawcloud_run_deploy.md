# ClawCloud Run Deployment (This Repository)

This guide deploys the current project as a single backend service on ClawCloud Run.

## 1. Prepare source

1. Push this repository to GitHub.
2. Ensure these files are committed:
- `Dockerfile`
- `requirements.txt`
- `config.clawcloud.example.yaml`

## 2. Create app in ClawCloud Run

1. Open `https://run.claw.cloud/`.
2. `App Launchpad` -> `Create App`.
3. Source type: GitHub repository.
4. Select this repo and branch.
5. Build context: `.`
6. Dockerfile path: `Dockerfile`

## 3. Runtime settings

Use these values:

- Container port: `8000`
- Start command: leave empty (use Dockerfile CMD)
- CPU/Memory: start small (`0.5 vCPU`, `512 MiB`)
- Replicas: `1`

Environment variables:

- `PORT=8000`
- `WEB_CONCURRENCY=1`
- `CONFIG_PATH=/data/config.yaml`

## 4. Persistent storage (important)

Add one persistent volume:

- Mount path: `/data`
- Initial size: `1 GiB` (or larger if needed)

This path stores:

- `/data/config.yaml`
- `/data/quark_strm.db` (after you update config)
- `/data/logs/`
- `/data/strm/`

## 5. First start and config update

On first boot, container auto-creates `/data/config.yaml` from `config.clawcloud.example.yaml`.

Edit `/data/config.yaml` in ClawCloud terminal/file editor and update at least:

- `quark.cookie: <your_cookie>`
- `webdav.enabled: false` if you do not need WebDAV

Redeploy or restart after config changes.

## 6. Verify

After app is running:

- `GET /health` should return `status: ok`
- Example: `https://<your-app-domain>/health`

## 7. Minimal rollback checks

If startup fails:

1. Check app logs for config validation errors.
2. Confirm `/data/config.yaml` exists and is valid YAML.
3. Confirm container port is `8000`.
4. Confirm environment `CONFIG_PATH=/data/config.yaml`.

# quark-strm

`quark-strm` is the deployable backend/frontend workspace for Smart Media.
It contains the FastAPI service, the Vue web client, automated tests, and
runtime/deployment assets used by the project.

## Layout

- `app/`: FastAPI application code and backend services
- `web/`: Vue 3 + TypeScript frontend
- `tests/`: backend regression and contract tests
- `docs/`: runbooks, plans, and operation notes
- `config.example.yaml`: local configuration template
- `docker-compose.yml`: container entrypoint for local deployment

## Local Development

```bash
pip install -r requirements.txt
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

```bash
cd web
pnpm install
pnpm run lint
pnpm run type-check
pnpm run test:run
```

## Verification

- Backend: `pytest tests -v --tb=short`
- Frontend lint: `cd web && pnpm run lint`
- Frontend type-check: `cd web && pnpm run type-check`
- Frontend unit tests: `cd web && pnpm run test:run`
- Frontend E2E: `cd web && pnpm run test:e2e`

The workspace-level overview and user-facing documentation remain in
`../README.md`.

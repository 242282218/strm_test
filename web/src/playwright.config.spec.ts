// @vitest-environment node
import { describe, expect, it } from 'vitest'

import { createPlaywrightWebServers, resolvePlaywrightRuntimeConfig } from '../playwright.config'

describe('playwright e2e startup contract', () => {
  it('uses isolated default e2e ports when no overrides are provided', () => {
    const runtime = resolvePlaywrightRuntimeConfig({})
    const [backend, frontend] = createPlaywrightWebServers(runtime, {})

    expect(runtime).toMatchObject({
      apiTarget: 'http://127.0.0.1:18000',
      baseURL: 'http://127.0.0.1:18099',
    })
    expect(backend.command).toContain('uvicorn app.main:app --host 127.0.0.1 --port 18000')
    expect(frontend.command).toContain('npm run dev -- --host 127.0.0.1 --port 18099')
  })

  it('auto-starts backend and frontend with aligned targets', () => {
    const env = {
      PLAYWRIGHT_BASE_URL: 'http://127.0.0.1:3001',
      VITE_API_PROXY_TARGET: 'http://127.0.0.1:18000',
      PLAYWRIGHT_PYTHON: 'python',
    } as NodeJS.ProcessEnv

    const runtime = resolvePlaywrightRuntimeConfig(env)
    const [backend, frontend] = createPlaywrightWebServers(runtime, env)

    expect(runtime).toMatchObject({
      apiTarget: 'http://127.0.0.1:18000',
      baseURL: 'http://127.0.0.1:3001',
    })
    expect(backend).toMatchObject({
      name: 'Backend',
      reuseExistingServer: true,
      url: 'http://127.0.0.1:18000/ready',
    })
    expect(backend.command).toContain('python -m uvicorn app.main:app --host 127.0.0.1 --port 18000')
    expect(backend.env?.ADMIN_PASSWORD).toBe('admin')
    expect(frontend).toMatchObject({
      name: 'Frontend',
      reuseExistingServer: true,
      url: 'http://127.0.0.1:3001',
    })
    expect(frontend.command).toContain('npm run dev -- --host 127.0.0.1 --port 3001')
    expect(frontend.env?.VITE_API_PROXY_TARGET).toBe('http://127.0.0.1:18000')
  })

  it('prefers explicit backend and auth overrides', () => {
    const env = {
      ADMIN_PASSWORD: 'secret-pass',
      CI: 'true',
      PLAYWRIGHT_API_TARGET: 'http://localhost:19000',
      PLAYWRIGHT_BASE_URL: 'http://localhost:3100',
      PLAYWRIGHT_PYTHON: 'py -3.11',
    } as NodeJS.ProcessEnv

    const runtime = resolvePlaywrightRuntimeConfig(env)
    const [backend, frontend] = createPlaywrightWebServers(runtime, env)

    expect(runtime.apiTarget).toBe('http://localhost:19000')
    expect(backend.command).toContain('py -3.11 -m uvicorn app.main:app --host localhost --port 19000')
    expect(backend.env?.ADMIN_PASSWORD).toBe('secret-pass')
    expect(backend.reuseExistingServer).toBe(false)
    expect(frontend.command).toContain('npm run dev -- --host localhost --port 3100')
    expect(frontend.env?.VITE_API_PROXY_TARGET).toBe('http://localhost:19000')
    expect(frontend.reuseExistingServer).toBe(false)
  })
})

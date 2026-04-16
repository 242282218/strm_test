import { existsSync } from 'node:fs'
import { resolve } from 'node:path'
import { fileURLToPath } from 'node:url'

import { defineConfig, devices } from '@playwright/test'

const DEFAULT_BASE_URL = 'http://127.0.0.1:3000'
const DEFAULT_API_TARGET = 'http://127.0.0.1:8000'
const configDir = fileURLToPath(new URL('.', import.meta.url))
const repoRoot = resolve(configDir, '..')

interface ServerTarget {
  origin: string
  host: string
  port: number
}

interface RuntimeConfig {
  apiTarget: string
  backend: ServerTarget
  baseURL: string
  frontend: ServerTarget
  pythonCommand: string
}

type CommandEnv = Record<string, string>

interface SharedWebServerConfig {
  command: string
  cwd: string
  name: string
  reuseExistingServer: boolean
  stderr: 'pipe'
  stdout: 'pipe'
  timeout: number
  url: string
}

interface BackendWebServerConfig extends SharedWebServerConfig {
  env: CommandEnv & {
    ADMIN_PASSWORD: string
  }
  name: 'Backend'
}

interface FrontendWebServerConfig extends SharedWebServerConfig {
  env: CommandEnv & {
    VITE_API_PROXY_TARGET: string
  }
  name: 'Frontend'
}

type PlaywrightWebServers = [BackendWebServerConfig, FrontendWebServerConfig]

function parseServerTarget(rawTarget: string): ServerTarget {
  const target = new URL(rawTarget)
  const fallbackPort = target.protocol === 'https:' ? 443 : 80

  return {
    origin: target.origin,
    host: target.hostname,
    port: Number(target.port || fallbackPort),
  }
}

function resolvePythonCommand(env: NodeJS.ProcessEnv): string {
  const override = env.PLAYWRIGHT_PYTHON?.trim() || env.PYTHON?.trim()
  if (override) {
    return override
  }

  const venvPython = process.platform === 'win32'
    ? resolve(repoRoot, '.venv', 'Scripts', 'python.exe')
    : resolve(repoRoot, '.venv', 'bin', 'python')

  if (existsSync(venvPython)) {
    return `"${venvPython}"`
  }

  return 'python'
}

export function resolvePlaywrightRuntimeConfig(env: NodeJS.ProcessEnv = process.env): RuntimeConfig {
  const baseURL = env.PLAYWRIGHT_BASE_URL?.trim() || DEFAULT_BASE_URL
  const apiTarget = env.PLAYWRIGHT_API_TARGET?.trim() || env.VITE_API_PROXY_TARGET?.trim() || DEFAULT_API_TARGET

  return {
    apiTarget,
    backend: parseServerTarget(apiTarget),
    baseURL,
    frontend: parseServerTarget(baseURL),
    pythonCommand: resolvePythonCommand(env),
  }
}

function toCommandEnv(env: NodeJS.ProcessEnv): CommandEnv {
  return Object.fromEntries(
    Object.entries(env).filter((entry): entry is [string, string] => entry[1] !== undefined),
  )
}

export function createPlaywrightWebServers(
  runtime: RuntimeConfig,
  env: NodeJS.ProcessEnv = process.env,
): PlaywrightWebServers {
  const commandEnv = toCommandEnv(env)

  return [
    {
      command: `${runtime.pythonCommand} -m uvicorn app.main:app --host ${runtime.backend.host} --port ${runtime.backend.port}`,
      cwd: repoRoot,
      env: {
        ...commandEnv,
        ADMIN_PASSWORD: env.ADMIN_PASSWORD?.trim() || 'admin',
      },
      name: 'Backend',
      reuseExistingServer: !env.CI,
      stderr: 'pipe' as const,
      stdout: 'pipe' as const,
      timeout: 120_000,
      url: `${runtime.backend.origin}/ready`,
    },
    {
      command: `npm run dev -- --host ${runtime.frontend.host} --port ${runtime.frontend.port}`,
      cwd: configDir,
      env: {
        ...commandEnv,
        VITE_API_PROXY_TARGET: runtime.apiTarget,
      },
      name: 'Frontend',
      reuseExistingServer: !env.CI,
      stderr: 'pipe' as const,
      stdout: 'pipe' as const,
      timeout: 120_000,
      url: runtime.baseURL,
    },
  ]
}

const runtime = resolvePlaywrightRuntimeConfig()
const baseURL = runtime.baseURL
const configuredWorkers = Number(process.env.PLAYWRIGHT_WORKERS || '')
const workers = Number.isFinite(configuredWorkers) && configuredWorkers > 0
  ? configuredWorkers
  : (process.env.CI ? 1 : 2)
const fullyParallel = process.env.PLAYWRIGHT_FULLY_PARALLEL === 'true'

export default defineConfig({
  testDir: './e2e',
  fullyParallel,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 2 : 0,
  workers,
  reporter: [['html', { open: 'never' }], ['list']],
  timeout: 30_000,

  use: {
    baseURL,
    trace: 'on-first-retry',
    screenshot: 'only-on-failure',
    video: 'retain-on-failure',
  },
  webServer: createPlaywrightWebServers(runtime),

  projects: [
    // 登录 setup — 不带 storageState
    {
      name: 'setup',
      testMatch: /global-setup\.ts/,
    },
    // 主测试 — 复用登录态
    {
      name: 'chromium',
      use: {
        ...devices['Desktop Chrome'],
        storageState: 'e2e/.auth/state.json',
      },
      dependencies: ['setup'],
    },
  ],
})

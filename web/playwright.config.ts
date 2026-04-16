import { defineConfig, devices } from '@playwright/test'

const baseURL = process.env.PLAYWRIGHT_BASE_URL?.trim() || 'http://127.0.0.1:3000'
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

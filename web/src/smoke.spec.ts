// @vitest-environment happy-dom
import { nextTick } from 'vue'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { bootstrapApp, type BootstrappedApp } from './bootstrap'
import { createAppRouter } from './router'

type MockStore = {
  isAuthenticated: boolean
  checkAuth: ReturnType<typeof vi.fn>
}

const mockStore: MockStore = {
  isAuthenticated: false,
  checkAuth: vi.fn(),
}

let mountedApp: BootstrappedApp | null = null

vi.mock('@/stores/auth', () => ({
  useAuthStore: () => mockStore,
}))

vi.mock('@/features/auth/views/LoginView.vue', () => ({
  default: {
    name: 'LoginViewStub',
    template: '<main data-testid="login-view">login</main>',
  },
}))

vi.mock('@/features/app-shell/views/LayoutView.vue', () => ({
  default: {
    name: 'LayoutViewStub',
    template: '<div data-testid="layout-view"><router-view /></div>',
  },
}))

vi.mock('@/features/dashboard/views/DashboardView.vue', () => ({
  default: {
    name: 'DashboardViewStub',
    template: '<section data-testid="dashboard-view">dashboard</section>',
  },
}))

async function bootstrapAt(path: string): Promise<BootstrappedApp> {
  mountedApp?.app.unmount()
  mountedApp = null
  const host = document.createElement('div')
  document.body.replaceChildren(host)
  window.history.replaceState({}, '', path)

  const router = createAppRouter()
  await router.push(path)
  await router.isReady()

  mountedApp = bootstrapApp(host, router)
  await nextTick()
  return mountedApp
}

async function waitForRoute(path: string): Promise<void> {
  const deadline = Date.now() + 2_000

  while (Date.now() < deadline) {
    if (mountedApp?.router.currentRoute.value.fullPath === path) {
      await nextTick()
      return
    }
    await new Promise((resolve) => setTimeout(resolve, 10))
  }

  throw new Error(`Route did not settle to ${path}`)
}

describe('app smoke startup contract', () => {
  beforeEach(() => {
    mockStore.isAuthenticated = false
    mockStore.checkAuth = vi.fn().mockResolvedValue(false)
    document.documentElement.className = ''
    window.localStorage.clear()
  })

  afterEach(() => {
    mountedApp?.app.unmount()
    mountedApp = null
    document.body.innerHTML = ''
  })

  it('redirects protected startup traffic to login when auth recovery fails', async () => {
    const { router } = await bootstrapAt('/dashboard')
    await waitForRoute('/login')

    expect(mockStore.checkAuth).toHaveBeenCalledTimes(1)
    expect(router.currentRoute.value.fullPath).toBe('/login')
    expect(document.querySelector('[data-testid="login-view"]')).not.toBeNull()
  })

  it('renders the protected shell after restoring auth on startup', async () => {
    mockStore.checkAuth = vi.fn().mockImplementation(async () => {
      mockStore.isAuthenticated = true
      return true
    })

    const { router } = await bootstrapAt('/dashboard')
    await waitForRoute('/dashboard')

    expect(mockStore.checkAuth).toHaveBeenCalledTimes(1)
    expect(router.currentRoute.value.fullPath).toBe('/dashboard')
    expect(document.querySelector('[data-testid="layout-view"]')).not.toBeNull()
    expect(document.querySelector('[data-testid="dashboard-view"]')).not.toBeNull()
  })
})

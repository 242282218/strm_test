import { beforeEach, describe, expect, it, vi } from 'vitest'

import { createAppRouter } from './index'

type MockStore = {
  isAuthenticated: boolean
  checkAuth: ReturnType<typeof vi.fn>
}

const mockStore: MockStore = {
  isAuthenticated: false,
  checkAuth: vi.fn(),
}

vi.mock('@/stores/auth', () => ({
  useAuthStore: () => mockStore,
}))

vi.mock('@/features/auth/views/LoginView.vue', () => ({
  default: { name: 'LoginViewStub', template: '<div />' },
}))

vi.mock('@/features/app-shell/views/LayoutView.vue', () => ({
  default: { name: 'LayoutViewStub', template: '<div />' },
}))

vi.mock('@/features/dashboard/views/DashboardView.vue', () => ({
  default: { name: 'DashboardViewStub', template: '<div />' },
}))

describe('router auth guard', () => {
  beforeEach(() => {
    mockStore.isAuthenticated = false
    mockStore.checkAuth = vi.fn()
  })

  it('tries to restore auth before redirecting protected routes', async () => {
    mockStore.checkAuth.mockImplementation(async () => {
      mockStore.isAuthenticated = true
      return true
    })

    const router = createAppRouter()

    await router.push('/dashboard')
    await router.isReady()

    expect(mockStore.checkAuth).toHaveBeenCalledTimes(1)
    expect(router.currentRoute.value.fullPath).toBe('/dashboard')
  })
})

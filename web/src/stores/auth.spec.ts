import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'

const apiMocks = vi.hoisted(() => ({
  post: vi.fn(),
  get: vi.fn(),
}))

vi.mock('@/api/index', () => ({
  default: apiMocks,
}))

describe('auth store api client usage', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    setActivePinia(createPinia())
  })

  it('uses shared api client for login', async () => {
    apiMocks.post.mockResolvedValue({
      access_token: 'token',
      refresh_token: 'token',
      token_type: 'bearer',
      expires_in: 3600,
      user: {
        id: 1,
        username: 'admin',
        role: 'admin',
        is_active: true,
      },
    })

    const { useAuthStore } = await import('./auth')
    const store = useAuthStore()

    await expect(store.login('admin', 'secret')).resolves.toBe(true)
    expect(apiMocks.post).toHaveBeenCalledWith('/auth/login', {
      username: 'admin',
      password: 'secret',
    })
    expect(store.user?.username).toBe('admin')
  })

  it('uses shared api client for checkAuth', async () => {
    apiMocks.get.mockResolvedValue({
      id: 1,
      username: 'admin',
      role: 'admin',
      is_active: true,
    })

    const { useAuthStore } = await import('./auth')
    const store = useAuthStore()

    await expect(store.checkAuth()).resolves.toBe(true)
    expect(apiMocks.get).toHaveBeenCalledWith('/auth/me')
    expect(store.user?.username).toBe('admin')
  })

  it('uses shared api client for logout', async () => {
    apiMocks.post.mockResolvedValue({ success: true, message: 'Logout successful' })

    const { useAuthStore } = await import('./auth')
    const store = useAuthStore()
    store.user = {
      id: 1,
      username: 'admin',
      role: 'admin',
      is_active: true,
    }

    await store.logout()

    expect(apiMocks.post).toHaveBeenCalledWith('/auth/logout')
    expect(store.user).toBeNull()
  })

  it('uses shared api client for changePassword', async () => {
    apiMocks.post.mockResolvedValue({ success: true, message: 'Password changed successfully' })

    const { useAuthStore } = await import('./auth')
    const store = useAuthStore()

    await expect(store.changePassword('old-pass', 'new-pass')).resolves.toBe(true)
    expect(apiMocks.post).toHaveBeenCalledWith('/auth/change-password', {
      old_password: 'old-pass',
      new_password: 'new-pass',
    })
  })
})

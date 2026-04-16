import { describe, expect, it, vi, beforeEach } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import ElementPlus from 'element-plus'

import LoginView from './LoginView.vue'

const routerPushMock = vi.fn()

const apiMocks = vi.hoisted(() => ({
  postMock: vi.fn(),
  getMock: vi.fn(),
}))

const notificationMocks = vi.hoisted(() => ({
  successMock: vi.fn(),
  errorMock: vi.fn(),
  withLoadingMock: vi.fn(async (fn: () => Promise<unknown>) => await fn()),
}))

const authStoreMocks = vi.hoisted(() => ({
  loading: { value: false },
  isAuthenticated: false,
  loginMock: vi.fn(),
}))

vi.mock('vue-router', () => ({
  useRouter: () => ({
    push: routerPushMock,
  }),
}))

vi.mock('@/api/index', () => ({
  default: {
    post: apiMocks.postMock,
    get: apiMocks.getMock,
  },
}))

vi.mock('@/composables', async (importOriginal) => {
  const actual = await importOriginal<typeof import('@/composables')>()

  return {
    ...actual,
    useLoading: () => ({
      loading: false,
      withLoading: notificationMocks.withLoadingMock,
    }),
    useNotification: () => ({
      success: notificationMocks.successMock,
      error: notificationMocks.errorMock,
    }),
  }
})

vi.mock('@/stores/auth', () => ({
  useAuthStore: () => ({
    loading: authStoreMocks.loading.value,
    isAuthenticated: authStoreMocks.isAuthenticated,
    login: authStoreMocks.loginMock,
  }),
}))

vi.mock('@/components/icons', () => {
  const stub = { template: '<span />' }
  return {
    User: stub,
    Lock: stub,
    Moon: stub,
    Sunny: stub,
    Cloudy: stub,
  }
})

const createAuthStatus = (overrides: Partial<Record<string, unknown>> = {}) => ({
  auth_required: true,
  has_api_key_configured: false,
  message: 'Authentication required',
  has_admin_user: false,
  can_init_admin: true,
  ...overrides,
})

interface LoginViewVm {
  handleInitAdmin: () => Promise<void>
  form: {
    username: string
    password: string
  }
  isDark: boolean
  toggleTheme: (nextDark: boolean) => void
}

const asLoginViewVm = (vm: unknown): LoginViewVm => vm as LoginViewVm

describe('LoginView', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    localStorage.clear()
    document.documentElement.classList.remove('dark')

    apiMocks.getMock.mockResolvedValue(createAuthStatus())
    apiMocks.postMock.mockResolvedValue({
      username: 'admin',
      password_generated: false,
      generated_password: 'admin',
    })
  })

  it('hides init admin entry when admin already exists', async () => {
    apiMocks.getMock.mockResolvedValue(createAuthStatus({
      has_admin_user: true,
      can_init_admin: false,
    }))

    const wrapper = mount(LoginView, {
      global: {
        plugins: [ElementPlus],
      },
    })

    await flushPromises()

    expect(wrapper.text()).not.toContain('初始化管理员')
    expect(wrapper.text()).not.toContain('首次使用请点击下方按钮初始化管理员账户')
  })

  it('shows init admin entry when bootstrap is allowed without admin', async () => {
    apiMocks.getMock.mockResolvedValue(createAuthStatus({
      has_admin_user: false,
      can_init_admin: true,
    }))

    const wrapper = mount(LoginView, {
      global: {
        plugins: [ElementPlus],
      },
    })

    await flushPromises()

    expect(wrapper.text()).toContain('初始化管理员')
    expect(wrapper.text()).toContain('首次使用请点击下方按钮初始化管理员账户')
  })

  it('refreshes auth status and hides init admin entry after conflict', async () => {
    apiMocks.getMock
      .mockResolvedValueOnce(createAuthStatus({
        has_admin_user: false,
        can_init_admin: true,
      }))
      .mockResolvedValueOnce(createAuthStatus({
        has_admin_user: true,
        can_init_admin: false,
      }))
    apiMocks.postMock.mockRejectedValue({
      response: {
        status: 409,
        data: {
          detail: 'Admin user already initialized',
        },
      },
    })

    const wrapper = mount(LoginView, {
      global: {
        plugins: [ElementPlus],
      },
    })

    await flushPromises()
    expect(wrapper.text()).toContain('初始化管理员')

    await asLoginViewVm(wrapper.vm).handleInitAdmin()
    await flushPromises()

    expect(notificationMocks.errorMock).toHaveBeenCalledWith('Admin user already initialized')
    expect(apiMocks.getMock).toHaveBeenCalledTimes(2)
    expect(wrapper.text()).not.toContain('初始化管理员')
  })

  it('refreshes auth status and hides init admin entry after forbidden response', async () => {
    apiMocks.getMock
      .mockResolvedValueOnce(createAuthStatus({
        has_admin_user: false,
        can_init_admin: true,
      }))
      .mockResolvedValueOnce(createAuthStatus({
        has_admin_user: false,
        can_init_admin: false,
      }))
    apiMocks.postMock.mockRejectedValue({
      response: {
        status: 403,
        data: {
          detail: 'Init-admin is only available for local first-time bootstrap',
        },
      },
    })

    const wrapper = mount(LoginView, {
      global: {
        plugins: [ElementPlus],
      },
    })

    await flushPromises()
    expect(wrapper.text()).toContain('初始化管理员')

    await asLoginViewVm(wrapper.vm).handleInitAdmin()
    await flushPromises()

    expect(notificationMocks.errorMock).toHaveBeenCalledWith('Init-admin is only available for local first-time bootstrap')
    expect(apiMocks.getMock).toHaveBeenCalledTimes(2)
    expect(wrapper.text()).not.toContain('初始化管理员')
  })

  it('shows admin/admin instead of temporary password after admin init succeeds', async () => {
    apiMocks.getMock
      .mockResolvedValueOnce(createAuthStatus({
        has_admin_user: false,
        can_init_admin: true,
      }))
      .mockResolvedValueOnce(createAuthStatus({
        has_admin_user: true,
        can_init_admin: false,
      }))

    const wrapper = mount(LoginView, {
      global: {
        plugins: [ElementPlus],
      },
    })

    await flushPromises()
    const vm = asLoginViewVm(wrapper.vm)
    await vm.handleInitAdmin()
    await flushPromises()

    expect(notificationMocks.successMock).toHaveBeenCalledWith(
      'Admin account created. Username: admin Password: admin',
      'Initialization complete',
    )
    expect(vm.form.username).toBe('admin')
    expect(vm.form.password).toBe('admin')
  })

  it('restores dark theme from localStorage on mount', async () => {
    localStorage.setItem('theme', 'dark')

    const wrapper = mount(LoginView, {
      global: {
        plugins: [ElementPlus],
      },
    })

    await flushPromises()

    expect(document.documentElement.classList.contains('dark')).toBe(true)
    expect(asLoginViewVm(wrapper.vm).isDark).toBe(true)
  })

  it('persists light theme when toggled off', async () => {
    const wrapper = mount(LoginView, {
      global: {
        plugins: [ElementPlus],
      },
    })

    await flushPromises()
    asLoginViewVm(wrapper.vm).toggleTheme(false)

    expect(document.documentElement.classList.contains('dark')).toBe(false)
    expect(localStorage.getItem('theme')).toBe('light')
  })
})

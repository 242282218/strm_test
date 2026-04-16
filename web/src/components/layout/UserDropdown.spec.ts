import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import { createRouter, createWebHistory } from 'vue-router'
import { createPinia, setActivePinia } from 'pinia'
import ElementPlus, { ElMessage, type MessageHandler } from 'element-plus'
import UserDropdown from './UserDropdown.vue'

// Mock icons with all required exports
vi.mock('@element-plus/icons-vue', () => {
  const createIcon = (name: string) => ({
    name,
    template: `<svg data-icon="${name}" />`
  })

  return {
    ArrowDown: createIcon('ArrowDown'),
    UserFilled: createIcon('UserFilled'),
    Cloudy: createIcon('Cloudy'),
    Expand: createIcon('Expand'),
    Fold: createIcon('Fold'),
    Odometer: createIcon('Odometer'),
    Search: createIcon('Search'),
    MagicStick: createIcon('MagicStick'),
    FolderOpened: createIcon('FolderOpened'),
    Document: createIcon('Document'),
    CollectionTag: createIcon('CollectionTag'),
    Monitor: createIcon('Monitor'),
    Link: createIcon('Link'),
    Folder: createIcon('Folder'),
    List: createIcon('List'),
    Setting: createIcon('Setting'),
    Film: createIcon('Film'),
    VideoPlay: createIcon('VideoPlay'),
    Tools: createIcon('Tools'),
    Bell: createIcon('Bell'),
    Message: createIcon('Message'),
    ChatDotSquare: createIcon('ChatDotSquare'),
    House: createIcon('House'),
    Refresh: createIcon('Refresh'),
    Check: createIcon('Check'),
    ArrowRight: createIcon('ArrowRight'),
    Moon: createIcon('Moon'),
    Sunny: createIcon('Sunny')
  }
})

const authStoreState = vi.hoisted(() => ({
  user: null as null | { username: string },
  logoutMock: vi.fn(),
  changePasswordMock: vi.fn()
}))

vi.mock('@/stores/auth', () => ({
  useAuthStore: vi.fn(() => ({
    get user() {
      return authStoreState.user
    },
    logout: authStoreState.logoutMock,
    changePassword: authStoreState.changePasswordMock
  }))
}))

describe('UserDropdown', () => {
  let router: ReturnType<typeof createRouter>
  let pinia: ReturnType<typeof createPinia>
  let messageSuccessSpy: ReturnType<typeof vi.spyOn>

  type UserDropdownVm = {
    handleCommand: (command: string) => void | Promise<void>
    passwordForm: {
      oldPassword: string
      newPassword: string
      confirmPassword: string
    }
    submitChangePassword: () => Promise<void>
  }

  const asUserDropdownVm = (vm: unknown): UserDropdownVm => vm as UserDropdownVm

  afterEach(() => {
    document.body.innerHTML = ''
  })

  beforeEach(() => {
    localStorage.clear()
    document.documentElement.classList.remove('dark')

    pinia = createPinia()
    setActivePinia(pinia)

    router = createRouter({
      history: createWebHistory(),
      routes: [
        { path: '/', component: { template: '<div />' } },
        { path: '/profile', component: { template: '<div />' } },
        { path: '/config', component: { template: '<div />' } },
        { path: '/login', component: { template: '<div />' } }
      ]
    })

    vi.clearAllMocks()
    authStoreState.user = { username: '侧栏管理员' }
    authStoreState.changePasswordMock.mockResolvedValue(true)
    messageSuccessSpy = vi.spyOn(ElMessage, 'success').mockImplementation(
      (): MessageHandler => ({ close: vi.fn() })
    )
  })

  it('uses auth store username when no explicit username prop is provided', () => {
    const wrapper = mount(UserDropdown, {
      global: {
        plugins: [router, pinia, ElementPlus]
      }
    })

    expect(wrapper.find('.user-dropdown').exists()).toBe(true)
    expect(wrapper.find('.username').text()).toBe('侧栏管理员')
    expect(wrapper.text()).not.toContain('当前账号')
  })

  it('falls back to default username when auth store has no user data', () => {
    authStoreState.user = null

    const wrapper = mount(UserDropdown, {
      global: {
        plugins: [router, pinia, ElementPlus]
      }
    })

    expect(wrapper.find('.username').text()).toBe('管理员')
  })

  it('falls back to custom username when auth store has no user data', () => {
    authStoreState.user = null

    const wrapper = mount(UserDropdown, {
      props: {
        username: '测试用户'
      },
      global: {
        plugins: [router, pinia, ElementPlus]
      }
    })

    expect(wrapper.find('.username').text()).toBe('测试用户')
  })

  it('prefers auth store username over custom prop', () => {
    const wrapper = mount(UserDropdown, {
      props: {
        username: '测试用户'
      },
      global: {
        plugins: [router, pinia, ElementPlus]
      }
    })

    expect(wrapper.find('.username').text()).toBe('侧栏管理员')
  })

  it('renders collapsed sidebar variant as a single centered trigger without username text', () => {
    const wrapper = mount(UserDropdown, {
      props: {
        collapsed: true
      },
      global: {
        plugins: [router, pinia, ElementPlus]
      }
    })

    expect(wrapper.find('.user-dropdown').classes()).toContain('is-collapsed')
    expect(wrapper.find('.username').exists()).toBe(false)
    expect(wrapper.find('.el-dropdown__caret-button').exists()).toBe(false)
    expect(wrapper.findAll('.el-button')).toHaveLength(1)
    expect(wrapper.find('.user-trigger-button').exists()).toBe(true)
  })

  it('opens account menu from collapsed single trigger', async () => {
    const wrapper = mount(UserDropdown, {
      attachTo: document.body,
      props: {
        collapsed: true
      },
      global: {
        plugins: [router, pinia, ElementPlus]
      }
    })

    await wrapper.get('.user-trigger-button').trigger('click')
    await flushPromises()

    const items = [...document.body.querySelectorAll('.el-dropdown-menu__item')].map((item) => item.textContent?.replace(/\s+/g, ' ').trim() ?? '')

    expect(items).toContain('个人中心')
    expect(items).toContain('修改密码')
    expect(items).toContain('退出登录')
  })

  it('renders dropdown shell', () => {
    const wrapper = mount(UserDropdown, {
      global: {
        plugins: [router, pinia, ElementPlus]
      }
    })

    expect(wrapper.find('.el-dropdown').exists()).toBe(true)
  })

  it('renders profile command without theme toggle in dropdown menu', async () => {
    const wrapper = mount(UserDropdown, {
      attachTo: document.body,
      global: {
        plugins: [router, pinia, ElementPlus]
      }
    })

    await wrapper.get('.el-dropdown__caret-button').trigger('click')
    await flushPromises()

    const items = [...document.body.querySelectorAll('.el-dropdown-menu__item')].map((item) => item.textContent?.replace(/\s+/g, ' ').trim() ?? '')

    expect(items).toContain('个人中心')
    expect(items).toContain('修改密码')
    expect(items).toContain('退出登录')
    expect(items).not.toContain('系统设置')
    expect(items).not.toContain('深色模式')
  })

  it('routes primary account trigger to personal center config group', async () => {
    const wrapper = mount(UserDropdown, {
      attachTo: document.body,
      global: {
        plugins: [router, pinia, ElementPlus]
      }
    })

    const primaryButton = wrapper.findAll('.el-button')[0]
    expect(primaryButton).toBeDefined()
    await primaryButton!.trigger('click')
    await flushPromises()

    expect(router.currentRoute.value.fullPath).toBe('/config?group=profile')
  })

  it('opens change password dialog when change-password command is triggered', async () => {
    const wrapper = mount(UserDropdown, {
      attachTo: document.body,
      global: {
        plugins: [router, pinia, ElementPlus]
      }
    })

    asUserDropdownVm(wrapper.vm).handleCommand('change-password')
    await flushPromises()

    expect(document.body.textContent ?? '').toContain('修改密码')
    expect(document.body.querySelector('input[type="password"]')).not.toBeNull()
  })

  it('navigates to personal center config group when profile command is triggered', async () => {
    const wrapper = mount(UserDropdown, {
      global: {
        plugins: [router, pinia, ElementPlus]
      }
    })

    asUserDropdownVm(wrapper.vm).handleCommand('profile')
    await flushPromises()

    expect(router.currentRoute.value.fullPath).toBe('/config?group=profile')
  })

  it('submits changed password through auth store', async () => {
    const wrapper = mount(UserDropdown, {
      attachTo: document.body,
      global: {
        plugins: [router, pinia, ElementPlus]
      }
    })

    const vm = asUserDropdownVm(wrapper.vm)
    vm.handleCommand('change-password')
    await flushPromises()

    vm.passwordForm.oldPassword = 'old-pass'
    vm.passwordForm.newPassword = 'new-pass'
    vm.passwordForm.confirmPassword = 'new-pass'

    await vm.submitChangePassword()

    expect(authStoreState.changePasswordMock).toHaveBeenCalledWith('old-pass', 'new-pass')
    expect(messageSuccessSpy).toHaveBeenCalled()
  })

  it('logs out and redirects to login after confirmation', async () => {
    const confirmSpy = vi.spyOn((await import('element-plus')).ElMessageBox, 'confirm').mockResolvedValue('confirm')

    const wrapper = mount(UserDropdown, {
      global: {
        plugins: [router, pinia, ElementPlus]
      }
    })

    asUserDropdownVm(wrapper.vm).handleCommand('logout')
    await flushPromises()

    expect(confirmSpy).toHaveBeenCalled()
    expect(authStoreState.logoutMock).toHaveBeenCalledTimes(1)
    expect(router.currentRoute.value.fullPath).toBe('/login')
    expect(messageSuccessSpy).toHaveBeenCalled()
  })
})

import { defineComponent, nextTick } from 'vue'
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { mount } from '@vue/test-utils'
import { createRouter, createWebHistory } from 'vue-router'
import { createPinia, setActivePinia } from 'pinia'
import ElementPlus from 'element-plus'
import { provideShellNavigation, type ShellNavigationContext } from '@/features/app-shell/shell-navigation'
import AppSidebar from './AppSidebar.vue'

vi.mock('@/stores/auth', () => ({
  useAuthStore: vi.fn(() => ({
    user: { username: '侧栏管理员' }
  }))
}))

vi.mock('./UserDropdown.vue', () => ({
  default: {
    name: 'UserDropdown',
    props: {
      username: {
        type: String,
        default: ''
      },
      collapsed: {
        type: Boolean,
        default: false
      }
    },
    template: '<div class="user-dropdown-mock" :data-username="username" :data-collapsed="String(collapsed)">UserDropdown</div>'
  }
}))

vi.mock('@element-plus/icons-vue', () => {
  const createIcon = (name: string) => ({
    name,
    template: `<svg data-icon="${name}" />`
  })

  return {
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
    ArrowDown: createIcon('ArrowDown'),
    ArrowLeft: createIcon('ArrowLeft'),
    Moon: createIcon('Moon'),
    Sunny: createIcon('Sunny'),
    UserFilled: createIcon('UserFilled')
  }
})

describe('AppSidebar', () => {
  let router: ReturnType<typeof createRouter>
  let pinia: ReturnType<typeof createPinia>
  let shellNavigation: ShellNavigationContext | null = null
  const originalMatchMedia = window.matchMedia

  const stubMatchMedia = (matches: boolean) => {
    window.matchMedia = vi.fn().mockImplementation((query: string) => ({
      matches,
      media: query,
      onchange: null,
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
      addListener: vi.fn(),
      removeListener: vi.fn(),
      dispatchEvent: vi.fn()
    })) as typeof window.matchMedia
  }

  const mountSidebar = () => mount(defineComponent({
    components: {
      AppSidebar
    },
    setup() {
      shellNavigation = provideShellNavigation()
      return {}
    },
    template: '<AppSidebar />'
  }), {
    global: {
      plugins: [router, pinia, ElementPlus]
    }
  })

  beforeEach(async () => {
    pinia = createPinia()
    setActivePinia(pinia)
    stubMatchMedia(false)

    router = createRouter({
      history: createWebHistory(),
      routes: [
        { path: '/', component: { template: '<div />' } },
        { path: '/dashboard', component: { template: '<div />' } },
        { path: '/tasks', component: { template: '<div />' } },
        { path: '/search', component: { template: '<div />' } },
        { path: '/notifications', component: { template: '<div />' } },
        { path: '/notifications/history', component: { template: '<div />' } },
        { path: '/config', component: { template: '<div />' } }
      ]
    })

    await router.push('/dashboard')
    await router.isReady()
  })

  afterEach(() => {
    window.matchMedia = originalMatchMedia
  })

  it('renders branded sidebar shell with contextual overview', () => {
    const wrapper = mountSidebar()

    expect(wrapper.find('.sidebar').exists()).toBe(true)
    expect(wrapper.find('.sidebar-shell').exists()).toBe(true)
    expect(wrapper.find('.logo-eyebrow').text()).toBe('Smart Media')
    expect(wrapper.get('.sidebar-overview-title').text()).toBe('概览')
    expect(wrapper.get('.sidebar-overview-copy').text()).toContain('7 个业务区')
  })

  it('renders footer account entry above the collapse button', () => {
    const wrapper = mountSidebar()

    expect(wrapper.find('.sidebar-account').exists()).toBe(true)
    expect(wrapper.find('.sidebar-account .user-dropdown-mock').exists()).toBe(true)
    expect(wrapper.get('.sidebar-account .user-dropdown-mock').attributes('data-collapsed')).toBe('false')
    expect(wrapper.find('.sidebar-menu .user-dropdown-mock').exists()).toBe(false)
    expect(wrapper.find('.sidebar-footer .collapse-button').exists()).toBe(true)
  })

  it('applies collapsed alignment hooks when button clicked', async () => {
    const wrapper = mountSidebar()

    const logoCopy = wrapper.get('.logo-copy')
    expect(logoCopy.isVisible()).toBe(true)
    expect(wrapper.get('.sidebar').classes()).not.toContain('is-collapsed')

    await wrapper.get('.sidebar-footer .collapse-button').trigger('click')
    await wrapper.vm.$nextTick()

    expect(logoCopy.attributes('style')).toContain('display: none')
    expect(wrapper.get('.sidebar').classes()).toContain('is-collapsed')
    expect(wrapper.get('.sidebar-shell').classes()).toContain('is-collapsed')
    expect(wrapper.get('.logo-container').classes()).toContain('collapsed')
    expect(wrapper.get('.sidebar-menu').classes()).toContain('is-collapsed')
    expect(wrapper.get('.sidebar-footer').classes()).toContain('is-collapsed')
  })

  it('passes collapsed state into the footer account entry and hides overview card', async () => {
    const wrapper = mountSidebar()

    expect(wrapper.get('.sidebar-account .user-dropdown-mock').attributes('data-collapsed')).toBe('false')
    expect(wrapper.get('.sidebar-overview').isVisible()).toBe(true)

    await wrapper.get('.sidebar-footer .collapse-button').trigger('click')
    await wrapper.vm.$nextTick()

    expect(wrapper.get('.sidebar-account .user-dropdown-mock').attributes('data-collapsed')).toBe('true')
    expect(wrapper.get('.sidebar-overview').attributes('style')).toContain('display: none')
  })

  it('renders menu with compact density class', () => {
    const wrapper = mountSidebar()

    const menu = wrapper.find('.sidebar-menu')
    expect(menu.exists()).toBe(true)
    expect(menu.classes()).toContain('is-dense')
  })

  it('starts in off-canvas drawer mode on narrow viewports', async () => {
    stubMatchMedia(true)
    await router.push('/dashboard')
    await router.isReady()

    const wrapper = mountSidebar()

    await nextTick()

    expect(wrapper.get('.sidebar').classes()).toContain('is-mobile')
    expect(wrapper.get('.sidebar').classes()).not.toContain('is-collapsed')
    expect(wrapper.get('.sidebar-shell').classes()).toContain('is-mobile')
    expect(wrapper.get('.sidebar-account .user-dropdown-mock').attributes('data-collapsed')).toBe('false')
  })

  it('opens and closes the mobile drawer through shared shell state', async () => {
    stubMatchMedia(true)
    await router.push('/dashboard')
    await router.isReady()

    const wrapper = mountSidebar()

    shellNavigation?.openMobileDrawer()
    await nextTick()

    expect(wrapper.get('.sidebar').classes()).toContain('is-drawer-open')
    expect(wrapper.get('.sidebar-shell').classes()).toContain('is-drawer-open')
    expect(wrapper.find('.sidebar-backdrop').exists()).toBe(true)

    await wrapper.get('.sidebar-backdrop').trigger('click')
    await nextTick()

    expect(wrapper.get('.sidebar').classes()).not.toContain('is-drawer-open')
    expect(wrapper.find('.sidebar-backdrop').exists()).toBe(false)
  })

  it('uses the longest matching menu path for the overview card title', async () => {
    await router.push('/notifications/history')
    await router.isReady()

    const wrapper = mountSidebar()

    expect(wrapper.get('.sidebar-overview-title').text()).toBe('通知历史')
  })

  it('keeps sidebar config entry scoped without a personal center menu', () => {
    const wrapper = mountSidebar()

    const menuItems = wrapper.findAll('.el-menu-item').map(node => node.text())

    expect(menuItems).toContain('系统配置')
    expect(menuItems).not.toContain('个人中心')
    expect(wrapper.find('.sidebar-menu .user-dropdown-mock').exists()).toBe(false)
  })
})

import { defineComponent } from 'vue'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount } from '@vue/test-utils'
import { createRouter, createWebHistory } from 'vue-router'
import { createPinia, setActivePinia } from 'pinia'
import ElementPlus from 'element-plus'
import { provideShellNavigation, type ShellNavigationContext } from '@/features/app-shell/shell-navigation'
import AppHeader from './AppHeader.vue'

vi.mock('@element-plus/icons-vue', () => {
  const createIcon = (name: string) => ({
    name,
    template: `<svg data-icon="${name}" />`
  })

  return {
    Moon: createIcon('Moon'),
    Sunny: createIcon('Sunny'),
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
    ArrowRight: createIcon('ArrowRight')
  }
})

vi.mock('@/components/Breadcrumb.vue', () => ({
  default: {
    name: 'Breadcrumb',
    template: '<div class="breadcrumb-mock">Breadcrumb</div>'
  }
}))

vi.mock('./UserDropdown.vue', () => ({
  default: {
    name: 'UserDropdown',
    props: {
      username: {
        type: String,
        default: ''
      }
    },
    template: '<div class="user-dropdown-mock" :data-username="username">UserDropdown</div>'
  }
}))

describe('AppHeader', () => {
  let router: ReturnType<typeof createRouter>
  let pinia: ReturnType<typeof createPinia>
  let shellNavigation: ShellNavigationContext | null = null

  const mountHeader = async (options?: { mobile?: boolean; path?: string }) => {
    if (options?.path) {
      await router.push(options.path)
      await router.isReady()
    }

    return mount(defineComponent({
      components: {
        AppHeader
      },
      setup() {
        shellNavigation = provideShellNavigation()

        if (options?.mobile) {
          shellNavigation.syncViewport(true)
        }

        return {}
      },
      template: '<AppHeader />'
    }), {
      global: {
        plugins: [router, pinia, ElementPlus]
      }
    })
  }

  beforeEach(async () => {
    vi.clearAllMocks()
    localStorage.clear()
    document.documentElement.classList.remove('dark')

    pinia = createPinia()
    setActivePinia(pinia)

    router = createRouter({
      history: createWebHistory(),
      routes: [
        {
          path: '/dashboard',
          name: 'Dashboard',
          component: { template: '<div />' },
          meta: { title: '系统概览' }
        },
        {
          path: '/notifications',
          component: { template: '<router-view />' },
          meta: { title: '通知服务' },
          children: [
            {
              path: 'history',
              name: 'NotificationHistory',
              component: { template: '<div />' },
              meta: { title: '通知历史' }
            }
          ]
        }
      ]
    })

    await router.push('/dashboard')
    await router.isReady()
  })

  it('renders the contextual control-deck summary above the utility rail', async () => {
    const wrapper = await mountHeader()

    expect(wrapper.find('.header').exists()).toBe(true)
    expect(wrapper.find('.header-shell').exists()).toBe(true)
    expect(wrapper.find('.header-context').exists()).toBe(true)
    expect(wrapper.get('.context-chip').text()).toBe('Control Deck')
    expect(wrapper.get('.context-title').text()).toBe('系统概览')
    expect(wrapper.get('.context-description').text()).toContain('缓存命中')
  })

  it('keeps only the user entry in the rail for top-level routes', async () => {
    const wrapper = await mountHeader()

    expect(wrapper.find('.header-shell').classes()).toContain('is-user-only')
    expect(wrapper.find('.header-rail').classes()).toContain('is-user-only')
    expect(wrapper.find('.header-breadcrumb-panel').exists()).toBe(false)
    expect(wrapper.find('.user-dropdown-mock').exists()).toBe(true)
    expect(wrapper.get('.user-dropdown-mock').attributes('data-username')).toBe('管理员')
  })

  it('renders breadcrumb panel when the route has nested hierarchy', async () => {
    const wrapper = await mountHeader({ path: '/notifications/history' })

    expect(wrapper.find('.header-breadcrumb-panel').exists()).toBe(true)
    expect(wrapper.find('.breadcrumb-mock').exists()).toBe(true)
    expect(wrapper.find('.user-dropdown-mock').exists()).toBe(true)
  })

  it('does not render standalone theme toggle in header', async () => {
    const wrapper = await mountHeader()

    expect(wrapper.find('.theme-toggle').exists()).toBe(false)
    expect(wrapper.find('.toggle-label').exists()).toBe(false)
    expect(wrapper.find('.el-switch').exists()).toBe(false)
  })

  it('shows a mobile drawer trigger when the shell enters narrow viewport mode', async () => {
    const wrapper = await mountHeader({ mobile: true })
    const trigger = wrapper.get('.header-menu-trigger')

    expect(trigger.attributes('aria-expanded')).toBe('false')

    await trigger.trigger('click')

    expect(shellNavigation?.isMobileDrawerOpen.value).toBe(true)
    expect(wrapper.get('.header-menu-trigger').attributes('aria-expanded')).toBe('true')
  })
})

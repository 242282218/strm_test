import { computed, inject, provide, ref, type ComputedRef, type InjectionKey, type Ref } from 'vue'

export interface ShellNavigationContext {
  isMobileViewport: Ref<boolean>
  isDesktopCollapsed: Ref<boolean>
  isMobileDrawerOpen: Ref<boolean>
  isSidebarCollapsed: ComputedRef<boolean>
  sidebarWidth: ComputedRef<string>
  syncViewport: (matches: boolean) => void
  openMobileDrawer: () => void
  closeMobileDrawer: () => void
  toggleMobileDrawer: () => void
  toggleDesktopCollapse: () => void
}

const shellNavigationKey: InjectionKey<ShellNavigationContext> = Symbol('shell-navigation')

const createShellNavigationContext = (): ShellNavigationContext => {
  const isMobileViewport = ref(false)
  const isDesktopCollapsed = ref(false)
  const isMobileDrawerOpen = ref(false)

  const isSidebarCollapsed = computed(() => !isMobileViewport.value && isDesktopCollapsed.value)
  const sidebarWidth = computed(() => {
    if (isMobileViewport.value) {
      return '0px'
    }

    return isDesktopCollapsed.value
      ? 'var(--sidebar-width-collapsed)'
      : 'var(--sidebar-width)'
  })

  const closeMobileDrawer = () => {
    isMobileDrawerOpen.value = false
  }

  const openMobileDrawer = () => {
    if (!isMobileViewport.value) {
      return
    }

    isMobileDrawerOpen.value = true
  }

  const toggleMobileDrawer = () => {
    if (!isMobileViewport.value) {
      return
    }

    isMobileDrawerOpen.value = !isMobileDrawerOpen.value
  }

  const toggleDesktopCollapse = () => {
    if (isMobileViewport.value) {
      closeMobileDrawer()
      return
    }

    isDesktopCollapsed.value = !isDesktopCollapsed.value
  }

  const syncViewport = (matches: boolean) => {
    isMobileViewport.value = matches

    if (!matches) {
      closeMobileDrawer()
    }
  }

  return {
    isMobileViewport,
    isDesktopCollapsed,
    isMobileDrawerOpen,
    isSidebarCollapsed,
    sidebarWidth,
    syncViewport,
    openMobileDrawer,
    closeMobileDrawer,
    toggleMobileDrawer,
    toggleDesktopCollapse,
  }
}

export const provideShellNavigation = (): ShellNavigationContext => {
  const context = createShellNavigationContext()
  provide(shellNavigationKey, context)
  return context
}

export const useShellNavigation = (): ShellNavigationContext => {
  return inject(shellNavigationKey, createShellNavigationContext())
}

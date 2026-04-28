import { computed, ref } from 'vue'

export type ThemeMode = 'light' | 'dark'

const THEME_STORAGE_KEY = 'theme'
const currentTheme = ref<ThemeMode>('light')

const getStoredTheme = (): ThemeMode => {
  if (typeof window === 'undefined') {
    return currentTheme.value
  }

  const storedTheme = window.localStorage.getItem(THEME_STORAGE_KEY)
  if (storedTheme === 'dark' || storedTheme === 'light') {
    return storedTheme
  }

  return document.documentElement.classList.contains('dark') ? 'dark' : 'light'
}

const applyTheme = (theme: ThemeMode, persist = true) => {
  currentTheme.value = theme

  if (typeof document !== 'undefined') {
    document.documentElement.classList.toggle('dark', theme === 'dark')
  }

  if (persist && typeof window !== 'undefined') {
    window.localStorage.setItem(THEME_STORAGE_KEY, theme)
  }
}

export const initTheme = () => {
  applyTheme(getStoredTheme())
}

export const useTheme = () => {
  initTheme()

  const isDark = computed({
    get: () => currentTheme.value === 'dark',
    set: (value: boolean) => {
      applyTheme(value ? 'dark' : 'light')
    },
  })

  const setTheme = (theme: ThemeMode) => {
    applyTheme(theme)
  }

  const toggleTheme = () => {
    applyTheme(currentTheme.value === 'dark' ? 'light' : 'dark')
  }

  return {
    theme: computed(() => currentTheme.value),
    isDark,
    setTheme,
    toggleTheme,
  }
}

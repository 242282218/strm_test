import { defineStore } from 'pinia'
import { ref, computed } from 'vue'

interface User {
  id: number
  username: string
  email?: string
}

export const useAuthStore = defineStore('auth', () => {
  // State
  const token = ref<string | null>(localStorage.getItem('token'))
  const user = ref<User | null>(null)
  const loading = ref(false)

  // Getters
  const isAuthenticated = computed(() => !!token.value)

  // Actions
  const login = async (username: string, password: string) => {
    loading.value = true
    try {
      // 这里应该调用实际的登录API
      // const response = await axios.post('/api/auth/login', { username, password })
      // token.value = response.data.token
      
      // 临时模拟登录
      if (username === 'admin' && password === 'admin') {
        token.value = 'mock_token_' + Date.now()
        localStorage.setItem('token', token.value)
        return true
      }
      return false
    } catch (error) {
      console.error('Login failed:', error)
      return false
    } finally {
      loading.value = false
    }
  }

  const logout = () => {
    token.value = null
    user.value = null
    localStorage.removeItem('token')
  }

  const checkAuth = () => {
    const storedToken = localStorage.getItem('token')
    if (storedToken) {
      token.value = storedToken
      return true
    }
    return false
  }

  return {
    token,
    user,
    loading,
    isAuthenticated,
    login,
    logout,
    checkAuth
  }
})

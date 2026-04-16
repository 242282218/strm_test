import { defineStore } from 'pinia'
import { ref, computed } from 'vue'

import api from '@/api/index'
import { getErrorMessage } from '@/utils/error-message'

// 用户状态 - 需要在拦截器外部定义
const user = ref<User | null>(null)

interface User {
  id: number
  username: string
  email?: string
  role: string
  is_active: boolean
  created_at?: string
  last_login?: string
}

interface LoginResponse {
  access_token: string
  refresh_token: string
  token_type: string
  expires_in: number
  user: User
}

export const useAuthStore = defineStore('auth', () => {
  // State - Token 现在存储在 HttpOnly Cookie 中，无需在前端存储
  const loading = ref(false)

  // Getters
  const isAuthenticated = computed(() => !!user.value)

  // Actions
  const login = async (username: string, password: string): Promise<boolean> => {
    loading.value = true
    try {
      const data = await api.post<LoginResponse>('/auth/login', {
        username,
        password,
      })

      // Token 已通过 HttpOnly Cookie 设置，无需手动存储
      user.value = data.user

      return true
    } catch (error) {
      console.error('Login failed:', error)
      throw new Error(getErrorMessage(error, '登录失败，请检查网络连接'))
    } finally {
      loading.value = false
    }
  }

  const logout = async () => {
    try {
      // 调用后端登出接口清除 Cookie
      await api.post('/auth/logout')
    } catch (error) {
      console.error('Logout API call failed:', error)
    } finally {
      // 清除用户状态
      user.value = null
    }
  }

  const checkAuth = async (): Promise<boolean> => {
    try {
      // 验证 Token 是否有效（通过 Cookie 自动发送）
      const currentUser = await api.get<User>('/auth/me')
      user.value = currentUser
      return true
    } catch {
      // Token 无效，清除状态
      user.value = null
      return false
    }
  }

  const changePassword = async (
    oldPassword: string,
    newPassword: string
  ): Promise<boolean> => {
    try {
      await api.post('/auth/change-password', {
        old_password: oldPassword,
        new_password: newPassword,
      })
      return true
    } catch (error) {
      throw new Error(getErrorMessage(error, '修改密码失败'))
    }
  }

  return {
    user,
    loading,
    isAuthenticated,
    login,
    logout,
    checkAuth,
    changePassword,
  }
})

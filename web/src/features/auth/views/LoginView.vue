<template>
  <div class="login-container">
    <!-- 背景动画 -->
    <div class="bg-animation">
      <div class="bg-circle circle-1"></div>
      <div class="bg-circle circle-2"></div>
      <div class="bg-circle circle-3"></div>
    </div>

    <!-- 登录卡片 -->
    <div class="login-card" :class="{ 'shake': shake }">
      <div class="login-header">
        <div class="logo">
          <el-icon size="48" class="logo-icon"><Cloudy /></el-icon>
        </div>
        <h1 class="title">Quark STRM Manager</h1>
        <p class="subtitle">夸克网盘 STRM 文件管理系统</p>
      </div>

      <el-form
        ref="formRef"
        :model="form"
        :rules="rules"
        class="login-form"
        @keyup.enter="handleLogin"
      >
        <el-form-item prop="username">
          <el-input
            v-model="form.username"
            placeholder="用户名"
            size="large"
            :prefix-icon="User"
            clearable
          />
        </el-form-item>

        <el-form-item prop="password">
          <el-input
            v-model="form.password"
            type="password"
            placeholder="密码"
            size="large"
            :prefix-icon="Lock"
            show-password
            clearable
          />
        </el-form-item>

        <div class="form-options">
          <el-checkbox v-model="form.remember">记住我</el-checkbox>
        </div>

        <el-button
          type="primary"
          size="large"
          class="login-btn"
          :loading="authStore.loading"
          @click="handleLogin"
        >
          {{ authStore.loading ? '登录中...' : '登 录' }}
        </el-button>
      </el-form>

      <!-- 错误提示 -->
      <el-alert
        v-if="errorMessage"
        :title="errorMessage"
        type="error"
        show-icon
        closable
        class="error-alert"
        @close="errorMessage = ''"
      />

      <div v-if="showInitAdmin" class="login-footer">
        <p>首次使用请点击下方按钮初始化管理员账户，默认账号密码为 admin/admin</p>
        <el-button
          type="primary"
          link
          size="small"
          :loading="initLoading"
          @click="handleInitAdmin"
        >
          {{ initLoading ? '初始化中...' : '初始化管理员' }}
        </el-button>
      </div>
    </div>

    <!-- 主题切换 -->
    <div class="theme-toggle">
      <el-switch
        v-model="isDark"
        :active-icon="Moon"
        :inactive-icon="Sunny"
        inline-prompt
        @change="toggleTheme"
      />
    </div>

    <!-- 版本信息 -->
    <div class="version">v1.0.0</div>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import api from '@/api/index'
import { getAuthStatus } from '@/api/auth'
import type { AuthStatusResponse } from '@/api/auth'
import { User, Lock, Moon, Sunny, Cloudy } from '@/components/icons'
import { useLoading, useNotification, useTheme } from '@/composables'
import { useAuthStore } from '@/stores/auth'
import { getErrorMessage, isAxiosError } from '@/utils/error-message'

interface InitAdminResponse {
  username: string
  password_generated: boolean
  generated_password?: string | null
}

const router = useRouter()
const authStore = useAuthStore()
const { success, error } = useNotification()
const { loading: initLoading, withLoading } = useLoading()

const formRef = ref()
const shake = ref(false)
const errorMessage = ref('')
const authStatus = ref<AuthStatusResponse | null>(null)
const { isDark, setTheme } = useTheme()

const showInitAdmin = computed(() => {
  if (!authStatus.value) {
    return false
  }

  return !authStatus.value.has_admin_user && authStatus.value.can_init_admin
})

const form = reactive({
  username: '',
  password: '',
  remember: false
})

const rules = {
  username: [
    { required: true, message: 'Enter username', trigger: 'blur' }
  ],
  password: [
    { required: true, message: 'Enter password', trigger: 'blur' },
    { min: 4, message: 'Password must be at least 4 characters', trigger: 'blur' }
  ]
}

const handleLogin = async () => {
  if (!formRef.value) return

  await formRef.value.validate(async (valid: boolean) => {
    if (!valid) return

    errorMessage.value = ''
    try {
      const result = await authStore.login(form.username, form.password)
      if (!result) return

      success('Login successful')

      if (form.remember) {
        localStorage.setItem('rememberedUser', form.username)
      } else {
        localStorage.removeItem('rememberedUser')
      }

      router.push('/')
    } catch (err) {
      shake.value = true
      setTimeout(() => {
        shake.value = false
      }, 500)
      errorMessage.value = getErrorMessage(err, 'Login failed')
    }
  })
}

const refreshAuthStatus = async () => {
  try {
    authStatus.value = await getAuthStatus()
  } catch (err) {
    authStatus.value = null
    console.warn('Failed to initialize auth status', err)
  }
}

const handleInitAdmin = async () => {
  try {
    await withLoading(async () => {
      const response = await api.post<InitAdminResponse>('/auth/init-admin')
      const passwordMessage = response.generated_password
        ? ` Password: ${response.generated_password}`
        : ''

      success(`Admin account created. Username: ${response.username}${passwordMessage}`, 'Initialization complete')
      form.username = response.username

      if (response.generated_password) {
        form.password = response.generated_password
      }

      await refreshAuthStatus()
    })
  } catch (err) {
    const statusCode = isAxiosError(err) ? err.response?.status : undefined
    error(getErrorMessage(err, 'Admin initialization failed'))

    if (statusCode === 403 || statusCode === 409) {
      await refreshAuthStatus()
    }
  }
}

const toggleTheme = (val: boolean) => {
  setTheme(val ? 'dark' : 'light')
}

onMounted(async () => {
  if (authStore.isAuthenticated) {
    router.push('/')
    return
  }

  await refreshAuthStatus()

  const rememberedUser = localStorage.getItem('rememberedUser')
  if (rememberedUser) {
    form.username = rememberedUser
    form.remember = true
  }
})
</script>

<style scoped>
.login-container {
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  background: var(--bg-primary);
  position: relative;
  overflow: hidden;
}

/* 背景动画 */
.bg-animation {
  position: absolute;
  width: 100%;
  height: 100%;
  overflow: hidden;
  z-index: 0;
}

.bg-circle {
  position: absolute;
  border-radius: 50%;
  filter: blur(80px);
  opacity: 0.5;
  animation: float 20s infinite ease-in-out;
}

.circle-1 {
  width: 400px;
  height: 400px;
  background: linear-gradient(135deg, #3b82f6, #8b5cf6);
  top: -100px;
  left: -100px;
  animation-delay: 0s;
}

.circle-2 {
  width: 300px;
  height: 300px;
  background: linear-gradient(135deg, #8b5cf6, #ec4899);
  bottom: -50px;
  right: -50px;
  animation-delay: -7s;
}

.circle-3 {
  width: 200px;
  height: 200px;
  background: linear-gradient(135deg, #06b6d4, #3b82f6);
  top: 50%;
  left: 50%;
  animation-delay: -14s;
}

@keyframes float {
  0%, 100% {
    transform: translate(0, 0) scale(1);
  }
  33% {
    transform: translate(30px, -30px) scale(1.1);
  }
  66% {
    transform: translate(-20px, 20px) scale(0.9);
  }
}

/* 登录卡片 */
.login-card {
  background: var(--glass-bg);
  backdrop-filter: var(--glass-blur);
  -webkit-backdrop-filter: var(--glass-blur);
  border-radius: var(--radius-2xl);
  padding: 48px;
  width: 100%;
  max-width: 440px;
  box-shadow: var(--glass-shadow), var(--shadow-2xl);
  border: 1px solid var(--glass-border);
  z-index: 1;
  animation: scaleIn 0.5s cubic-bezier(0.34, 1.56, 0.64, 1);
}

.login-card.shake {
  animation: shake 0.5s ease;
}

@keyframes shake {
  0%, 100% { transform: translateX(0); }
  10%, 30%, 50%, 70%, 90% { transform: translateX(-5px); }
  20%, 40%, 60%, 80% { transform: translateX(5px); }
}

/* 登录头部 */
.login-header {
  text-align: center;
  margin-bottom: 32px;
}

.logo {
  width: 88px;
  height: 88px;
  margin: 0 auto 24px;
  background: var(--gradient-primary);
  border-radius: var(--radius-xl);
  display: flex;
  align-items: center;
  justify-content: center;
  box-shadow: var(--shadow-xl), 0 0 40px rgba(102, 126, 234, 0.3);
  animation: float 6s ease-in-out infinite;
  position: relative;
}

.logo::before {
  content: '';
  position: absolute;
  inset: -2px;
  background: var(--gradient-primary);
  border-radius: var(--radius-xl);
  opacity: 0.5;
  filter: blur(10px);
  z-index: -1;
}

.logo-icon {
  color: white;
}

.title {
  font-size: 32px;
  font-weight: 700;
  margin-bottom: 8px;
  background: var(--gradient-primary);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  background-clip: text;
  letter-spacing: -0.5px;
}

.subtitle {
  color: var(--text-secondary);
  font-size: 14px;
}

/* 登录表单 */
.login-form {
  margin-bottom: 16px;
}

:deep(.el-input__wrapper) {
  border-radius: var(--radius-md);
  padding: 4px 12px;
}

:deep(.el-input__inner) {
  height: 44px;
}

.form-options {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 24px;
}

.login-btn {
  width: 100%;
  height: 48px;
  font-size: 16px;
  font-weight: 600;
  border-radius: var(--radius-md);
}

/* 错误提示 */
.error-alert {
  margin-top: 16px;
}

/* 登录底部 */
.login-footer {
  text-align: center;
  color: var(--text-tertiary);
  font-size: 12px;
  margin-top: 16px;
}

/* 主题切换 */
.theme-toggle {
  position: absolute;
  top: 24px;
  right: 24px;
  z-index: 1;
}

/* 版本信息 */
.version {
  position: absolute;
  bottom: 24px;
  right: 24px;
  color: var(--text-tertiary);
  font-size: 12px;
  z-index: 1;
}

/* 响应式 */
@media (max-width: 480px) {
  .login-card {
    margin: 20px;
    padding: 32px 24px;
  }

  .title {
    font-size: 24px;
  }

  .bg-circle {
    filter: blur(60px);
  }

  .circle-1 {
    width: 250px;
    height: 250px;
  }

  .circle-2 {
    width: 200px;
    height: 200px;
  }
}
</style>

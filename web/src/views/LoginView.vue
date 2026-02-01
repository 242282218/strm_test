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
          <el-link type="primary" :underline="false">忘记密码?</el-link>
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

      <div class="login-footer">
        <p>默认账号: admin / admin</p>
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
import { ref, reactive } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { User, Lock, Moon, Sunny, Cloudy } from '@element-plus/icons-vue'
import { useAuthStore } from '@/stores/auth'

const router = useRouter()
const authStore = useAuthStore()
const formRef = ref()
const shake = ref(false)
const isDark = ref(false)

const form = reactive({
  username: '',
  password: '',
  remember: false
})

const rules = {
  username: [
    { required: true, message: '请输入用户名', trigger: 'blur' }
  ],
  password: [
    { required: true, message: '请输入密码', trigger: 'blur' },
    { min: 4, message: '密码至少4位', trigger: 'blur' }
  ]
}

const handleLogin = async () => {
  if (!formRef.value) return

  await formRef.value.validate(async (valid: boolean) => {
    if (valid) {
      const success = await authStore.login(form.username, form.password)
      if (success) {
        ElMessage.success('登录成功')
        router.push('/')
      } else {
        shake.value = true
        setTimeout(() => shake.value = false, 500)
        ElMessage.error('用户名或密码错误')
      }
    }
  })
}

const toggleTheme = (val: boolean) => {
  if (val) {
    document.documentElement.classList.add('dark')
  } else {
    document.documentElement.classList.remove('dark')
  }
}
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
  background: var(--bg-secondary);
  border-radius: var(--radius-xl);
  padding: 48px;
  width: 100%;
  max-width: 420px;
  box-shadow: var(--shadow-xl);
  border: 1px solid var(--border-color);
  z-index: 1;
  animation: fadeIn 0.6s ease;
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
  width: 80px;
  height: 80px;
  margin: 0 auto 20px;
  background: linear-gradient(135deg, var(--primary-color), var(--secondary-color));
  border-radius: var(--radius-lg);
  display: flex;
  align-items: center;
  justify-content: center;
  box-shadow: var(--shadow-lg);
}

.logo-icon {
  color: white;
}

.title {
  font-size: 28px;
  font-weight: 700;
  margin-bottom: 8px;
  background: linear-gradient(135deg, var(--primary-color), var(--secondary-color));
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  background-clip: text;
}

.subtitle {
  color: var(--text-secondary);
  font-size: 14px;
}

/* 登录表单 */
.login-form {
  margin-bottom: 24px;
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

/* 登录底部 */
.login-footer {
  text-align: center;
  color: var(--text-tertiary);
  font-size: 12px;
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

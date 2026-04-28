<template>
  <el-dropdown
    v-if="collapsed"
    class="user-dropdown"
    :class="{ 'is-collapsed': collapsed }"
    trigger="click"
    :placement="dropdownPlacement"
    @command="handleCommand"
  >
    <el-button class="user-trigger-button" aria-label="打开账户菜单">
      <span class="user-trigger-content">
        <el-avatar :size="30" :icon="UserFilled" />
      </span>
    </el-button>
    <template #dropdown>
      <el-dropdown-menu>
        <el-dropdown-item command="profile">个人中心</el-dropdown-item>
        <el-dropdown-item command="change-password">修改密码</el-dropdown-item>
        <el-dropdown-item divided command="logout">退出登录</el-dropdown-item>
      </el-dropdown-menu>
    </template>
  </el-dropdown>

  <el-dropdown
    v-else
    class="user-dropdown"
    :class="{ 'is-collapsed': collapsed }"
    split-button
    :placement="dropdownPlacement"
    @click="handleProfileClick"
    @command="handleCommand"
  >
    <span class="user-trigger-content">
      <el-avatar :size="30" :icon="UserFilled" />
      <span class="username">{{ displayName }}</span>
    </span>
    <template #dropdown>
      <el-dropdown-menu>
        <el-dropdown-item command="profile">个人中心</el-dropdown-item>
        <el-dropdown-item command="change-password">修改密码</el-dropdown-item>
        <el-dropdown-item divided command="logout">退出登录</el-dropdown-item>
      </el-dropdown-menu>
    </template>
  </el-dropdown>

  <el-dialog v-model="changePasswordDialogVisible" title="修改密码" width="420px" append-to-body destroy-on-close>
    <el-form label-width="90px">
      <el-form-item label="原密码">
        <el-input v-model="passwordForm.oldPassword" type="password" show-password />
      </el-form-item>
      <el-form-item label="新密码">
        <el-input v-model="passwordForm.newPassword" type="password" show-password />
      </el-form-item>
      <el-form-item label="确认密码">
        <el-input v-model="passwordForm.confirmPassword" type="password" show-password />
      </el-form-item>
    </el-form>
    <template #footer>
      <span class="dialog-footer">
        <el-button @click="closeChangePasswordDialog">取消</el-button>
        <el-button type="primary" @click="submitChangePassword">确认</el-button>
      </span>
    </template>
  </el-dialog>
</template>

<script setup lang="ts">
import { computed, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { UserFilled } from '@/components/icons'
import { useAuthStore } from '@/stores/auth'

defineOptions({
  name: 'UserDropdown'
})

interface Props {
  username?: string
  collapsed?: boolean
}

const props = withDefaults(defineProps<Props>(), {
  username: '',
  collapsed: false
})

const router = useRouter()
const authStore = useAuthStore()

const changePasswordDialogVisible = ref(false)
const passwordForm = reactive({
  oldPassword: '',
  newPassword: '',
  confirmPassword: ''
})

const displayName = computed(() => authStore.user?.username || props.username || '管理员')
const dropdownPlacement = computed(() => props.collapsed ? 'right-start' : 'top-end')

const navigateToProfile = () => {
  return router.push({
    path: '/config',
    query: { group: 'profile' }
  })
}

const resetPasswordForm = () => {
  passwordForm.oldPassword = ''
  passwordForm.newPassword = ''
  passwordForm.confirmPassword = ''
}

const closeChangePasswordDialog = () => {
  changePasswordDialogVisible.value = false
  resetPasswordForm()
}

const handleProfileClick = () => {
  return navigateToProfile()
}

const submitChangePassword = async () => {
  if (!passwordForm.oldPassword || !passwordForm.newPassword || !passwordForm.confirmPassword) {
    ElMessage.error('请填写完整密码信息')
    return
  }
  if (passwordForm.newPassword !== passwordForm.confirmPassword) {
    ElMessage.error('两次输入的新密码不一致')
    return
  }

  await authStore.changePassword(passwordForm.oldPassword, passwordForm.newPassword)
  ElMessage.success('密码修改成功')
  closeChangePasswordDialog()
}

const handleCommand = async (command: string) => {
  switch (command) {
    case 'profile':
      await navigateToProfile()
      break
    case 'change-password':
      changePasswordDialogVisible.value = true
      break
    case 'logout':
      ElMessageBox.confirm('确定要退出登录吗？', '提示', {
        confirmButtonText: '确定',
        cancelButtonText: '取消',
        type: 'warning'
      }).then(() => {
        void authStore.logout()
        void router.push('/login')
        ElMessage.success('已退出登录')
      })
      break
  }
}
</script>

<style scoped>
.user-dropdown {
  display: inline-flex;
  max-width: 100%;
}

.user-dropdown :deep(.el-button-group) {
  display: inline-flex;
  align-items: center;
  max-width: 100%;
}

.user-dropdown :deep(.el-button) {
  min-height: 42px;
  border-color: var(--border-light);
  background: rgba(255, 255, 255, 0.36);
  color: var(--text-primary);
  transition:
    background-color var(--transition-fast),
    border-color var(--transition-fast),
    transform var(--transition-fast);
}

.user-dropdown :deep(.el-button:hover) {
  background: rgba(255, 255, 255, 0.5);
  border-color: var(--border-medium);
  transform: translateY(-1px);
}

.user-dropdown :deep(.el-button:first-child) {
  padding: 6px 14px 6px 8px;
  border-radius: var(--radius-full) 0 0 var(--radius-full);
}

.user-dropdown :deep(.el-dropdown__caret-button) {
  padding-inline: 10px;
  border-radius: 0 var(--radius-full) var(--radius-full) 0;
}

.user-dropdown.is-collapsed :deep(.el-button) {
  width: var(--sidebar-axis-size, 44px);
  height: var(--sidebar-axis-size, 44px);
  padding: 0;
  justify-content: center;
  border-radius: 14px;
  background: transparent;
  border-color: transparent;
}

.user-dropdown.is-collapsed :deep(.el-button:hover) {
  background: rgba(79, 141, 246, 0.08);
  border-color: transparent;
  transform: none;
}

.user-trigger-button {
  display: inline-flex;
  align-items: center;
  justify-content: center;
}

.user-trigger-content {
  display: inline-flex;
  align-items: center;
  gap: 10px;
  min-width: 0;
}

.username {
  font-size: 0.9rem;
  font-weight: var(--font-semibold);
  color: var(--text-primary);
  white-space: nowrap;
}

@media (max-width: 768px) {
  .username {
    display: none;
  }

  .user-dropdown :deep(.el-button:first-child) {
    padding-right: 10px;
  }
}
</style>

<template>
  <div class="config-page">
    <div class="page-header">
      <h2>系统配置</h2>
    </div>

    <div class="config-content">
      <el-form :model="config" label-width="120px" class="config-form">
        <el-divider>夸克网盘配置</el-divider>
        
        <el-form-item label="Cookie">
          <el-input
            v-model="config.cookie"
            type="textarea"
            :rows="3"
            placeholder="请输入夸克网盘Cookie"
            show-password
          />
        </el-form-item>

        <el-form-item label="根目录ID">
          <el-input v-model="config.rootId" placeholder="0" />
        </el-form-item>

        <el-divider>Emby配置</el-divider>

        <el-form-item label="Emby地址">
          <el-input v-model="config.embyUrl" placeholder="http://localhost:8096" />
        </el-form-item>

        <el-form-item label="API密钥">
          <el-input v-model="config.apiKey" show-password placeholder="请输入Emby API密钥" />
        </el-form-item>

        <el-divider>Telegram Bot配置 (预留)</el-divider>

        <el-form-item label="Bot Token">
          <el-input v-model="config.telegramToken" placeholder="预留配置项" disabled />
        </el-form-item>

        <el-form-item label="Chat ID">
          <el-input v-model="config.telegramChatId" placeholder="预留配置项" disabled />
        </el-form-item>

        <el-form-item>
          <el-button type="primary" @click="saveConfig">保存配置</el-button>
          <el-button @click="resetConfig">重置</el-button>
        </el-form-item>
      </el-form>
    </div>
  </div>
</template>

<script setup lang="ts">
import { reactive } from 'vue'
import { ElMessage } from 'element-plus'

const config = reactive({
  cookie: '',
  rootId: '0',
  embyUrl: '',
  apiKey: '',
  telegramToken: '',
  telegramChatId: ''
})

const saveConfig = () => {
  ElMessage.success('配置已保存')
}

const resetConfig = () => {
  ElMessage.info('配置已重置')
}
</script>

<style scoped>
.config-page {
  padding: 8px;
}

.page-header {
  margin-bottom: 24px;
}

.page-header h2 {
  margin: 0;
  font-size: 24px;
  font-weight: 600;
}

.config-content {
  background: var(--bg-secondary);
  border-radius: var(--radius-lg);
  padding: 24px;
  box-shadow: var(--shadow-sm);
  border: 1px solid var(--border-color);
  max-width: 800px;
}

.config-form {
  margin-top: 20px;
}
</style>

<template>
  <div class="tasks-page">
    <div class="page-header">
      <h2>任务管理</h2>
      <el-button type="primary" @click="createTask">
        <el-icon><Plus /></el-icon>
        新建任务
      </el-button>
    </div>

    <div class="tasks-content">
      <el-empty description="任务列表" />
    </div>
  </div>
</template>

<script setup lang="ts">
import { ElMessage } from 'element-plus'
import { Plus } from '@element-plus/icons-vue'

const createTask = () => {
  ElMessage.info('创建任务功能开发中')
}
</script>

<style scoped>
.tasks-page {
  padding: 8px;
}

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 24px;
}

.page-header h2 {
  margin: 0;
  font-size: 24px;
  font-weight: 600;
}

.tasks-content {
  background: var(--bg-secondary);
  border-radius: var(--radius-lg);
  padding: 24px;
  box-shadow: var(--shadow-sm);
  border: 1px solid var(--border-color);
}
</style>

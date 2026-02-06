<template>
  <div class="scrape-pathes-page">
    <div class="page-header">
      <h2>刮削目录</h2>
      <div class="header-actions">
        <el-button :icon="RefreshRight" @click="loadPaths">刷新</el-button>
        <el-button type="primary" :icon="Plus" @click="openCreateDialog">新增目录</el-button>
      </div>
    </div>

    <el-card shadow="never" class="card">
      <el-form :inline="true" class="filters">
        <el-form-item label="关键词">
          <el-input
            v-model="filters.keyword"
            placeholder="source/dest/path_id"
            clearable
            @keyup.enter="loadPaths"
          />
        </el-form-item>
        <el-form-item label="状态">
          <el-select v-model="filters.status" placeholder="全部" clearable style="width: 150px">
            <el-option label="idle" value="idle" />
            <el-option label="running" value="running" />
            <el-option label="stopped" value="stopped" />
          </el-select>
        </el-form-item>
        <el-form-item label="启用">
          <el-select v-model="filters.enabled" placeholder="全部" clearable style="width: 120px">
            <el-option label="是" :value="true" />
            <el-option label="否" :value="false" />
          </el-select>
        </el-form-item>
        <el-form-item>
          <el-button type="primary" @click="loadPaths">查询</el-button>
          <el-button @click="resetFilters">重置</el-button>
        </el-form-item>
      </el-form>

      <el-table :data="paths" v-loading="loading" stripe border>
        <el-table-column prop="source_path" label="源目录" min-width="220" show-overflow-tooltip />
        <el-table-column prop="dest_path" label="目标目录" min-width="220" show-overflow-tooltip />
        <el-table-column label="媒体类型" width="90">
          <template #default="{ row }">
            <el-tag size="small">{{ row.media_type }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="模式" width="200">
          <template #default="{ row }">
            <div class="mode-cell">
              <el-tag size="small" type="info">{{ row.scrape_mode }}</el-tag>
              <el-tag size="small" type="warning">{{ row.rename_mode }}</el-tag>
            </div>
          </template>
        </el-table-column>
        <el-table-column prop="max_threads" label="并发" width="70" />
        <el-table-column label="定时" width="170">
          <template #default="{ row }">
            <div class="cron-cell">
              <span class="cron-text">{{ row.cron || '-' }}</span>
              <el-switch
                :model-value="row.cron_enabled"
                :disabled="!row.cron || actionLoadingMap[row.path_id]"
                @change="toggleCron(row, $event)"
              />
            </div>
          </template>
        </el-table-column>
        <el-table-column label="状态" width="120">
          <template #default="{ row }">
            <el-tag :type="statusTagType(row.status)" size="small">{{ row.status }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="更新时间" width="180">
          <template #default="{ row }">{{ formatTime(row.updated_at) }}</template>
        </el-table-column>
        <el-table-column label="操作" width="300" fixed="right">
          <template #default="{ row }">
            <el-space>
              <el-button
                type="primary"
                link
                :icon="VideoPlay"
                :loading="actionLoadingMap[row.path_id]"
                @click="startPath(row)"
              >
                启动
              </el-button>
              <el-button
                type="warning"
                link
                :icon="VideoPause"
                :loading="actionLoadingMap[row.path_id]"
                @click="stopPath(row)"
              >
                停止
              </el-button>
              <el-button type="info" link :icon="Edit" @click="openEditDialog(row)">编辑</el-button>
              <el-button type="danger" link :icon="Delete" @click="deletePath(row)">删除</el-button>
            </el-space>
          </template>
        </el-table-column>
      </el-table>

      <div class="pagination">
        <el-pagination
          background
          layout="total, prev, pager, next, sizes"
          :total="total"
          v-model:current-page="pagination.page"
          v-model:page-size="pagination.size"
          @current-change="loadPaths"
          @size-change="loadPaths"
        />
      </div>
    </el-card>

    <el-dialog
      v-model="dialog.visible"
      :title="dialog.mode === 'create' ? '新增刮削目录' : '编辑刮削目录'"
      width="760px"
      destroy-on-close
    >
      <el-form ref="formRef" :model="form" :rules="rules" label-width="150px">
        <el-form-item label="源目录" prop="source_path">
          <el-input v-model="form.source_path" placeholder="例如: D:/media/raw" />
        </el-form-item>
        <el-form-item label="目标目录" prop="dest_path">
          <el-input v-model="form.dest_path" placeholder="例如: D:/media/library" />
        </el-form-item>
        <el-form-item label="媒体类型" prop="media_type">
          <el-select v-model="form.media_type" style="width: 220px">
            <el-option label="auto" value="auto" />
            <el-option label="movie" value="movie" />
            <el-option label="tv" value="tv" />
          </el-select>
        </el-form-item>
        <el-form-item label="刮削模式" prop="scrape_mode">
          <el-select v-model="form.scrape_mode" style="width: 260px">
            <el-option label="only_scrape" value="only_scrape" />
            <el-option label="scrape_and_rename" value="scrape_and_rename" />
            <el-option label="only_rename" value="only_rename" />
          </el-select>
        </el-form-item>
        <el-form-item label="整理方式" prop="rename_mode">
          <el-select v-model="form.rename_mode" style="width: 260px">
            <el-option label="move" value="move" />
            <el-option label="copy" value="copy" />
            <el-option label="hardlink" value="hardlink" />
            <el-option label="softlink" value="softlink" />
          </el-select>
        </el-form-item>
        <el-form-item label="并发线程" prop="max_threads">
          <el-input-number v-model="form.max_threads" :min="1" :max="32" />
        </el-form-item>
        <el-form-item label="Cron 表达式" prop="cron">
          <el-input v-model="form.cron" placeholder="可空。支持 5 或 6 段 cron" />
        </el-form-item>
        <el-form-item label="启用目录">
          <el-switch v-model="form.enabled" />
        </el-form-item>
        <el-form-item label="启用二级分类">
          <el-switch v-model="form.enable_secondary_category" />
        </el-form-item>
      </el-form>

      <template #footer>
        <el-button @click="dialog.visible = false">取消</el-button>
        <el-button type="primary" :loading="submitting" @click="submitForm">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { reactive, ref } from 'vue'
import { ElMessage, ElMessageBox, type FormInstance, type FormRules } from 'element-plus'
import { Clock, Delete, Edit, Plus, RefreshRight, VideoPause, VideoPlay } from '@element-plus/icons-vue'
import { scrapeApi, type ScrapePath, type ScrapePathCreatePayload } from '@/api/scrape'

type DialogMode = 'create' | 'edit'

interface Filters {
  keyword: string
  status: string
  enabled: boolean | undefined
}

interface DialogState {
  visible: boolean
  mode: DialogMode
  editingId: string
}

const loading = ref(false)
const submitting = ref(false)
const paths = ref<ScrapePath[]>([])
const total = ref(0)
const formRef = ref<FormInstance>()
const actionLoadingMap = reactive<Record<string, boolean>>({})

const filters = reactive<Filters>({
  keyword: '',
  status: '',
  enabled: undefined
})

const pagination = reactive({
  page: 1,
  size: 20
})

const dialog = reactive<DialogState>({
  visible: false,
  mode: 'create',
  editingId: ''
})

const form = reactive<ScrapePathCreatePayload>({
  source_path: '',
  dest_path: '',
  media_type: 'auto',
  scrape_mode: 'scrape_and_rename',
  rename_mode: 'move',
  max_threads: 2,
  cron: '',
  enabled: true,
  enable_secondary_category: true
})

const cronValidator = (_rule: unknown, value: string, callback: (error?: Error) => void): void => {
  if (!value) {
    callback()
    return
  }
  const parts = value.trim().split(/\s+/)
  if (parts.length !== 5 && parts.length !== 6) {
    callback(new Error('cron 需为 5 或 6 段'))
    return
  }
  callback()
}

const rules = reactive<FormRules<typeof form>>({
  source_path: [{ required: true, message: '请输入源目录', trigger: 'blur' }],
  dest_path: [{ required: true, message: '请输入目标目录', trigger: 'blur' }],
  cron: [{ validator: cronValidator, trigger: 'blur' }]
})

const statusTagType = (status: string): '' | 'success' | 'warning' | 'info' | 'danger' => {
  if (status === 'running') return 'success'
  if (status === 'stopped') return 'warning'
  if (status === 'idle') return 'info'
  return ''
}

const formatTime = (time?: string | null): string => {
  if (!time) return '-'
  const value = new Date(time)
  if (Number.isNaN(value.getTime())) return String(time)
  return `${value.getFullYear()}-${String(value.getMonth() + 1).padStart(2, '0')}-${String(
    value.getDate()
  ).padStart(2, '0')} ${String(value.getHours()).padStart(2, '0')}:${String(value.getMinutes()).padStart(2, '0')}`
}

const normalizeForm = (row?: ScrapePath): void => {
  form.source_path = row?.source_path ?? ''
  form.dest_path = row?.dest_path ?? ''
  form.media_type = row?.media_type ?? 'auto'
  form.scrape_mode = row?.scrape_mode ?? 'scrape_and_rename'
  form.rename_mode = row?.rename_mode ?? 'move'
  form.max_threads = row?.max_threads ?? 2
  form.cron = row?.cron ?? ''
  form.enabled = row?.enabled ?? true
  form.enable_secondary_category = row?.enable_secondary_category ?? true
}

const loadPaths = async (): Promise<void> => {
  loading.value = true
  try {
    const data = await scrapeApi.listPaths({
      keyword: filters.keyword || undefined,
      status: filters.status || undefined,
      enabled: typeof filters.enabled === 'boolean' ? filters.enabled : undefined,
      page: pagination.page,
      size: pagination.size
    })
    paths.value = data.items
    total.value = data.total
  } catch (error: any) {
    ElMessage.error(error?.response?.data?.detail || '加载刮削目录失败')
  } finally {
    loading.value = false
  }
}

const resetFilters = (): void => {
  filters.keyword = ''
  filters.status = ''
  filters.enabled = undefined
  pagination.page = 1
  void loadPaths()
}

const openCreateDialog = (): void => {
  dialog.visible = true
  dialog.mode = 'create'
  dialog.editingId = ''
  normalizeForm()
}

const openEditDialog = (row: ScrapePath): void => {
  dialog.visible = true
  dialog.mode = 'edit'
  dialog.editingId = row.path_id
  normalizeForm(row)
}

const submitForm = async (): Promise<void> => {
  if (!formRef.value) return
  try {
    await formRef.value.validate()
  } catch {
    return
  }

  submitting.value = true
  try {
    const payload = {
      ...form,
      cron: form.cron?.trim() ? form.cron.trim() : null
    }
    if (dialog.mode === 'create') {
      await scrapeApi.createPath(payload)
      ElMessage.success('刮削目录已创建')
    } else {
      await scrapeApi.updatePath(dialog.editingId, payload)
      ElMessage.success('刮削目录已更新')
    }
    dialog.visible = false
    await loadPaths()
  } catch (error: any) {
    ElMessage.error(error?.response?.data?.detail || '保存失败')
  } finally {
    submitting.value = false
  }
}

const withRowAction = async (row: ScrapePath, action: () => Promise<void>): Promise<void> => {
  actionLoadingMap[row.path_id] = true
  try {
    await action()
  } finally {
    actionLoadingMap[row.path_id] = false
  }
}

const startPath = async (row: ScrapePath): Promise<void> => {
  await withRowAction(row, async () => {
    try {
      const result = await scrapeApi.startPath(row.path_id)
      if (result.already_running) {
        ElMessage.info('目录任务已在运行，未重复启动')
      } else {
        ElMessage.success('目录任务已启动')
      }
      await loadPaths()
    } catch (error: any) {
      ElMessage.error(error?.response?.data?.detail || '启动失败')
    }
  })
}

const stopPath = async (row: ScrapePath): Promise<void> => {
  await withRowAction(row, async () => {
    try {
      await scrapeApi.stopPath(row.path_id)
      ElMessage.success('目录任务已停止')
      await loadPaths()
    } catch (error: any) {
      ElMessage.error(error?.response?.data?.detail || '停止失败')
    }
  })
}

const toggleCron = async (row: ScrapePath, enabled: boolean): Promise<void> => {
  await withRowAction(row, async () => {
    try {
      await scrapeApi.toggleCron(row.path_id, enabled)
      ElMessage.success(enabled ? '定时任务已开启' : '定时任务已关闭')
      await loadPaths()
    } catch (error: any) {
      ElMessage.error(error?.response?.data?.detail || '定时切换失败')
      await loadPaths()
    }
  })
}

const deletePath = async (row: ScrapePath): Promise<void> => {
  try {
    await ElMessageBox.confirm(`确认删除目录配置 ${row.path_id} 吗？`, '删除确认', {
      type: 'warning',
      confirmButtonText: '删除',
      cancelButtonText: '取消'
    })
  } catch {
    return
  }

  await withRowAction(row, async () => {
    try {
      await scrapeApi.deletePath(row.path_id)
      ElMessage.success('目录已删除')
      await loadPaths()
    } catch (error: any) {
      ElMessage.error(error?.response?.data?.detail || '删除失败')
    }
  })
}

void loadPaths()
</script>

<style scoped>
.scrape-pathes-page {
  padding: 8px;
}

.page-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 16px;
}

.page-header h2 {
  margin: 0;
  font-size: 24px;
  font-weight: 600;
}

.header-actions {
  display: flex;
  gap: 8px;
}

.card {
  border: 1px solid var(--border-color);
}

.filters {
  margin-bottom: 12px;
}

.mode-cell {
  display: flex;
  gap: 4px;
  flex-wrap: wrap;
}

.cron-cell {
  display: flex;
  align-items: center;
  gap: 8px;
}

.cron-text {
  max-width: 100px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.pagination {
  margin-top: 16px;
  display: flex;
  justify-content: flex-end;
}
</style>


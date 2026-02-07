<template>
  <div class="scrape-records-page">
    <div class="page-header">
      <h2>刮削记录</h2>
      <div class="header-actions">
        <el-button :icon="RefreshRight" @click="loadRecords">刷新</el-button>
      </div>
    </div>

    <el-card shadow="never" class="card">
      <el-form :inline="true" class="filters">
        <el-form-item label="关键词">
          <el-input
            v-model="filters.keyword"
            placeholder="文件名/标题/错误"
            clearable
            @keyup.enter="loadRecords"
          />
        </el-form-item>
        <el-form-item label="状态">
          <el-select v-model="filters.status" clearable placeholder="全部" style="width: 170px">
            <el-option label="pending" value="pending" />
            <el-option label="scanned" value="scanned" />
            <el-option label="scraping" value="scraping" />
            <el-option label="scraped" value="scraped" />
            <el-option label="renaming" value="renaming" />
            <el-option label="renamed" value="renamed" />
            <el-option label="scrape_failed" value="scrape_failed" />
            <el-option label="rename_failed" value="rename_failed" />
          </el-select>
        </el-form-item>
        <el-form-item>
          <el-button type="primary" @click="loadRecords">查询</el-button>
          <el-button @click="resetFilters">重置</el-button>
        </el-form-item>
      </el-form>

      <div class="toolbar">
        <el-button type="primary" :disabled="selectedIds.length === 0" @click="reScrapeSelected">
          重新刮削 ({{ selectedIds.length }})
        </el-button>
        <el-button type="warning" @click="clearFailedRecords">清理失败</el-button>
        <el-button type="danger" @click="truncateAllRecords">清空记录</el-button>
      </div>

      <el-table
        v-loading="loading"
        :data="records"
        stripe
        border
        @selection-change="handleSelectionChange"
      >
        <el-table-column type="selection" width="45" />
        <el-table-column prop="source_file" label="源文件" min-width="220" show-overflow-tooltip />
        <el-table-column prop="target_file" label="目标文件" min-width="220" show-overflow-tooltip />
        <el-table-column prop="title" label="识别标题" min-width="150" show-overflow-tooltip />
        <el-table-column prop="status" label="状态" width="130">
          <template #default="{ row }">
            <el-tag :type="statusTagType(row.status)" size="small">{{ row.status }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="error_code" label="错误码" width="130" />
        <el-table-column label="更新时间" width="180">
          <template #default="{ row }">{{ formatTime(row.updated_at || row.created_at) }}</template>
        </el-table-column>
        <el-table-column label="操作" width="110" fixed="right">
          <template #default="{ row }">
            <el-button type="primary" link @click="openDetail(row.record_id)">详情</el-button>
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
          @current-change="loadRecords"
          @size-change="loadRecords"
        />
      </div>
    </el-card>

    <el-drawer v-model="detail.visible" title="记录详情" size="42%" destroy-on-close>
      <div v-if="detail.loading" class="detail-loading">
        <el-skeleton :rows="8" animated />
      </div>
      <div v-else-if="detail.record">
        <el-descriptions :column="1" border>
          <el-descriptions-item label="Record ID">{{ detail.record.record_id }}</el-descriptions-item>
          <el-descriptions-item label="状态">{{ detail.record.status }}</el-descriptions-item>
          <el-descriptions-item label="源文件">{{ detail.record.source_file }}</el-descriptions-item>
          <el-descriptions-item label="目标文件">{{ detail.record.target_file || '-' }}</el-descriptions-item>
          <el-descriptions-item label="识别标题">{{ detail.record.title || '-' }}</el-descriptions-item>
          <el-descriptions-item label="TMDB ID">{{ detail.record.tmdb_id || '-' }}</el-descriptions-item>
          <el-descriptions-item label="错误码">{{ detail.record.error_code || '-' }}</el-descriptions-item>
          <el-descriptions-item label="错误信息">
            <div class="error-message">{{ detail.record.error_message || '-' }}</div>
          </el-descriptions-item>
          <el-descriptions-item label="处理建议">
            <el-tag type="info" effect="plain">{{ errorSuggestion(detail.record.error_code) }}</el-tag>
          </el-descriptions-item>
          <el-descriptions-item label="识别信息">
            <pre class="recognition-json">{{ formatRecognition(detail.record.recognition_result) }}</pre>
          </el-descriptions-item>
        </el-descriptions>
      </div>
      <el-empty v-else description="暂无详情" />
    </el-drawer>
  </div>
</template>

<script setup lang="ts">
import { reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { RefreshRight } from '@element-plus/icons-vue'
import { scrapeApi, type ScrapeRecord } from '@/api/scrape'

const loading = ref(false)
const records = ref<ScrapeRecord[]>([])
const total = ref(0)
const selectedIds = ref<string[]>([])

const filters = reactive({
  keyword: '',
  status: ''
})

const pagination = reactive({
  page: 1,
  size: 20
})

const detail = reactive<{
  visible: boolean
  loading: boolean
  record: ScrapeRecord | null
}>({
  visible: false,
  loading: false,
  record: null
})

const loadRecords = async (): Promise<void> => {
  loading.value = true
  try {
    const data = await scrapeApi.listRecords({
      keyword: filters.keyword || undefined,
      status: filters.status || undefined,
      page: pagination.page,
      size: pagination.size
    })
    records.value = data.items || []
    total.value = data.total || 0
  } catch (error: any) {
    ElMessage.error(error?.response?.data?.detail || '加载记录失败')
    records.value = []
    total.value = 0
  } finally {
    loading.value = false
  }
}

const resetFilters = (): void => {
  filters.keyword = ''
  filters.status = ''
  pagination.page = 1
  void loadRecords()
}

const statusTagType = (status: string): '' | 'success' | 'warning' | 'danger' | 'info' => {
  if (status === 'renamed') return 'success'
  if (status === 'scrape_failed' || status === 'rename_failed') return 'danger'
  if (status === 'pending' || status === 'scanned') return 'info'
  return 'warning'
}

const formatTime = (time: string): string => {
  const value = new Date(time)
  if (Number.isNaN(value.getTime())) return time
  return `${value.getFullYear()}-${String(value.getMonth() + 1).padStart(2, '0')}-${String(
    value.getDate()
  ).padStart(2, '0')} ${String(value.getHours()).padStart(2, '0')}:${String(value.getMinutes()).padStart(2, '0')}`
}

const handleSelectionChange = (selection: ScrapeRecord[]): void => {
  selectedIds.value = selection.map((item) => item.record_id)
}

const reScrapeSelected = async (): Promise<void> => {
  if (selectedIds.value.length === 0) return
  try {
    await ElMessageBox.confirm(`确认重新刮削已选 ${selectedIds.value.length} 条记录吗？`, '重新刮削', {
      type: 'warning',
      confirmButtonText: '确认',
      cancelButtonText: '取消'
    })
  } catch {
    return
  }

  try {
    const result = await scrapeApi.reScrape(selectedIds.value)
    ElMessage.success(`已提交 ${result.updated} 条记录重新处理`)
    selectedIds.value = []
    await loadRecords()
  } catch (error: any) {
    ElMessage.error(error?.response?.data?.detail || '重新刮削失败')
  }
}

const clearFailedRecords = async (): Promise<void> => {
  try {
    await ElMessageBox.confirm('确认清理所有失败记录吗？', '清理失败', {
      type: 'warning',
      confirmButtonText: '确认',
      cancelButtonText: '取消'
    })
  } catch {
    return
  }

  try {
    const result = await scrapeApi.clearFailed()
    ElMessage.success(`已清理 ${result.cleared} 条失败记录`)
    await loadRecords()
  } catch (error: any) {
    ElMessage.error(error?.response?.data?.detail || '清理失败记录失败')
  }
}

const truncateAllRecords = async (): Promise<void> => {
  try {
    await ElMessageBox.confirm('确认清空全部刮削记录吗？该操作不可恢复。', '清空记录', {
      type: 'warning',
      confirmButtonText: '确认清空',
      cancelButtonText: '取消'
    })
  } catch {
    return
  }

  try {
    const result = await scrapeApi.truncateAll()
    ElMessage.success(`已清空 ${result.truncated} 条记录`)
    selectedIds.value = []
    await loadRecords()
  } catch (error: any) {
    ElMessage.error(error?.response?.data?.detail || '清空记录失败')
  }
}

const openDetail = async (recordId: string): Promise<void> => {
  detail.visible = true
  detail.loading = true
  detail.record = null
  try {
    detail.record = await scrapeApi.getRecord(recordId)
  } catch (error: any) {
    ElMessage.error(error?.response?.data?.detail || '加载详情失败')
  } finally {
    detail.loading = false
  }
}

const formatRecognition = (value: Record<string, unknown> | null): string => {
  if (!value) return '-'
  try {
    return JSON.stringify(value, null, 2)
  } catch {
    return '-'
  }
}

const errorSuggestion = (errorCode: string | null): string => {
  if (!errorCode) return '无错误，无需处理'
  if (errorCode.includes('TMDB') || errorCode.includes('SCRAPE')) return '检查 TMDB 参数或文件命名，再重试'
  if (errorCode.includes('RENAME')) return '检查目标目录权限与重名冲突'
  if (errorCode.includes('SOURCE')) return '确认源文件仍存在并可访问'
  return '查看错误详情后重试，必要时手工修复'
}

void loadRecords()
</script>

<style scoped>
.scrape-records-page {
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

.card {
  border: 1px solid var(--border-color);
}

.filters {
  margin-bottom: 12px;
}

.toolbar {
  display: flex;
  gap: 8px;
  margin-bottom: 12px;
}

.pagination {
  margin-top: 16px;
  display: flex;
  justify-content: flex-end;
}

.detail-loading {
  padding: 16px;
}

.error-message {
  white-space: pre-wrap;
  word-break: break-word;
}

.recognition-json {
  margin: 0;
  white-space: pre-wrap;
  word-break: break-word;
  font-size: 12px;
  line-height: 1.5;
}
</style>


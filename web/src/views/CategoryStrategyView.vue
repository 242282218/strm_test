<template>
  <div class="category-strategy-page">
    <div class="page-header">
      <h2>二级分类策略</h2>
      <div class="header-actions">
        <el-button :icon="RefreshRight" @click="loadStrategy">刷新</el-button>
        <el-button type="primary" :loading="saving" @click="saveStrategy">保存策略</el-button>
      </div>
    </div>

    <el-row :gutter="16">
      <el-col :span="14">
        <el-card shadow="never" class="card">
          <el-form label-width="140px" v-loading="loading">
            <el-form-item label="启用二级分类">
              <el-switch v-model="form.enabled" />
            </el-form-item>
            <el-form-item label="动漫目录名">
              <el-input v-model="form.folder_names.anime" />
            </el-form-item>
            <el-form-item label="电影目录名">
              <el-input v-model="form.folder_names.movie" />
            </el-form-item>
            <el-form-item label="电视剧目录名">
              <el-input v-model="form.folder_names.tv" />
            </el-form-item>
            <el-form-item label="动漫关键词">
              <el-input
                v-model="keywordText"
                type="textarea"
                :rows="5"
                placeholder="使用逗号分隔，例如：anime,animation,动漫,番剧"
              />
            </el-form-item>
          </el-form>
        </el-card>
      </el-col>

      <el-col :span="10">
        <el-card shadow="never" class="card">
          <template #header>分类预览</template>
          <el-form label-width="100px">
            <el-form-item label="样本文件名">
              <el-input v-model="preview.file_name" placeholder="示例：Naruto.S01E01.1080p.mkv" />
            </el-form-item>
            <el-form-item label="媒体类型">
              <el-select v-model="preview.media_type" style="width: 100%">
                <el-option label="auto" value="auto" />
                <el-option label="movie" value="movie" />
                <el-option label="tv" value="tv" />
              </el-select>
            </el-form-item>
            <el-form-item>
              <el-button type="primary" :loading="preview.loading" @click="runPreview">执行预览</el-button>
            </el-form-item>
          </el-form>

          <el-divider />
          <div v-if="preview.result" class="preview-result">
            <el-tag type="success">{{ preview.result.category_key }}</el-tag>
            <span> -> </span>
            <el-tag>{{ preview.result.category_folder }}</el-tag>
          </div>
          <el-empty v-else description="请输入样本后预览" :image-size="84" />
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<script setup lang="ts">
import { reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { RefreshRight } from '@element-plus/icons-vue'
import { categoryStrategyApi, type CategoryStrategy, type CategoryPreviewResponse } from '@/api/categoryStrategy'

const loading = ref(false)
const saving = ref(false)
const keywordText = ref('')

const form = reactive<CategoryStrategy>({
  enabled: true,
  anime_keywords: ['anime', 'animation', '动漫', '番剧'],
  folder_names: {
    anime: '动漫文件夹',
    movie: '电影',
    tv: '电视剧'
  }
})

const preview = reactive<{
  file_name: string
  media_type: 'auto' | 'movie' | 'tv'
  loading: boolean
  result: CategoryPreviewResponse | null
}>({
  file_name: '',
  media_type: 'auto',
  loading: false,
  result: null
})

const parseKeywords = (): string[] => {
  return keywordText.value
    .split(/[,，\n]/)
    .map((item) => item.trim())
    .filter((item) => item.length > 0)
}

const loadStrategy = async (): Promise<void> => {
  loading.value = true
  try {
    const data = await categoryStrategyApi.get()
    form.enabled = data.enabled
    form.folder_names.anime = data.folder_names.anime
    form.folder_names.movie = data.folder_names.movie
    form.folder_names.tv = data.folder_names.tv
    form.anime_keywords = data.anime_keywords
    keywordText.value = data.anime_keywords.join(', ')
  } catch (error: any) {
    ElMessage.error(error?.response?.data?.detail || '加载策略失败')
  } finally {
    loading.value = false
  }
}

const saveStrategy = async (): Promise<void> => {
  saving.value = true
  try {
    const payload: CategoryStrategy = {
      enabled: form.enabled,
      anime_keywords: parseKeywords(),
      folder_names: {
        anime: form.folder_names.anime.trim() || '动漫文件夹',
        movie: form.folder_names.movie.trim() || '电影',
        tv: form.folder_names.tv.trim() || '电视剧'
      }
    }
    const updated = await categoryStrategyApi.update(payload)
    form.enabled = updated.enabled
    form.anime_keywords = updated.anime_keywords
    form.folder_names = updated.folder_names
    keywordText.value = updated.anime_keywords.join(', ')
    ElMessage.success('分类策略已保存')
  } catch (error: any) {
    ElMessage.error(error?.response?.data?.detail || '保存策略失败')
  } finally {
    saving.value = false
  }
}

const runPreview = async (): Promise<void> => {
  if (!preview.file_name.trim()) {
    ElMessage.warning('请输入样本文件名')
    return
  }
  preview.loading = true
  preview.result = null
  try {
    preview.result = await categoryStrategyApi.preview({
      file_name: preview.file_name.trim(),
      media_type: preview.media_type
    })
  } catch (error: any) {
    ElMessage.error(error?.response?.data?.detail || '预览失败')
  } finally {
    preview.loading = false
  }
}

void loadStrategy()
</script>

<style scoped>
.category-strategy-page {
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
  min-height: 420px;
}

.preview-result {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 14px;
}
</style>


<template>
  <div class="workbench-page category-strategy-page">
    <section class="workbench-hero page-surface" data-testid="category-strategy-hero">
      <div class="workbench-main">
        <div class="workbench-toolbar">
          <div class="workbench-copy">
            <span class="workbench-chip">Category Routing</span>
            <h2 class="workbench-title">二级分类策略、目录映射与样本预判集中收口</h2>
            <p class="workbench-description">
              先定义二级分类命名，再用样本文件即时预判落点，保存前就能看清规则是否会把媒体分流到正确目录。
            </p>
          </div>

          <div class="workbench-actions">
            <el-button :icon="RefreshRight" @click="loadStrategy">刷新</el-button>
            <el-button
              type="primary"
              :loading="saving"
              data-testid="category-strategy-save-button"
              @click="saveStrategy"
            >
              保存策略
            </el-button>
          </div>
        </div>

        <div class="workbench-metrics">
          <article
            v-for="metric in heroMetrics"
            :key="metric.label"
            class="workbench-metric"
          >
            <span class="workbench-metric-label">{{ metric.label }}</span>
            <strong class="workbench-metric-value">{{ metric.value }}</strong>
            <p class="workbench-metric-detail">{{ metric.detail }}</p>
          </article>
        </div>
      </div>

      <div class="workbench-side">
        <article class="workbench-side-card">
          <div class="workbench-side-head">
            <div class="workbench-side-heading">
              <span class="workbench-side-kicker">Current Mapping</span>
              <h3 class="workbench-side-title">当前目录映射</h3>
            </div>
          </div>

          <div class="mapping-grid">
            <article
              v-for="mapping in directoryMappings"
              :key="mapping.label"
              class="mapping-card"
            >
              <span class="mapping-label">{{ mapping.label }}</span>
              <strong class="mapping-value">{{ mapping.value }}</strong>
              <p class="mapping-detail">{{ mapping.detail }}</p>
            </article>
          </div>
        </article>

        <article class="workbench-side-card" data-testid="category-strategy-preview-focus">
          <div class="workbench-side-head">
            <div class="workbench-side-heading">
              <span class="workbench-side-kicker">Preview Focus</span>
              <h3 class="workbench-side-title">{{ preview.result ? '最近一次预判' : '等待样本验证' }}</h3>
            </div>
          </div>

          <div v-if="preview.result" class="preview-focus-result">
            <el-tag type="success" effect="dark">{{ preview.result.category_key }}</el-tag>
            <span class="preview-arrow">→</span>
            <el-tag>{{ preview.result.category_folder }}</el-tag>
          </div>
          <p class="workbench-side-copy">{{ previewSummary }}</p>
        </article>
      </div>
    </section>

    <div class="category-strategy-layout">
      <section class="workbench-section page-surface" data-testid="category-strategy-editor">
        <div class="workbench-section-head">
          <div class="workbench-section-heading">
            <span class="workbench-section-kicker">Rule Editor</span>
            <h3 class="workbench-section-title">分类规则编辑区</h3>
            <p class="workbench-section-description">
              这里只维护二级分类是否启用、目录命名与动漫关键词列表，不引入额外抽象，保证规则来源单一。
            </p>
          </div>

          <div class="strategy-state" :class="{ 'is-enabled': form.enabled }">
            <span class="strategy-state-label">当前状态</span>
            <strong>{{ form.enabled ? '已启用' : '已停用' }}</strong>
          </div>
        </div>

        <el-form label-width="136px" v-loading="loading" class="strategy-form">
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
              :rows="6"
              placeholder="使用逗号或换行分隔，例如：anime, animation, 动漫, 番剧"
            />
            <p class="field-tip">只有命中这些关键词的样本会落到动漫目录，其它样本沿用电影/电视剧分流。</p>
          </el-form-item>
        </el-form>
      </section>

      <section class="workbench-section page-surface" data-testid="category-strategy-preview">
        <div class="workbench-section-head">
          <div class="workbench-section-heading">
            <span class="workbench-section-kicker">Sample Check</span>
            <h3 class="workbench-section-title">样本预判工作台</h3>
            <p class="workbench-section-description">
              保存前先用真实文件名验证命中结果，确认目录落点和媒体类型推断是否符合预期。
            </p>
          </div>
        </div>

        <el-form label-width="96px" class="preview-form">
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
            <el-button
              type="primary"
              :loading="preview.loading"
              data-testid="category-strategy-preview-button"
              @click="runPreview"
            >
              执行预览
            </el-button>
          </el-form-item>
        </el-form>

        <div v-if="preview.result" class="preview-result">
          <span class="preview-result-label">命中结果</span>
          <div class="preview-result-tags">
            <el-tag type="success" effect="dark">{{ preview.result.category_key }}</el-tag>
            <span class="preview-arrow">→</span>
            <el-tag>{{ preview.result.category_folder }}</el-tag>
          </div>
        </div>
        <el-empty v-else description="请输入样本后预览" :image-size="84" />
      </section>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { RefreshRight } from '@/components/icons'
import {
  categoryStrategyApi,
  type CategoryStrategy,
  type CategoryPreviewResponse
} from '@/features/category-strategy/api/categoryStrategy'
import { showError, showSuccess } from '@/utils/error'

type HeroMetric = {
  label: string
  value: string
  detail: string
}

type DirectoryMapping = {
  label: string
  value: string
  detail: string
}

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

const keywordList = computed(() => parseKeywords())

const heroMetrics = computed<HeroMetric[]>(() => {
  return [
    {
      label: '策略状态',
      value: form.enabled ? '已启用' : '已停用',
      detail: form.enabled ? '命中规则后会自动做二级目录分流。' : '当前所有样本都会绕过二级分类。'
    },
    {
      label: '动漫关键词',
      value: `${keywordList.value.length} 个`,
      detail: keywordList.value.length > 0 ? `首个关键词：${keywordList.value[0]}` : '尚未定义关键词。'
    },
    {
      label: '目录映射',
      value: '3 组',
      detail: `${form.folder_names.anime} / ${form.folder_names.movie} / ${form.folder_names.tv}`
    },
    {
      label: '预览状态',
      value: preview.result ? '已验证' : '待验证',
      detail: preview.result
        ? `${preview.result.category_key} -> ${preview.result.category_folder}`
        : '输入样本文件名后可即时预判。'
    }
  ]
})

const directoryMappings = computed<DirectoryMapping[]>(() => {
  return [
    {
      label: '动漫',
      value: form.folder_names.anime.trim() || '动漫文件夹',
      detail: keywordList.value.length > 0 ? `${keywordList.value.length} 个关键词参与命中` : '等待补充动漫关键词'
    },
    {
      label: '电影',
      value: form.folder_names.movie.trim() || '电影',
      detail: '未命中动漫关键词且识别为电影时使用'
    },
    {
      label: '剧集',
      value: form.folder_names.tv.trim() || '电视剧',
      detail: '未命中动漫关键词且识别为剧集时使用'
    }
  ]
})

const previewSummary = computed(() => {
  if (preview.result) {
    return `当前样本会落到「${preview.result.category_folder}」目录，可在保存前继续改关键词或目录名验证边界。`
  }

  return '输入样本文件名后，这里会展示命中的分类键与实际目录落点。'
})

const loadStrategy = async (): Promise<void> => {
  loading.value = true
  try {
    const data = await categoryStrategyApi.get()
    form.enabled = data.enabled ?? true
    form.folder_names.anime = data.folder_names?.anime ?? '动漫文件夹'
    form.folder_names.movie = data.folder_names?.movie ?? '电影'
    form.folder_names.tv = data.folder_names?.tv ?? '电视剧'
    form.anime_keywords = data.anime_keywords || []
    keywordText.value = (data.anime_keywords || []).join(', ')
  } catch (error: unknown) {
    showError(error, '加载策略失败')
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
    form.enabled = updated.enabled ?? true
    form.anime_keywords = updated.anime_keywords || []
    form.folder_names = updated.folder_names || {
      anime: '动漫文件夹',
      movie: '电影',
      tv: '电视剧'
    }
    keywordText.value = (updated.anime_keywords || []).join(', ')
    showSuccess('分类策略已保存')
  } catch (error: unknown) {
    showError(error, '保存策略失败')
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
  } catch (error: unknown) {
    showError(error, '预览失败')
  } finally {
    preview.loading = false
  }
}

onMounted(() => {
  void loadStrategy()
})
</script>

<style scoped>
.category-strategy-layout {
  display: grid;
  grid-template-columns: minmax(0, 1.35fr) minmax(320px, 0.92fr);
  gap: var(--page-section-gap);
}

.mapping-grid {
  display: grid;
  gap: 12px;
}

.mapping-card {
  padding: 16px 18px;
  border-radius: var(--radius-md);
  background: rgba(79, 141, 246, 0.08);
  border: 1px solid rgba(79, 141, 246, 0.16);
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.mapping-label,
.preview-result-label,
.strategy-state-label,
.field-tip {
  color: var(--text-tertiary);
  font-size: 12px;
}

.mapping-value {
  font-size: 1rem;
  font-weight: var(--font-semibold);
}

.mapping-detail,
.preview-arrow {
  color: var(--text-secondary);
}

.strategy-state {
  min-width: 160px;
  padding: 16px 18px;
  border-radius: var(--radius-lg);
  background: rgba(231, 168, 61, 0.12);
  border: 1px solid rgba(231, 168, 61, 0.18);
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.strategy-state.is-enabled {
  background: rgba(51, 176, 122, 0.12);
  border-color: rgba(51, 176, 122, 0.18);
}

.strategy-state strong {
  font-size: 1rem;
  font-weight: var(--font-semibold);
}

.strategy-form,
.preview-form {
  margin-top: 20px;
}

.field-tip {
  margin: 8px 0 0;
  line-height: 1.55;
}

.preview-result,
.preview-focus-result {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

.preview-result {
  margin-top: 20px;
  padding: 16px 18px;
  border-radius: var(--radius-lg);
  background: rgba(51, 176, 122, 0.08);
  border: 1px solid rgba(51, 176, 122, 0.16);
  flex-direction: column;
  align-items: flex-start;
}

@media (max-width: 1080px) {
  .category-strategy-layout {
    grid-template-columns: 1fr;
  }
}
</style>

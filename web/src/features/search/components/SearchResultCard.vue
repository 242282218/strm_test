<template>
  <article
    class="result-card page-surface"
    :style="{ animationDelay: `${animationDelay}s` }"
  >
    <div class="card-header">
      <div class="card-badges">
        <span class="source-badge" :class="item.source">
          {{ getSourceLabel(item.source) }}
        </span>
        <span class="score-chip" :class="getScoreClass(item.score)">
          质量 {{ (item.score || 0).toFixed(2) }}
        </span>
      </div>
    </div>

    <div class="card-body">
      <h3 class="result-title" :title="item.title">{{ item.title }}</h3>
      <p class="result-content">{{ item.content }}</p>

      <div class="result-meta">
        <span v-if="item.channel" class="meta-item">
          <el-icon><Collection /></el-icon>
          {{ item.channel }}
        </span>
        <span v-if="item.pub_date" class="meta-item">
          <el-icon><Calendar /></el-icon>
          {{ formatDate(item.pub_date) }}
        </span>
      </div>
    </div>

    <div class="card-footer">
      <div class="cloud-links">
        <el-tooltip
          v-for="link in item.cloud_links.slice(0, 2)"
          :key="link.url"
          :content="link.password ? `密码: ${link.password}` : '点击访问'"
          placement="top"
        >
          <el-button
            type="primary"
            size="small"
            class="link-btn"
            @click="$emit('open-link', link)"
          >
            <el-icon><Link /></el-icon>
            {{ getCloudTypeLabel(link.type) }}
          </el-button>
        </el-tooltip>
        <el-dropdown v-if="item.cloud_links.length > 2" trigger="click">
          <el-button size="small">
            +{{ item.cloud_links.length - 2 }}
          </el-button>
          <template #dropdown>
            <el-dropdown-menu>
              <el-dropdown-item
                v-for="link in item.cloud_links.slice(2)"
                :key="link.url"
                @click="$emit('open-link', link)"
              >
                {{ getCloudTypeLabel(link.type) }}
                <el-tag v-if="link.password" size="small" type="warning">
                  密码: {{ link.password }}
                </el-tag>
              </el-dropdown-item>
            </el-dropdown-menu>
          </template>
        </el-dropdown>
      </div>

      <el-button
        type="success"
        size="small"
        class="save-btn"
        @click="$emit('save', item)"
      >
        <el-icon><Download /></el-icon>
        转存
      </el-button>
    </div>
  </article>
</template>

<script setup lang="ts">
import { Collection, Calendar, Link, Download } from '@/components/icons'
import type { CloudLink, SearchResult } from '@/api/search'

defineProps<{
  item: SearchResult
  animationDelay: number
}>()

defineEmits<{
  'open-link': [link: CloudLink]
  'save': [item: SearchResult]
}>()

const getSourceLabel = (source: string) => {
  const map: Record<string, string> = {
    telegram: 'Telegram',
    wechat: '微信公众号',
    website: '网站',
    api: 'API'
  }
  return map[source] || source
}

const getCloudTypeLabel = (type: string) => {
  const map: Record<string, string> = {
    quark: '夸克',
    baidu: '百度',
    aliyun: '阿里',
    other: '其他'
  }
  return map[type] || type
}

const getScoreClass = (score?: number) => {
  if (!score) return 'score-low'
  if (score >= 80) return 'score-high'
  if (score >= 50) return 'score-medium'
  return 'score-low'
}

const formatDate = (dateStr: string) => {
  const date = new Date(dateStr)
  return date.toLocaleDateString('zh-CN')
}
</script>

<style scoped>
.result-card {
  display: flex;
  flex-direction: column;
  gap: var(--space-4);
  padding: 22px;
  animation: rise-in var(--transition-normal) cubic-bezier(0.22, 1, 0.36, 1) forwards;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.card-badges {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-2);
}

.source-badge,
.score-chip {
  display: inline-flex;
  align-items: center;
  min-height: 30px;
  padding: 0 12px;
  border-radius: var(--radius-full);
  font-size: 0.75rem;
  font-weight: var(--font-semibold);
}

.source-badge.telegram {
  background: rgba(79, 141, 246, 0.12);
  color: var(--primary-700);
}

.source-badge.wechat {
  background: rgba(51, 176, 122, 0.14);
  color: var(--success-700);
}

.source-badge.website {
  background: rgba(75, 159, 216, 0.14);
  color: var(--info-700);
}

.source-badge.api {
  background: rgba(231, 168, 61, 0.16);
  color: var(--warning-700);
}

.score-high {
  background: rgba(51, 176, 122, 0.14);
  color: var(--success-700);
}

.score-medium {
  background: rgba(231, 168, 61, 0.16);
  color: var(--warning-700);
}

.score-low {
  background: rgba(120, 138, 167, 0.14);
  color: var(--text-secondary);
}

.card-body {
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
}

.result-title {
  margin: 0;
  font-size: 1.06rem;
  line-height: 1.45;
  font-weight: var(--font-semibold);
  color: var(--text-primary);
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.result-content {
  margin: 0;
  font-size: 0.92rem;
  line-height: 1.68;
  color: var(--text-secondary);
  display: -webkit-box;
  -webkit-line-clamp: 3;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.result-meta {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-3);
}

.meta-item {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  color: var(--text-tertiary);
  font-size: 0.82rem;
}

.card-footer {
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  gap: var(--space-3);
  padding-top: var(--space-4);
  border-top: 1px solid var(--border-light);
}

.cloud-links {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-2);
}

.link-btn,
.save-btn {
  display: inline-flex;
  align-items: center;
  gap: 4px;
}

@media (max-width: 768px) {
  .card-footer {
    flex-direction: column;
    align-items: stretch;
  }

  .save-btn {
    width: 100%;
  }
}
</style>

<template>
  <div class="dashboard">
    <el-skeleton v-if="isInitialLoading" :rows="8" animated class="dashboard-skeleton" />

    <template v-else>
      <section class="dashboard-hero page-surface">
        <div class="hero-main">
          <div class="hero-toolbar">
            <div class="hero-copy">
              <span class="hero-chip">Operations Cockpit</span>
              <h2 class="hero-title">媒体链路、任务状态与缓存命中一屏可见</h2>
              <p class="hero-description">
                优先暴露服务健康、最近任务和文件谱系，把需要立即关注的信息固定在首屏上方。
              </p>
            </div>

            <div class="hero-header-actions">
              <el-button text @click="router.push('/tasks')">
                任务中心
                <el-icon class="el-icon--right"><ArrowRight /></el-icon>
              </el-button>
              <el-button plain :icon="Refresh" :loading="isRefreshing" @click="refreshDashboard">刷新数据</el-button>
            </div>
          </div>

          <div class="hero-signals">
            <article
              v-for="signal in heroSignals"
              :key="signal.label"
              class="hero-signal"
              :class="signal.tone"
            >
              <div class="hero-signal-icon">
                <el-icon size="18">
                  <component :is="signal.icon" />
                </el-icon>
              </div>
              <div class="hero-signal-copy">
                <span class="hero-signal-label">{{ signal.label }}</span>
                <strong class="hero-signal-value">{{ signal.value }}</strong>
                <p class="hero-signal-detail">{{ signal.detail }}</p>
              </div>
            </article>
          </div>
        </div>

        <div class="hero-side">
          <article class="hero-side-card task-spotlight">
            <div class="hero-side-head">
              <div class="hero-side-heading">
                <span class="section-label">聚焦</span>
                <h3 class="hero-side-title">最近任务</h3>
              </div>
              <el-tag :type="latestTaskStatus.type" size="small">{{ latestTaskStatus.label }}</el-tag>
            </div>

            <template v-if="latestTask">
              <p class="spotlight-name">{{ latestTask.name }}</p>
              <div class="spotlight-meta">
                <el-tag :type="getTaskTypeTag(latestTask.type)" size="small">
                  {{ getTaskTypeLabel(latestTask.type) }}
                </el-tag>
                <span class="spotlight-time">{{ latestTask.time }}</span>
              </div>
              <el-progress
                :percentage="latestTask.progress"
                :status="getProgressStatus(latestTask.status)"
                :stroke-width="8"
              />
            </template>

            <p v-else class="spotlight-empty">
              最近还没有任务记录，下一次执行后这里会自动显示最新状态。
            </p>
          </article>

          <article class="hero-side-card action-card">
            <div class="hero-side-head">
              <div class="hero-side-heading">
                <span class="section-label">操作</span>
                <h3 class="hero-side-title">快捷入口</h3>
              </div>
            </div>
            <div class="hero-actions">
              <el-button
                v-for="action in quickActions"
                :key="action.label"
                :type="action.type"
                class="action-btn"
                @click="action.onClick"
              >
                <el-icon><component :is="action.icon" /></el-icon>
                {{ action.label }}
              </el-button>
            </div>
          </article>
        </div>
      </section>

      <el-row :gutter="18" class="stats-row">
        <el-col :xs="24" :sm="12" :lg="6" v-for="stat in stats" :key="stat.title">
          <article
            class="stat-card page-surface"
            :class="stat.type"
            role="article"
            :aria-label="`${stat.title}: ${stat.value}`"
            tabindex="0"
          >
            <div class="stat-head">
              <span class="stat-title">{{ stat.title }}</span>
              <div class="stat-icon">
                <el-icon size="28">
                  <component :is="getIconComponent(stat.icon)" />
                </el-icon>
              </div>
            </div>

            <div class="stat-body">
              <div class="stat-value">{{ stat.value }}</div>
              <p class="stat-support">{{ stat.support }}</p>
            </div>
          </article>
        </el-col>
      </el-row>

      <el-row :gutter="18" class="charts-row">
        <el-col :xs="24" :lg="16">
          <section class="chart-card dashboard-card page-surface">
            <div class="card-header">
              <div class="card-heading">
                <span class="section-label">趋势</span>
                <h3 class="card-title">任务执行趋势</h3>
                <p class="card-description">观察最近 {{ timeRangeLabel }} 的任务完成与失败波动。</p>
              </div>
              <el-radio-group v-model="timeRange" size="small">
                <el-radio-button value="week">本周</el-radio-button>
                <el-radio-button value="month">本月</el-radio-button>
              </el-radio-group>
            </div>
            <div
              ref="taskChartRef"
              class="chart-container"
              role="img"
              aria-label="任务执行趋势图表"
              :aria-describedby="`chart-desc-${timeRange}`"
            ></div>
            <div :id="`chart-desc-${timeRange}`" class="sr-only">
              {{ `${timeRange === 'week' ? '本周' : '本月'}任务执行趋势，包含成功和失败数据` }}
            </div>
          </section>
        </el-col>

        <el-col :xs="24" :lg="8">
          <section class="chart-card dashboard-card page-surface">
            <div class="card-header compact">
              <div class="card-heading">
                <span class="section-label">分布</span>
                <h3 class="card-title">文件类型分布</h3>
                <p class="card-description">当前已收录文件的扩展类型占比。</p>
              </div>
            </div>
            <div
              ref="fileChartRef"
              class="chart-container"
              role="img"
              aria-label="文件类型分布图表"
            ></div>
          </section>
        </el-col>
      </el-row>

      <el-row class="tasks-row">
        <el-col :span="24">
          <section class="tasks-card dashboard-card page-surface">
            <div class="card-header">
              <div class="card-heading">
                <span class="section-label">任务</span>
                <h3 class="card-title">最近任务</h3>
                <p class="card-description">最近执行任务的状态、进度与耗时。</p>
              </div>
              <el-button type="primary" text @click="router.push('/tasks')">
                查看全部
                <el-icon class="el-icon--right"><ArrowRight /></el-icon>
              </el-button>
            </div>

            <el-table :data="recentTasks" class="dashboard-table" style="width: 100%">
              <el-table-column prop="name" label="任务名称" min-width="200">
                <template #default="{ row }">
                  <div class="task-name">
                    <el-icon :size="16"><Document /></el-icon>
                    <span>{{ row.name }}</span>
                  </div>
                </template>
              </el-table-column>
              <el-table-column prop="type" label="类型" width="120">
                <template #default="{ row }">
                  <el-tag :type="getTaskTypeTag(row.type)" size="small">
                    {{ getTaskTypeLabel(row.type) }}
                  </el-tag>
                </template>
              </el-table-column>
              <el-table-column prop="status" label="状态" width="110">
                <template #default="{ row }">
                  <el-tag :type="getStatusType(row.status)" size="small">
                    {{ getStatusLabel(row.status) }}
                  </el-tag>
                </template>
              </el-table-column>
              <el-table-column prop="progress" label="进度" width="200">
                <template #default="{ row }">
                  <el-progress
                    :percentage="row.progress"
                    :status="getProgressStatus(row.status)"
                    :stroke-width="8"
                  />
                </template>
              </el-table-column>
              <el-table-column prop="time" label="执行时间" width="180" />
            </el-table>
          </section>
        </el-col>
      </el-row>

      <el-row :gutter="18" class="status-row">
        <el-col :xs="24" :sm="12" :lg="8">
          <section class="status-card dashboard-card page-surface">
            <div class="status-header">
              <div class="card-heading">
                <span class="section-label">服务</span>
                <h3 class="card-title">服务状态</h3>
                <p class="card-description">关键服务当前可用性与健康状态。</p>
              </div>
              <el-tag :type="serviceSummary.type" size="small">{{ serviceSummary.badge }}</el-tag>
            </div>
            <div class="status-list">
              <div v-for="service in services" :key="service.name" class="status-item">
                <div class="status-info">
                  <el-icon :size="18" class="service-icon" :class="service.status">
                    <component :is="service.status === 'running' ? CircleCheck : CircleClose" />
                  </el-icon>
                  <span>{{ service.name }}</span>
                </div>
                <el-tag :type="service.status === 'running' ? 'success' : 'danger'" size="small">
                  {{ service.status === 'running' ? '正常' : '异常' }}
                </el-tag>
              </div>
            </div>
          </section>
        </el-col>

        <el-col :xs="24" :sm="12" :lg="8">
          <section class="status-card dashboard-card page-surface">
            <div class="status-header">
              <div class="card-heading">
                <span class="section-label">缓存</span>
                <h3 class="card-title">缓存统计</h3>
                <p class="card-description">缓存规模、命中率与过期策略概览。</p>
              </div>
              <el-button
                type="primary"
                text
                size="small"
                class="cache-clear-button"
                :loading="isClearingCache"
                @click="clearCache"
              >
                清空缓存
              </el-button>
            </div>
            <div class="cache-stats">
              <div class="cache-item">
                <div class="cache-value">{{ cacheStats.size }}</div>
                <div class="cache-label">缓存条目</div>
              </div>
              <div class="cache-item">
                <div class="cache-value">{{ formatPercent(cacheStats.hit_rate) }}</div>
                <div class="cache-label">命中率</div>
              </div>
              <div class="cache-item">
                <div class="cache-value">{{ cacheStats.ttl }}s</div>
                <div class="cache-label">TTL</div>
              </div>
            </div>
          </section>
        </el-col>

        <el-col :xs="24" :sm="12" :lg="8">
          <section class="status-card dashboard-card page-surface">
            <div class="status-header">
              <div class="card-heading">
                <span class="section-label">类型</span>
                <h3 class="card-title">文件谱系聚焦</h3>
                <p class="card-description">快速确认当前占比最高的文件类型。</p>
              </div>
            </div>
            <div v-if="topFileTypes.length > 0" class="type-list">
              <div v-for="fileType in topFileTypes" :key="fileType.name" class="type-item">
                <div class="type-copy">
                  <strong class="type-name">{{ fileType.name }}</strong>
                  <span class="type-share">{{ formatTypeShare(fileType.value) }}</span>
                </div>
                <span class="type-count">{{ fileType.value }}</span>
              </div>
            </div>
            <p v-else class="type-empty">等待索引同步后显示文件类型聚焦。</p>
          </section>
        </el-col>
      </el-row>
    </template>

    <div aria-live="polite" aria-atomic="true" class="sr-only">
      {{ isInitialLoading ? '正在加载数据' : isRefreshing ? '正在刷新数据' : '数据加载完成' }}
    </div>
  </div>
</template>

<script setup lang="ts">
import type { Component } from 'vue'
import { useRouter } from 'vue-router'
import {
  ArrowRight,
  CircleCheck,
  CircleClose,
  Document,
  DocumentAdd,
  Film,
  Refresh,
  Setting,
  getIconComponent,
} from '@/components/icons'
import {
  buildTaskLaunchQuery,
  getTaskTypeLabel,
} from '@/features/tasks'
import { useDashboardViewModel } from '@/features/dashboard/dashboard-view-model'

interface QuickAction {
  label: string
  icon: Component
  type?: 'primary' | 'success' | 'warning'
  onClick: () => void
}

const router = useRouter()
const {
  cacheStats,
  clearCache,
  fileChartRef,
  formatPercent,
  formatTypeShare,
  getProgressStatus,
  getStatusLabel,
  getStatusType,
  getTaskTypeTag,
  heroSignals,
  isClearingCache,
  isInitialLoading,
  isRefreshing,
  latestTask,
  latestTaskStatus,
  recentTasks,
  refreshDashboard,
  serviceSummary,
  services,
  stats,
  taskChartRef,
  timeRange,
  timeRangeLabel,
  topFileTypes,
} = useDashboardViewModel()

const quickActions: QuickAction[] = [
  {
    label: '同步文件',
    icon: Refresh,
    type: 'primary',
    onClick: () => {
      void router.push({
        path: '/tasks',
        query: buildTaskLaunchQuery('file_sync')
      })
    }
  },
  {
    label: '生成 STRM',
    icon: DocumentAdd,
    type: 'success',
    onClick: () => {
      void router.push({
        path: '/tasks',
        query: buildTaskLaunchQuery('strm_generation')
      })
    }
  },
  {
    label: '刮削目录',
    icon: Film,
    type: 'warning',
    onClick: () => {
      void router.push('/scrape-pathes')
    }
  },
  {
    label: '系统配置',
    icon: Setting,
    onClick: () => {
      void router.push('/config')
    }
  }
]
</script>

<style scoped>
.dashboard {
  display: flex;
  flex-direction: column;
  gap: var(--page-section-gap);
}

.dashboard-skeleton {
  padding: var(--space-5);
  border: 1px solid var(--border-light);
  border-radius: calc(var(--radius-xl) + 2px);
  background: var(--surface-card);
  box-shadow: var(--shadow-sm);
}

.dashboard-hero {
  position: relative;
  display: grid;
  grid-template-columns: minmax(0, 1.5fr) minmax(320px, 420px);
  gap: var(--space-5);
  overflow: hidden;
  padding: 24px;
}

.dashboard-hero::before,
.dashboard-hero::after {
  content: '';
  position: absolute;
  pointer-events: none;
}

.dashboard-hero::before {
  inset: -24% auto auto 54%;
  width: 240px;
  height: 240px;
  border-radius: 50%;
  background: radial-gradient(circle, rgba(79, 141, 246, 0.18), transparent 72%);
}

.dashboard-hero::after {
  inset: auto auto -18% -8%;
  width: 180px;
  height: 180px;
  border-radius: 50%;
  background: radial-gradient(circle, rgba(127, 113, 234, 0.14), transparent 70%);
}

.hero-main,
.hero-side {
  position: relative;
  z-index: 1;
}

.hero-main {
  display: flex;
  flex-direction: column;
  gap: 18px;
}

.hero-toolbar {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 20px;
}

.hero-copy {
  display: flex;
  min-width: 0;
  flex-direction: column;
  gap: 12px;
}

.hero-header-actions {
  display: flex;
  flex-shrink: 0;
  flex-wrap: wrap;
  align-items: center;
  justify-content: flex-end;
  gap: 10px;
}

.hero-chip {
  display: inline-flex;
  align-self: flex-start;
  padding: 7px 12px;
  border-radius: var(--radius-full);
  background: rgba(79, 141, 246, 0.14);
  color: var(--primary-700);
  font-family: var(--font-mono);
  font-size: 0.72rem;
  font-weight: var(--font-semibold);
  letter-spacing: 0.06em;
  text-transform: uppercase;
}

.hero-title {
  margin: 0;
  max-width: 16ch;
  font-size: clamp(1.7rem, 1.3rem + 1vw, 2.5rem);
  line-height: 1.05;
  font-weight: var(--font-bold);
  letter-spacing: var(--letter-spacing-tight);
  color: var(--text-primary);
}

.hero-description {
  max-width: 58ch;
  margin: 0;
  font-size: 0.94rem;
  line-height: 1.72;
  color: var(--text-secondary);
}

.hero-signals {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 12px;
}

.hero-signal,
.hero-side-card {
  border: 1px solid var(--border-light);
  border-radius: var(--radius-xl);
  background: rgba(255, 255, 255, 0.36);
  backdrop-filter: blur(16px);
  -webkit-backdrop-filter: blur(16px);
}

.hero-signal {
  display: flex;
  gap: 12px;
  min-height: 132px;
  padding: 16px;
}

.hero-signal.primary {
  --signal-bg: rgba(79, 141, 246, 0.14);
  --signal-color: var(--primary-700);
}

.hero-signal.success {
  --signal-bg: rgba(51, 176, 122, 0.14);
  --signal-color: var(--success-700);
}

.hero-signal.warning {
  --signal-bg: rgba(231, 168, 61, 0.16);
  --signal-color: var(--warning-700);
}

.hero-signal.info {
  --signal-bg: rgba(75, 159, 216, 0.14);
  --signal-color: var(--info-700);
}

.hero-signal-icon {
  display: flex;
  width: 42px;
  height: 42px;
  flex-shrink: 0;
  align-items: center;
  justify-content: center;
  border-radius: 14px;
  background: var(--signal-bg);
  color: var(--signal-color);
}

.hero-signal-copy {
  display: flex;
  min-width: 0;
  flex: 1;
  flex-direction: column;
  gap: 6px;
}

.hero-signal-label {
  color: var(--text-secondary);
  font-size: 0.76rem;
  font-weight: var(--font-semibold);
  letter-spacing: 0.04em;
}

.hero-signal-value {
  color: var(--text-primary);
  font-size: clamp(1.18rem, 1rem + 0.35vw, 1.45rem);
  line-height: 1.12;
}

.hero-signal-detail {
  margin: 0;
  color: var(--text-secondary);
  font-size: 0.82rem;
  line-height: 1.55;
}

.hero-side {
  display: grid;
  gap: 12px;
}

.hero-side-card {
  padding: 18px;
}

.hero-side-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 14px;
}

.hero-side-heading {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.hero-side-title {
  margin: 0;
  font-size: 1rem;
  line-height: 1.35;
  font-weight: var(--font-semibold);
  color: var(--text-primary);
}

.spotlight-name {
  margin: 0;
  color: var(--text-primary);
  font-size: 1rem;
  font-weight: var(--font-semibold);
  line-height: 1.5;
}

.spotlight-meta {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 10px;
  margin: 10px 0 14px;
}

.spotlight-time,
.spotlight-empty {
  color: var(--text-secondary);
  font-size: 0.84rem;
  line-height: 1.6;
}

.spotlight-empty {
  margin: 0;
}

.hero-actions {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 10px;
}

.action-btn {
  min-height: 46px;
  justify-content: flex-start;
  gap: 8px;
  border-radius: var(--radius-lg);
}

.stats-row,
.charts-row,
.tasks-row,
.status-row {
  margin-bottom: 0;
}

.stat-card,
.dashboard-card {
  height: 100%;
}

.stat-card {
  position: relative;
  display: flex;
  flex-direction: column;
  justify-content: space-between;
  gap: var(--space-5);
  min-height: 170px;
  padding: 22px;
  overflow: hidden;
  transition:
    transform var(--transition-fast),
    box-shadow var(--transition-fast),
    background var(--transition-fast);
}

.stat-card:hover {
  transform: translateY(-2px);
  background: var(--surface-card-hover);
  box-shadow: var(--shadow-md);
}

.stat-card::before {
  content: '';
  position: absolute;
  top: -26px;
  right: -18px;
  width: 140px;
  height: 140px;
  background: radial-gradient(circle, var(--stat-tint), transparent 70%);
  pointer-events: none;
}

.stat-card.primary {
  --stat-tint: rgba(79, 141, 246, 0.18);
  --stat-icon-bg: rgba(79, 141, 246, 0.12);
  --stat-icon-color: var(--primary-700);
  --stat-icon-border: rgba(79, 141, 246, 0.14);
}

.stat-card.success {
  --stat-tint: rgba(51, 176, 122, 0.18);
  --stat-icon-bg: rgba(51, 176, 122, 0.14);
  --stat-icon-color: var(--success-700);
  --stat-icon-border: rgba(51, 176, 122, 0.16);
}

.stat-card.warning {
  --stat-tint: rgba(231, 168, 61, 0.2);
  --stat-icon-bg: rgba(231, 168, 61, 0.16);
  --stat-icon-color: var(--warning-700);
  --stat-icon-border: rgba(231, 168, 61, 0.18);
}

.stat-card.info {
  --stat-tint: rgba(75, 159, 216, 0.2);
  --stat-icon-bg: rgba(75, 159, 216, 0.14);
  --stat-icon-color: var(--info-700);
  --stat-icon-border: rgba(75, 159, 216, 0.16);
}

.stat-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: var(--space-3);
}

.stat-title {
  font-size: 0.82rem;
  font-weight: var(--font-semibold);
  color: var(--text-secondary);
  letter-spacing: 0.03em;
}

.stat-body {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.stat-value {
  font-size: clamp(1.86rem, 4vw, 2.5rem);
  line-height: 1;
  font-weight: 700;
  color: var(--text-primary);
}

.stat-support {
  margin: 0;
  color: var(--text-secondary);
  font-size: 0.82rem;
  line-height: 1.55;
}

.stat-icon {
  position: relative;
  z-index: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  width: 58px;
  height: 58px;
  border: 1px solid var(--stat-icon-border);
  border-radius: 20px;
  background: var(--stat-icon-bg);
  color: var(--stat-icon-color);
  flex-shrink: 0;
}

.dashboard-card {
  padding: 22px;
}

.card-header,
.status-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: var(--space-4);
  margin-bottom: var(--space-5);
}

.card-header.compact {
  margin-bottom: var(--space-4);
}

.card-heading {
  display: flex;
  flex-direction: column;
  gap: 10px;
  min-width: 0;
}

.card-title {
  margin: 0;
  font-size: 1.05rem;
  line-height: 1.4;
  font-weight: var(--font-semibold);
  color: var(--text-primary);
}

.card-description {
  margin: 0;
  font-size: 0.9rem;
  line-height: 1.6;
  color: var(--text-secondary);
}

.chart-container {
  height: 300px;
}

.task-name {
  display: flex;
  align-items: center;
  gap: 10px;
  font-weight: var(--font-medium);
  color: var(--text-primary);
}

.task-name :deep(.el-icon) {
  color: var(--primary-600);
}

.dashboard-table :deep(.el-progress__text) {
  color: var(--text-secondary);
  font-weight: var(--font-semibold);
}

.status-card {
  display: flex;
  flex-direction: column;
}

.status-list,
.type-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.status-item,
.cache-item,
.type-item {
  border: 1px solid var(--border-light);
  background: rgba(255, 255, 255, 0.24);
}

.status-item,
.type-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-3);
  padding: 14px 16px;
  border-radius: var(--radius-lg);
}

.status-info {
  display: flex;
  align-items: center;
  gap: 10px;
  color: var(--text-primary);
}

.service-icon.running {
  color: var(--success-600);
}

.service-icon.stopped {
  color: var(--danger-600);
}

.cache-stats {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 12px;
}

.cache-item {
  padding: 16px 12px;
  border-radius: var(--radius-lg);
  text-align: center;
}

.cache-value {
  font-size: clamp(1.25rem, 2.4vw, 1.75rem);
  font-weight: 700;
  color: var(--text-primary);
  margin-bottom: 6px;
}

.cache-label {
  font-size: 0.78rem;
  color: var(--text-secondary);
}

.type-copy {
  display: flex;
  min-width: 0;
  flex-direction: column;
  gap: 4px;
}

.type-name {
  color: var(--text-primary);
  font-size: 0.9rem;
  font-weight: var(--font-semibold);
}

.type-share,
.type-empty {
  color: var(--text-secondary);
  font-size: 0.8rem;
  line-height: 1.55;
}

.type-count {
  color: var(--text-primary);
  font-size: 1rem;
  font-weight: var(--font-semibold);
}

.type-empty {
  margin: 0;
}

.sr-only {
  position: absolute;
  width: 1px;
  height: 1px;
  padding: 0;
  margin: -1px;
  overflow: hidden;
  clip: rect(0, 0, 0, 0);
  white-space: nowrap;
  border-width: 0;
}

@media (max-width: 1200px) {
  .dashboard-hero {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 992px) {
  .card-header,
  .status-header,
  .hero-side-head,
  .hero-toolbar {
    flex-direction: column;
    align-items: stretch;
  }

  .hero-signals {
    grid-template-columns: 1fr;
  }

  .hero-header-actions {
    justify-content: flex-start;
  }

  .chart-container {
    height: 260px;
  }
}

@media (max-width: 768px) {
  .dashboard-hero,
  .stat-card,
  .dashboard-card {
    padding: 18px;
  }

  .hero-title {
    max-width: none;
    font-size: 1.5rem;
  }

  .hero-actions,
  .cache-stats {
    grid-template-columns: 1fr;
  }

  .chart-container {
    height: 220px;
  }
}
</style>

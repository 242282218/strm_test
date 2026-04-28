<template>
  <div class="search-page">
    <!-- Hero Search Section -->
    <SearchHero>
      <SearchBox
        v-model="searchStore.query"
        :loading="searchStore.loading"
        :hot-tags="searchStore.hotTags"
        @search="handleSearch"
      />
    </SearchHero>

    <!-- Results Info Bar -->
    <SearchFilters :visible="searchStore.hasSearched" />

    <!-- Search Results -->
    <SearchResults
      v-if="searchStore.hasSearched && !searchStore.isEmpty"
      :results="searchStore.results"
      :total="searchStore.totalResults"
      :search-time="searchStore.searchTime"
      :view-mode="searchStore.viewMode"
      :has-more="searchStore.hasMore"
      :loading-more="searchStore.loadingMore"
      @update:view-mode="searchStore.setViewMode"
      @open-link="openCloudLink"
      @save="saveToCloud"
      @load-more="searchStore.loadMore"
    />

    <!-- Empty State -->
    <SearchEmpty v-if="searchStore.isEmpty" type="empty" />

    <!-- Initial State -->
    <SearchEmpty v-if="!searchStore.hasSearched && !searchStore.loading" type="initial" />
  </div>
</template>

<script setup lang="ts">
import type { AxiosError } from 'axios'
import { useSearchStore } from '@/stores/search'
import { listCloudDrives } from '@/api/cloudDrive'
import { transferShare } from '@/api/transfer'
import type { SearchResult, CloudLink } from '@/api/search'
import { useNotification, useDebounce } from '@/composables'
import SearchHero from '@/components/search/SearchHero.vue'
import SearchBox from '@/components/search/SearchBox.vue'
import SearchFilters from '@/components/search/SearchFilters.vue'
import SearchResults from '@/components/search/SearchResults.vue'
import SearchEmpty from '@/components/search/SearchEmpty.vue'

const searchStore = useSearchStore()
const { success, error, warning, info, alert, prompt } = useNotification()

// 使用防抖优化搜索
const { run: debouncedSearch } = useDebounce(
  async (keyword: string) => {
    const result = await searchStore.search(keyword)
    if (!result) {
      error('搜索失败，请稍后重试')
    }
  },
  300
)

// Handle search
const handleSearch = async (keyword: string) => {
  if (!keyword.trim()) {
    warning('请输入搜索关键词')
    return
  }
  await debouncedSearch(keyword)
}

// Open cloud link
const openCloudLink = (link: CloudLink) => {
  if (link.password) {
    alert(`提取密码: ${link.password}`, '需要提取密码').then(() => {
      navigator.clipboard.writeText(link.password || '')
      window.open(link.url, '_blank')
    })
  } else {
    window.open(link.url, '_blank')
  }
}

// Save to cloud
const saveToCloud = async (item: SearchResult) => {
  const quarkLink = item.cloud_links.find((link) => link.type === 'quark')
  if (!quarkLink) {
    error('该资源没有夸克网盘链接')
    return
  }

  try {
    const targetDir = await prompt(
      '请输入转存目录，例如 /电影 或 /电视剧',
      '转存到夸克网盘',
      '/'
    )

    if (!targetDir) return

    let quarkDriveId: number | undefined
    try {
      const drives = await listCloudDrives()
      const quarkDrive = drives.find((drive) => drive.drive_type === 'quark')
      quarkDriveId = quarkDrive?.id
    } catch {
      quarkDriveId = undefined
    }

    if (!quarkDriveId) {
      info('未检测到夸克账号，将尝试使用系统配置的 quark.cookie 转存')
    }

    const result = await transferShare({
      drive_id: quarkDriveId,
      share_url: quarkLink.url,
      target_dir: (targetDir || '/').trim() || '/',
      password: quarkLink.password || '',
      auto_organize: false
    })

    success(result.message || '转存请求已提交')
  } catch (err: unknown) {
    const action = (err as { action?: string } | null)?.action
    if (action === 'cancel' || action === 'close' || String(err).includes('cancel')) {
      return
    }
    const detail = (err as AxiosError<{ detail?: string }> | null)?.response?.data?.detail
    error(detail || '转存失败，请稍后重试')
  }
}
</script>

<style scoped>
.search-page {
  min-height: 100%;
}
</style>

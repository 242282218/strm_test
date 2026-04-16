import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { searchResources, type SearchResult } from '@/api/search'

export type ViewMode = 'grid' | 'list'

export const useSearchStore = defineStore('search', () => {
  // State
  const query = ref('')
  const results = ref<SearchResult[]>([])
  const loading = ref(false)
  const loadingMore = ref(false)
  const hasMore = ref(false)
  const hasSearched = ref(false)
  const viewMode = ref<ViewMode>('grid')
  const totalResults = ref(0)
  const searchTime = ref(0)
  const currentPage = ref(1)
  const pageSize = 20

  // Hot tags
  const hotTags = ['流浪地球', '三体', '狂飙', '奥本海默', '芭比', '封神']

  // Getters
  const isEmpty = computed(() => results.value.length === 0 && !loading.value && hasSearched.value)

  // Actions
  async function search(keyword: string) {
    if (!keyword.trim()) {
      return false
    }

    loading.value = true
    hasSearched.value = true
    query.value = keyword
    currentPage.value = 1

    const startTime = Date.now()

    try {
      const response = await searchResources({
        keyword: keyword,
        page: currentPage.value,
        page_size: pageSize
      })

      results.value = response.results
      totalResults.value = response.total
      hasMore.value = response.has_more
      searchTime.value = Date.now() - startTime
      if (response.error) {
        return false
      }
      return true
    } catch (error) {
      console.error('Search failed:', error)
      return false
    } finally {
      loading.value = false
    }
  }

  async function loadMore() {
    if (loadingMore.value || !hasMore.value) return false

    loadingMore.value = true
    currentPage.value++

    try {
      const response = await searchResources({
        keyword: query.value,
        page: currentPage.value,
        page_size: pageSize
      })

      if (response.error) {
        currentPage.value--
        return false
      }

      results.value.push(...response.results)
      hasMore.value = response.has_more
      return true
    } catch (error) {
      console.error('Load more failed:', error)
      currentPage.value--
      return false
    } finally {
      loadingMore.value = false
    }
  }

  function reset() {
    query.value = ''
    results.value = []
    loading.value = false
    loadingMore.value = false
    hasMore.value = false
    hasSearched.value = false
    totalResults.value = 0
    searchTime.value = 0
    currentPage.value = 1
  }

  function setViewMode(mode: ViewMode) {
    viewMode.value = mode
  }

  return {
    // State
    query,
    results,
    loading,
    loadingMore,
    hasMore,
    hasSearched,
    viewMode,
    totalResults,
    searchTime,
    hotTags,
    // Getters
    isEmpty,
    // Actions
    search,
    loadMore,
    reset,
    setViewMode
  }
})

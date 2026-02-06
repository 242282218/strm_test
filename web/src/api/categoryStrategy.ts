import api from './index'

export interface CategoryStrategy {
  enabled: boolean
  anime_keywords: string[]
  folder_names: {
    anime: string
    movie: string
    tv: string
  }
}

export interface CategoryPreviewResponse {
  category_key: 'anime' | 'movie' | 'tv'
  category_folder: string
}

export const categoryStrategyApi = {
  get(): Promise<CategoryStrategy> {
    return api.get('/scrape/category-strategy')
  },

  update(payload: CategoryStrategy): Promise<CategoryStrategy> {
    return api.put('/scrape/category-strategy', payload)
  },

  preview(payload: { file_name: string; media_type: 'auto' | 'movie' | 'tv' }): Promise<CategoryPreviewResponse> {
    return api.post('/scrape/category-strategy/preview', payload)
  }
}


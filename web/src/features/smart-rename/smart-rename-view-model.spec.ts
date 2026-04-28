import { describe, expect, it } from 'vitest'

import {
  buildDisplayRows,
  mergeRecentPaths,
  normalizeCloudItem,
  type ViewRenameItem,
} from './smart-rename-view-model'

describe('smart-rename-view-model', () => {
  it('mergeRecentPaths deduplicates and keeps the newest six paths', () => {
    const result = mergeRecentPaths('G:/Media', [
      'A:/Anime',
      'B:/TV',
      'G:/Media',
      'C:/Movies',
      'D:/Docs',
      'E:/Kids',
      'F:/Sports',
    ])

    expect(result).toEqual([
      'G:/Media',
      'A:/Anime',
      'B:/TV',
      'C:/Movies',
      'D:/Docs',
      'E:/Kids',
    ])
  })

  it('buildDisplayRows filters and sorts rows with the same rules as the view', () => {
    const rows: ViewRenameItem[] = [
      {
        id: '1',
        source_mode: 'local',
        original_path: 'D:/Media/Alpha.mkv',
        original_name: 'Alpha.mkv',
        new_name: 'Alpha (2024).mkv',
        media_type: 'movie',
        overall_confidence: 0.95,
        status: 'parsed',
        needs_confirmation: false,
        tmdb_id: 100,
      },
      {
        id: '2',
        source_mode: 'local',
        original_path: 'D:/Media/Beta.mkv',
        original_name: 'Beta.mkv',
        new_name: 'Beta (2020).mkv',
        media_type: 'movie',
        overall_confidence: 0.55,
        status: 'failed',
        needs_confirmation: true,
      },
      {
        id: '3',
        source_mode: 'cloud',
        original_path: 'fid-3',
        original_name: 'Gamma.mkv',
        new_name: 'Gamma (2023).mkv',
        media_type: 'tv',
        overall_confidence: 0.72,
        status: 'success',
        needs_confirmation: false,
        tmdb_title: 'Gamma',
      },
    ]

    const result = buildDisplayRows(rows, {
      keyword: 'a',
      statusFilter: 'all',
      confidenceFilter: 'medium',
      sortKey: 'confidence_asc',
    })

    expect(result.map((row) => row.id)).toEqual(['3'])
  })

  it('normalizeCloudItem maps cloud rows to the shared view shape with fallback status', () => {
    const result = normalizeCloudItem({
      fid: 'fid-1',
      original_name: 'Episode 01.mkv',
      new_name: '',
      media_type: 'tv',
      overall_confidence: 0.88,
      needs_confirmation: true,
      used_algorithm: 'ai_enhanced',
      tmdb_title: 'Show Name',
    })

    expect(result).toMatchObject({
      id: 'fid-1',
      source_mode: 'cloud',
      original_path: 'fid-1',
      original_name: 'Episode 01.mkv',
      new_name: 'Episode 01.mkv',
      status: 'needs_confirmation',
      needs_confirmation: true,
      used_algorithm: 'ai_enhanced',
      tmdb_title: 'Show Name',
    })
  })
})

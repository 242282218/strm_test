import { describe, expect, it } from 'vitest'

import {
  applyCloudExecuteResponse,
  applyCloudRollbackResponse,
} from './smart-rename-execution'
import type { CloudExecutionSnapshot, ViewRenameItem } from './smart-rename-view-model'

describe('smart-rename-execution', () => {
  it('applyCloudExecuteResponse builds summary, snapshots, and row statuses', () => {
    const rows: ViewRenameItem[] = [
      {
        id: 'fid-1',
        source_mode: 'cloud',
        original_path: 'fid-1',
        original_name: 'Old One.mkv',
        new_name: 'New One.mkv',
        media_type: 'movie',
        overall_confidence: 0.95,
        status: 'parsed',
        needs_confirmation: false,
      },
      {
        id: 'fid-2',
        source_mode: 'cloud',
        original_path: 'fid-2',
        original_name: 'Old Two.mkv',
        new_name: 'Old Two.mkv',
        media_type: 'movie',
        overall_confidence: 0.7,
        status: 'parsed',
        needs_confirmation: false,
      },
      {
        id: 'fid-3',
        source_mode: 'cloud',
        original_path: 'fid-3',
        original_name: 'Old Three.mkv',
        new_name: 'New Three.mkv',
        media_type: 'movie',
        overall_confidence: 0.4,
        status: 'parsed',
        needs_confirmation: false,
      },
    ]

    const result = applyCloudExecuteResponse('batch-1', rows, {
      total: 3,
      success: 1,
      failed: 1,
      skipped: 1,
      results: [
        { fid: 'fid-1', status: 'success', new_name: 'New One.mkv' },
        { fid: 'fid-2', status: 'skipped' },
        { fid: 'fid-3', status: 'failed', error: 'rename failed' },
      ],
    })

    expect(result.executeSummary).toEqual({
      batch_id: 'batch-1',
      total_items: 3,
      success_items: 1,
      failed_items: 1,
      skipped_items: 1,
    })
    expect(result.lastCloudExecution).toEqual<CloudExecutionSnapshot[]>([
      { fid: 'fid-1', original_name: 'Old One.mkv', executed_name: 'New One.mkv' },
      { fid: 'fid-2', original_name: 'Old Two.mkv', executed_name: 'Old Two.mkv' },
      { fid: 'fid-3', original_name: 'Old Three.mkv', executed_name: 'New Three.mkv' },
    ])
    expect(result.previewRows).toMatchObject([
      { id: 'fid-1', original_name: 'New One.mkv', status: 'success', needs_confirmation: false },
      { id: 'fid-2', status: 'skipped', confirmation_reason: '目标名称与原名称一致，已跳过' },
      { id: 'fid-3', status: 'failed', confirmation_reason: 'rename failed' },
    ])
  })

  it('applyCloudRollbackResponse restores successful rows and keeps failed snapshots pending', () => {
    const rows: ViewRenameItem[] = [
      {
        id: 'fid-1',
        source_mode: 'cloud',
        original_path: 'fid-1',
        original_name: 'New One.mkv',
        new_name: 'New One.mkv',
        media_type: 'movie',
        overall_confidence: 0.95,
        status: 'success',
        needs_confirmation: false,
      },
      {
        id: 'fid-2',
        source_mode: 'cloud',
        original_path: 'fid-2',
        original_name: 'New Two.mkv',
        new_name: 'New Two.mkv',
        media_type: 'movie',
        overall_confidence: 0.7,
        status: 'success',
        needs_confirmation: false,
      },
    ]
    const snapshots: CloudExecutionSnapshot[] = [
      { fid: 'fid-1', original_name: 'Old One.mkv', executed_name: 'New One.mkv' },
      { fid: 'fid-2', original_name: 'Old Two.mkv', executed_name: 'New Two.mkv' },
    ]

    const result = applyCloudRollbackResponse('batch-1', rows, snapshots, {
      total: 2,
      success: 1,
      failed: 1,
      results: [
        { fid: 'fid-1', status: 'success' },
        { fid: 'fid-2', status: 'failed', error: 'still locked' },
      ],
    })

    expect(result.executeSummary).toEqual({
      batch_id: 'batch-1',
      total_items: 2,
      success_items: 1,
      failed_items: 1,
      skipped_items: 0,
    })
    expect(result.previewRows).toMatchObject([
      { id: 'fid-1', original_name: 'Old One.mkv', new_name: 'Old One.mkv', status: 'rolled_back' },
      { id: 'fid-2', original_name: 'New Two.mkv', new_name: 'New Two.mkv', status: 'success' },
    ])
    expect(result.remainingSnapshots).toEqual<CloudExecutionSnapshot[]>([
      { fid: 'fid-2', original_name: 'Old Two.mkv', executed_name: 'New Two.mkv' },
    ])
  })
})

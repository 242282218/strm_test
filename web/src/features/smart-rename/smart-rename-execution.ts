import type { QuarkRenameExecuteResponse } from '@/api/quark'

import type { CloudExecutionSnapshot, ViewRenameItem } from './smart-rename-view-model'
import type { SmartRenameExecuteResponse } from './api/smartRename'

export function buildExecuteSummary(
  batchId: string,
  response: Pick<QuarkRenameExecuteResponse['data'], 'total' | 'success' | 'failed'> & { skipped?: number },
): SmartRenameExecuteResponse {
  return {
    batch_id: batchId,
    total_items: response.total,
    success_items: response.success,
    failed_items: response.failed,
    skipped_items: response.skipped ?? Math.max(response.total - response.success - response.failed, 0),
  }
}

export function buildCloudExecutionSnapshots(rows: ViewRenameItem[]): CloudExecutionSnapshot[] {
  return rows
    .filter((row) => (row.new_name || '').trim().length > 0)
    .map((row) => ({
      fid: row.id,
      original_name: row.original_name,
      executed_name: row.new_name,
    }))
}

export function applyCloudExecuteResponse(
  batchId: string,
  previewRows: ViewRenameItem[],
  response: Pick<QuarkRenameExecuteResponse['data'], 'total' | 'success' | 'failed' | 'results'> & { skipped?: number },
): {
  executeSummary: SmartRenameExecuteResponse
  lastCloudExecution: CloudExecutionSnapshot[]
  previewRows: ViewRenameItem[]
} {
  const resultMap = new Map((response.results || []).map((item) => [item.fid, item]))

  return {
    executeSummary: buildExecuteSummary(batchId, response),
    lastCloudExecution: buildCloudExecutionSnapshots(previewRows),
    previewRows: previewRows.map((row) => {
      const result = resultMap.get(row.id)
      if (!result) return row
      if (result.status === 'success') {
        return {
          ...row,
          original_name: row.new_name,
          status: 'success',
          needs_confirmation: false,
          confirmation_reason: undefined,
        }
      }
      if (result.status === 'skipped') {
        return {
          ...row,
          status: 'skipped',
          confirmation_reason: '目标名称与原名称一致，已跳过',
        }
      }
      return {
        ...row,
        status: 'failed',
        confirmation_reason: result.error || '执行失败',
      }
    }),
  }
}

export function applyCloudRollbackResponse(
  batchId: string,
  previewRows: ViewRenameItem[],
  snapshots: CloudExecutionSnapshot[],
  response: Pick<QuarkRenameExecuteResponse['data'], 'total' | 'success' | 'failed' | 'results'> & { skipped?: number },
): {
  executeSummary: SmartRenameExecuteResponse
  previewRows: ViewRenameItem[]
  remainingSnapshots: CloudExecutionSnapshot[]
} {
  const successSet = new Set((response.results || []).filter((item) => item.status === 'success').map((item) => item.fid))

  return {
    executeSummary: buildExecuteSummary(batchId, response),
    previewRows: previewRows.map((row) => {
      const snapshot = snapshots.find((item) => item.fid === row.id)
      if (!snapshot || !successSet.has(row.id)) return row
      return {
        ...row,
        original_name: snapshot.original_name,
        new_name: snapshot.original_name,
        status: 'rolled_back',
        needs_confirmation: false,
        confirmation_reason: undefined,
      }
    }),
    remainingSnapshots: snapshots.filter((item) => !successSet.has(item.fid)),
  }
}

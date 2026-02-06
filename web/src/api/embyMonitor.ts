import api from './index'

export interface EmbyEventLog {
  id: number
  event_id: string
  event_type: string
  item_id: string | null
  item_name: string | null
  item_type: string | null
  aggregated_count: number
  payload: Record<string, unknown> | null
  created_at: string
  updated_at: string
}

export interface EmbyEventsResponse {
  items: EmbyEventLog[]
  total: number
}

export interface EmbyDeletePlanItem {
  emby_item_id: string
  event_id?: string | null
  event_type?: string | null
  item_name?: string | null
  item_type?: string | null
  pickcode?: string | null
  path?: string | null
  risk_level: string
  can_execute: boolean
  reason?: string | null
  action: string
  execution_status?: string
  execution_detail?: string
}

export interface EmbyDeletePlanResponse {
  success: boolean
  plan_id: string
  dry_run: boolean
  total_items: number
  executable_items: number
  items: EmbyDeletePlanItem[]
}

export interface EmbyDeleteExecuteResponse {
  success: boolean
  plan_id: string
  status: string
  executed_items: number
  skipped_items: number
  idempotent?: boolean
}

export const embyMonitorApi = {
  getEvents(params?: {
    event_type?: string
    item_type?: string
    keyword?: string
    page?: number
    size?: number
  }): Promise<EmbyEventsResponse> {
    return api.get('/emby/events', { params: params || {} })
  },

  createDeletePlan(payload: {
    source?: string
    event_ids?: string[]
    item_ids?: string[]
    reason?: string
  }): Promise<EmbyDeletePlanResponse> {
    return api.post('/emby/delete-plan', payload)
  },

  executeDeletePlan(payload: { plan_id: string; executed_by?: string }): Promise<EmbyDeleteExecuteResponse> {
    return api.post('/emby/delete-execute', payload)
  }
}

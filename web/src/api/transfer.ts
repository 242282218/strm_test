/**
 * Transfer API wrapper.
 *
 * Purpose: Provide transfer operations for share links.
 * Input: Transfer request payload.
 * Output: Promise with transfer result message.
 * Side effects: Performs HTTP POST request to backend.
 */
import api from './index'

export interface TransferRequest {
  drive_id?: number
  share_url: string
  target_dir: string
  password?: string
  auto_organize?: boolean
}

export interface TransferResponse {
  message: string
}

/**
 * Submit transfer request.
 *
 * Purpose: Trigger backend transfer of a share link.
 * Input: TransferRequest.
 * Output: Promise<TransferResponse>.
 * Side effects: Performs HTTP POST request.
 */
export const transferShare = (data: TransferRequest): Promise<TransferResponse> => {
  return api.post('/transfer', data)
}

/**
 * Cloud drive API wrapper.
 *
 * Purpose: Provide access to cloud drive endpoints.
 * Input: None.
 * Output: Promise of cloud drive list.
 * Side effects: Performs HTTP requests to backend.
 */
import api from './index'

export interface CloudDrive {
  id: number
  name: string
  drive_type: string
  cookie?: string
  remark?: string
  status?: string
  last_check?: string
}

/**
 * Fetch cloud drives.
 *
 * Purpose: Get available cloud drives for transfer.
 * Input: None.
 * Output: Promise<CloudDrive[]>.
 * Side effects: Performs HTTP GET request.
 */
export const listCloudDrives = (): Promise<CloudDrive[]> => {
  return api.get('/drives')
}

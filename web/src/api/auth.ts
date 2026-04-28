/**
 * 认证 API 模块
 *
 * 提供登录、登出、Token 验证等认证相关接口
 */
import api from './index'

/**
 * 登录请求接口
 */
export interface LoginRequest {
  api_key: string
}

/**
 * 登录响应接口
 */
export interface LoginResponse {
  success: boolean
  message: string
  token: string | null
}

/**
 * 验证响应接口
 */
export interface VerifyResponse {
  valid: boolean
  message: string
}

/**
 * 登出响应接口
 */
export interface LogoutResponse {
  success: boolean
  message: string
}

/**
 * 认证状态响应接口
 */
export interface AuthStatusResponse {
  auth_required: boolean
  has_api_key_configured: boolean
  has_admin_user: boolean
  can_init_admin: boolean
  message: string
}

/**
 * 登录
 *
 * @param apiKey API Key
 * @returns 登录响应
 */
export const login = async (apiKey: string): Promise<LoginResponse> => {
  const response = await api.post('/auth/login', { api_key: apiKey })
  return response as unknown as LoginResponse
}

/**
 * 验证 Token
 *
 * @returns 验证响应
 */
export const verifyToken = async (): Promise<VerifyResponse> => {
  const response = await api.get('/auth/verify')
  return response as unknown as VerifyResponse
}

/**
 * 登出
 *
 * @returns 登出响应
 */
export const logout = async (): Promise<LogoutResponse> => {
  const response = await api.post('/auth/logout')
  return response as unknown as LogoutResponse
}

/**
 * 获取认证状态
 *
 * @returns 认证状态响应
 */
export const getAuthStatus = async (): Promise<AuthStatusResponse> => {
  const response = await api.get('/auth/status')
  return response as unknown as AuthStatusResponse
}

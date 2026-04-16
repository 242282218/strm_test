import axios, { type AxiosInstance, type AxiosRequestConfig } from 'axios'

type DataReturningMethodNames =
  | 'request'
  | 'get'
  | 'delete'
  | 'head'
  | 'options'
  | 'post'
  | 'put'
  | 'patch'
  | 'postForm'
  | 'putForm'
  | 'patchForm'

export interface ApiClient extends Omit<AxiosInstance, DataReturningMethodNames> {
  request<T = unknown, D = unknown>(config: AxiosRequestConfig<D>): Promise<T>
  get<T = unknown, D = unknown>(url: string, config?: AxiosRequestConfig<D>): Promise<T>
  delete<T = unknown, D = unknown>(url: string, config?: AxiosRequestConfig<D>): Promise<T>
  head<T = unknown, D = unknown>(url: string, config?: AxiosRequestConfig<D>): Promise<T>
  options<T = unknown, D = unknown>(url: string, config?: AxiosRequestConfig<D>): Promise<T>
  post<T = unknown, D = unknown>(url: string, data?: D, config?: AxiosRequestConfig<D>): Promise<T>
  put<T = unknown, D = unknown>(url: string, data?: D, config?: AxiosRequestConfig<D>): Promise<T>
  patch<T = unknown, D = unknown>(url: string, data?: D, config?: AxiosRequestConfig<D>): Promise<T>
  postForm<T = unknown, D = unknown>(url: string, data?: D, config?: AxiosRequestConfig<D>): Promise<T>
  putForm<T = unknown, D = unknown>(url: string, data?: D, config?: AxiosRequestConfig<D>): Promise<T>
  patchForm<T = unknown, D = unknown>(url: string, data?: D, config?: AxiosRequestConfig<D>): Promise<T>
}

// 从 Cookie 获取 CSRF Token
function getCsrfToken(): string | null {
  const match = document.cookie.match(new RegExp('(^| )csrf_token=([^;]+)'))
  return match && match[2] ? match[2] : null
}

const axiosInstance = axios.create({
  baseURL: '/api',
  timeout: 30000,
  headers: {
    'Content-Type': 'application/json'
  },
  withCredentials: true  // 允许发送 Cookie
})

function shouldHandleUnauthorizedLocally(url?: string): boolean {
  const normalized = (url || '').toLowerCase()
  return normalized.includes('/auth/login') || normalized.includes('/auth/status')
}

axiosInstance.interceptors.request.use(
  (config) => {
    // Token 现在通过 HttpOnly Cookie 自动发送，无需手动添加

    // 添加 CSRF Token（仅对非 GET 请求）
    if (config.method && !['get', 'head', 'options'].includes(config.method.toLowerCase())) {
      const csrfToken = getCsrfToken()
      if (csrfToken) {
        if (typeof config.headers?.set === 'function') {
          config.headers.set('X-CSRF-Token', csrfToken)
        } else {
          config.headers['X-CSRF-Token'] = csrfToken
        }
      }
    }

    return config
  },
  (error) => Promise.reject(error)
)

axiosInstance.interceptors.response.use(
  (response) => response.data,
  (error) => {
    if (
      error.response?.status === 401 &&
      !shouldHandleUnauthorizedLocally(error.config?.url) &&
      window.location.pathname !== '/login'
    ) {
      // Token 无效，重定向到登录页
      window.location.href = '/login'
    }
    return Promise.reject(error)
  }
)

const api = axiosInstance as ApiClient

export default api

import axios, { type AxiosRequestConfig } from 'axios'

const instance = axios.create({
  baseURL: '/api',
  timeout: 30000,
})

// 请求拦截器：注入 JWT token
instance.interceptors.request.use((config) => {
  const token = localStorage.getItem('token')
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

// 响应拦截器：统一错误处理 + 自动解包 response.data
instance.interceptors.response.use(
  (response) => response.data,
  (error) => {
    if (error.response?.status === 401) {
      // 只在非登录页面时清除 token 并跳转
      if (!window.location.pathname.includes('/login')) {
        localStorage.removeItem('token')
        window.location.href = '/login'
      }
    }
    return Promise.reject(error)
  },
)

/**
 * 类型安全的请求封装 —— 响应拦截器已解包 response.data，
 * 这里将返回类型从 Promise<AxiosResponse<T>> 修正为 Promise<T>
 */
const request = {
  get<T = any>(url: string, config?: AxiosRequestConfig): Promise<T> {
    return instance.get(url, config) as Promise<T>
  },
  post<T = any>(url: string, data?: any, config?: AxiosRequestConfig): Promise<T> {
    return instance.post(url, data, config) as Promise<T>
  },
  put<T = any>(url: string, data?: any, config?: AxiosRequestConfig): Promise<T> {
    return instance.put(url, data, config) as Promise<T>
  },
  delete<T = any>(url: string, config?: AxiosRequestConfig): Promise<T> {
    return instance.delete(url, config) as Promise<T>
  },
}

export default request

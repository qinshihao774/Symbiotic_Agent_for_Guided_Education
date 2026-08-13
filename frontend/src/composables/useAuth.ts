import { useAuthStore } from '@/stores/auth'
import request from '@/utils/request'

export function useAuth() {
  const authStore = useAuthStore()

  async function login(username: string, password: string) {
    const data = await request.post('/auth/login', { username, password })
    // request interceptor unwraps response.data, so data is the response body
    authStore.setToken((data as any).token)
    return data
  }

  async function register(username: string, password: string, role: 'student' | 'teacher') {
    return request.post('/auth/register', { username, password, role })
  }

  return { login, register }
}

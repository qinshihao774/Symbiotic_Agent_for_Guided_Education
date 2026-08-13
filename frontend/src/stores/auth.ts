import { defineStore } from 'pinia'
import { ref } from 'vue'

export interface UserInfo {
  id: number
  name: string
  email: string | null
  gender: string | null
  stu_level: string | null
  class_id?: number | null
  class_name?: string | null
  role: 'student' | 'teacher' | 'admin'
}

export const useAuthStore = defineStore('auth', () => {
  const token = ref<string | null>(localStorage.getItem('token'))
  const user = ref<UserInfo | null>(null)

  function setToken(newToken: string) {
    token.value = newToken
    localStorage.setItem('token', newToken)
  }

  function setUser(userInfo: UserInfo) {
    user.value = userInfo
  }

  function logout() {
    token.value = null
    user.value = null
    localStorage.removeItem('token')
    localStorage.removeItem('userRole')
  }

  return { token, user, setToken, setUser, logout }
})

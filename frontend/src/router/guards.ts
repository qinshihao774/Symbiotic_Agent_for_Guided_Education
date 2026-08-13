import type { Router } from 'vue-router'

export function setupGuards(router: Router) {
  router.beforeEach((to, _from, next) => {
    // Public routes: login, register - no auth check
    if (to.meta.public) {
      next()
      return
    }

    const token = localStorage.getItem('token')

    // Not logged in → redirect to login
    if (!token) {
      next('/login')
      return
    }

    // Parse role from stored user (auth store may not be initialized yet in guard)
    const user = getUserFromStorage()

    // Route requires a specific role
    const requiredRole = to.meta.role as string | undefined

    if (requiredRole && user && user.role !== requiredRole && user.role !== 'admin') {
      // Cross-role access → redirect to own dashboard
      if (user.role === 'student') next('/student/dashboard')
      else if (user.role === 'teacher') next('/teacher/dashboard')
      else if (user.role === 'admin') next('/admin/ocr')
      else next('/login')
      return
    }

    // Admin can access anything
    if (user?.role === 'admin') {
      next()
      return
    }

    next()
  })
}

function getUserFromStorage(): { role: string } | null {
  try {
    // Pinia state is stored in memory; reconstruct from localStorage
    // Auth store persists token but user object is in-memory
    // For route guard purposes, we parse role from the stored token
    const token = localStorage.getItem('token')
    if (!token) return null

    // The token is a simple mock string; we can't decode role from it.
    // Instead, pinia-plugin-persistedstate is not used here,
    // so we store role alongside token for guard access.
    const role = localStorage.getItem('userRole')
    return role ? { role } : null
  } catch {
    return null
  }
}

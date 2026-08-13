<template>
  <div class="login-wrapper">
    <!-- Letter Glitch Background -->
    <LetterGlitch class="background-glitch" />

    <!-- Login Form -->
    <div class="form-container">
      <form class="form" @submit.prevent="handleLogin">
        <h2 class="title">智教慧学Agent平台</h2>
        
        <!-- Role Selector -->
        <div class="role-selector">
          <label class="radio-label">
            <input type="radio" v-model="role" value="student" /> Student
          </label>
          <label class="radio-label">
            <input type="radio" v-model="role" value="teacher" /> Teacher
          </label>
          <label class="radio-label">
            <input type="radio" v-model="role" value="admin" /> Admin
          </label>
        </div>

        <span class="input-span">
          <label for="email" class="label">Email</label>
          <input 
            type="email" 
            name="email" 
            id="email" 
            v-model="email" 
            required 
          />
        </span>
        <span class="input-span">
          <label for="password" class="label">Password</label>
          <input 
            type="password" 
            name="password" 
            id="password" 
            v-model="password" 
            required 
          />
        </span>
        <span class="span"><a href="#">Forgot password?</a></span>
        <input class="submit" type="submit" value="Log in" :disabled="loading" />
        <span class="span">Don't have an account? <a href="#">Sign up</a></span>
      </form>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { ElMessage } from 'element-plus'
import LetterGlitch from '@/components/LetterGlitch.vue'
import request from '@/utils/request'

const router = useRouter()
const authStore = useAuthStore()

const email = ref('')
const password = ref('')
const role = ref<'student' | 'teacher' | 'admin'>('student')
const loading = ref(false)

const handleLogin = async () => {
  if (!email.value || !password.value) {
    ElMessage.warning('Email and Password cannot be empty')
    return
  }

  loading.value = true
  try {
    // Admin: mock login (no backend admin table)
    if (role.value === 'admin') {
      if (!email.value.startsWith('admin')) {
        ElMessage.warning('管理员账号必须以 admin 开头')
        loading.value = false
        return
      }
      authStore.setToken('admin-mock-token')
      authStore.setUser({
        id: 0,
        name: email.value.split('@')[0],
        email: email.value,
        gender: null,
        stu_level: null,
        role: 'admin',
      })
      localStorage.setItem('userRole', 'admin')
      ElMessage.success('Logged in as admin')
      await router.push('/admin/ocr')
      return
    }

    const res: any = await request.post('/auth/login', {
      email: email.value,
      password: password.value,
      user_type: role.value,
    })

    console.log('Login response:', res)

    // 保存 token 和用户完整信息（包括从后端返回的姓名和邮箱）
    authStore.setToken(res.access_token)
    authStore.setUser({
      id: res.user_id,
      name: res.user_name || email.value.split('@')[0],
      email: res.user_email || email.value,
      gender: null,
      stu_level: res.stu_level ?? null,
      role: res.user_type,
    })
    // 同步写入 localStorage，供路由守卫读取角色
    localStorage.setItem('userRole', res.user_type)

    ElMessage.success(`Logged in as ${role.value}`)

    // 根据角色跳转到不同的主页面
    if (res.user_type === 'student') {
      await router.push('/student/dashboard')
    } else {
      await router.push('/teacher/dashboard')
    }
  } catch (err: any) {
    const msg = err?.response?.data?.detail || '邮箱或密码错误'
    ElMessage.error(msg)
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.login-wrapper {
  position: relative;
  width: 100vw;
  height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  overflow: hidden;
  background-color: #000;
}

.background-glitch {
  position: absolute;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  z-index: 0;
}

.form-container {
  position: relative;
  z-index: 10;
  background: rgba(255, 255, 255, 0.95);
  padding: 2rem;
  border-radius: 1rem;
  box-shadow: 0 25px 50px -12px rgba(0, 0, 0, 0.5);
  backdrop-filter: blur(10px);
  width: 500px;
}

.title {
  text-align: center;
  margin-bottom: 1rem;
  color: #333;
  font-size: 2.5rem;
  font-weight: bold;
}

.role-selector {
  display: flex;
  justify-content: center;
  gap: 1.5rem;
  margin-bottom:1rem;
}

.radio-label {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  cursor: pointer;
  font-weight: 600;
  color: #555;
  font-size: 1.5rem;
}

/* 引入 template.txt 的样式 */
.form {
  --bg-light: #efefef;
  --bg-dark: #707070;
  --clr: #58bc82;
  --clr-alpha: #9c9c9c60;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 1rem;
  width: 100%;
  max-width: 500px;
}

.form .input-span {
  width: 100%;
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}

.form input[type="email"],
.form input[type="password"] {
  border-radius: 0.5rem;
  padding: 1rem 0.75rem;
  width: 100%;
  border: none;
  display: flex;
  align-items: center;
  gap: 0.5rem;
  background-color: var(--clr-alpha);
  outline: 2px solid var(--bg-dark);
  box-sizing: border-box;
}

.form input[type="email"]:focus,
.form input[type="password"]:focus {
  outline: 2px solid var(--clr);
}

.label {
  align-self: flex-start;
  color: var(--clr);
  font-weight: 600;
  font-size: 1.2rem;
}

.form .submit {
  padding: 1rem 0.75rem;
  width: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 0.5rem;
  border-radius: 3rem;
  background-color: var(--bg-dark);
  color: var(--bg-light);
  border: none;
  cursor: pointer;
  transition: all 300ms;
  font-weight: 600;
  font-size: 1.2rem;
}

.form .submit:hover {
  background-color: var(--clr);
  color: var(--bg-dark);
}

.span {
  text-decoration: none;
  color: var(--bg-dark);
  font-size: 0.9rem;
}

.span a {
  color: var(--clr);
  font-weight: bold;
}
</style>

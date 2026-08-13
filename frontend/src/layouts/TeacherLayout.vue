<template>
  <div class="relative w-screen h-screen overflow-hidden bg-transparent font-sans">
    <!-- 背景特效 -->
    <FloatingLines class="fixed inset-0 z-0" mixBlendMode="normal" />

    <!-- 左上角控制面板切换按钮 -->
    <button 
      @click="toggleMenu"
      class="fixed top-6 left-6 z-50 p-3 rounded-2xl bg-white/60 backdrop-blur-xl border border-white/50 shadow-lg hover:bg-white/90 hover:scale-105 transition-all cursor-pointer flex items-center justify-center group"
      title="控制面板"
    >
      <LayoutGrid class="w-6 h-6 text-gray-700 group-hover:text-blue-500 transition-colors" />
    </button>

    <!-- 右上角退出登录按钮 -->
    <button 
      @click="handleLogout"
      class="fixed top-6 right-6 z-50 p-3 rounded-2xl bg-white/60 backdrop-blur-xl border border-white/50 shadow-lg hover:bg-white/90 hover:scale-105 hover:bg-red-50 transition-all cursor-pointer flex items-center justify-center group"
      title="退出登录"
    >
      <LogOut class="w-6 h-6 text-gray-700 group-hover:text-red-500 transition-colors" />
    </button>

    <!-- 主内容区（子页面渲染处） -->
    <div class="relative z-10 w-full h-full overflow-auto pt-24 px-8 pb-8">
      <router-view />
    </div>

    <!-- Magic Bento 控制面板悬浮层 -->
    <transition name="fade-scale">
      <div 
        v-show="isMenuOpen" 
        class="fixed inset-0 z-40 flex items-center justify-center bg-black/20 backdrop-blur-md"
        @click.self="toggleMenu"
      >
        <div 
          ref="bentoRef"
          class="grid grid-cols-2 grid-rows-2 gap-8 w-[60%] max-w-[1000px] min-w-[600px] aspect-[2/1]"
          @mousemove="handleMouseMove"
        >
          <div 
            v-for="item in menuItems" 
            :key="item.path"
            @click="handleNav(item.path)"
            class="bento-card group"
          >
            <div class="bento-card-inner relative">
              <span class="text-3xl font-bold text-gray-800 tracking-wider group-hover:text-blue-600 transition-colors">
                {{ item.name }}
              </span>
              <!-- 消息提醒红点徽标 -->
              <div v-if="item.name === '互动专区' && unreadCount > 0" class="absolute top-6 right-6 bg-red-500 text-white text-sm font-bold w-8 h-8 flex items-center justify-center rounded-full shadow-md">
                {{ unreadCount }}
              </div>
            </div>
          </div>
        </div>
      </div>
    </transition>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { LayoutGrid, LogOut } from 'lucide-vue-next'
import { ElMessageBox, ElMessage } from 'element-plus'
import FloatingLines from '@/components/FloatingLines.vue'
import { unreadCount } from '@/store/messages'
import { useAuthStore } from '@/stores/auth'

const router = useRouter()
const route = useRoute()
const authStore = useAuthStore()

// 控制面板是否打开的响应式状态
const isMenuOpen = ref(true)

// 当在特定子页面刷新时，可选择自动隐藏面板
onMounted(() => {
  if (route.path !== '/teacher' && route.path !== '/teacher/dashboard') {
    isMenuOpen.value = false
  }
})

// 菜单配置：教师端四大模块
const menuItems = [
  { name: '班级学情仪表盘', path: '/teacher/dashboard' },
  { name: 'AI 助教', path: '/teacher/chat' },
  { name: '互动专区', path: '/teacher/interactive' },
  { name: '学科维护', path: '/teacher/subject' }
]

// 导航跳转逻辑
const handleNav = (path: string) => {
  isMenuOpen.value = false
  router.push(path)
}

// 切换菜单显示/隐藏
const toggleMenu = () => {
  isMenuOpen.value = !isMenuOpen.value
}

// 退出登录逻辑
const handleLogout = () => {
  ElMessageBox.confirm('是否确定退出当前账号？', '退出登录', {
    confirmButtonText: '确定',
    cancelButtonText: '取消',
    type: 'warning',
    customClass: 'logout-confirm-dialog'
  }).then(() => {
    authStore.logout()
    ElMessage({
      type: 'success',
      message: '已成功退出',
    })
    router.push('/login')
  }).catch(() => {
    // 用户取消退出
  })
}

// Magic Bento 鼠标跟踪发光特效逻辑
const bentoRef = ref<HTMLElement | null>(null)
const handleMouseMove = (e: MouseEvent) => {
  if (!bentoRef.value) return
  const cards = bentoRef.value.querySelectorAll('.bento-card') as NodeListOf<HTMLElement>
  for (const card of cards) {
    const rect = card.getBoundingClientRect()
    const x = e.clientX - rect.left
    const y = e.clientY - rect.top
    card.style.setProperty('--mouse-x', `${x}px`)
    card.style.setProperty('--mouse-y', `${y}px`)
  }
}
</script>

<style scoped>
/* 悬浮层过渡动画 */
.fade-scale-enter-active,
.fade-scale-leave-active {
  transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
}
.fade-scale-enter-from,
.fade-scale-leave-to {
  opacity: 0;
  transform: scale(0.95);
}

/* Magic Bento 卡片基础样式 */
.bento-card {
  position: relative;
  background: rgba(255, 255, 255, 0.4);
  border: 1px solid rgba(255, 255, 255, 0.6);
  border-radius: 1.5rem;
  overflow: hidden;
  cursor: pointer;
  box-shadow: 0 8px 32px rgba(0, 0, 0, 0.05);
  transition: transform 0.2s ease, box-shadow 0.2s ease, border-color 0.2s ease;
}

/* 悬浮时的卡片上浮和阴影加深 */
.bento-card:hover {
  transform: translateY(-4px);
  box-shadow: 0 12px 48px rgba(0, 0, 0, 0.15);
  border-color: rgba(255, 255, 255, 0.9);
}

/* 光晕伪元素（鼠标跟踪的核心实现） */
.bento-card::before {
  content: "";
  position: absolute;
  top: 0; left: 0; right: 0; bottom: 0;
  border-radius: inherit;
  opacity: 0;
  transition: opacity 0.3s ease;
  /* 利用 JS 注入的 CSS 变量绘制跟随鼠标的径向渐变 */
  background: radial-gradient(
    400px circle at var(--mouse-x, 50%) var(--mouse-y, 50%),
    rgba(255, 255, 255, 0.9),
    transparent 40%
  );
  z-index: 1;
  pointer-events: none;
}

.bento-card:hover::before {
  opacity: 1;
}

/* 卡片内部内容层（放置文字） */
.bento-card-inner {
  position: relative;
  z-index: 2;
  width: 100%;
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  /* 增加轻微的玻璃质感渐变 */
  background: linear-gradient(135deg, rgba(255,255,255,0.4) 0%, rgba(255,255,255,0.1) 100%);
  backdrop-filter: blur(12px);
}

/* --- 子组件穿透样式 --- */
:deep(.teacher-page) {
  background: transparent !important;
}

:deep(.el-card) {
  background: rgba(255, 255, 255, 0.7) !important;
  backdrop-filter: blur(12px);
  border: 1px solid rgba(255, 255, 255, 0.5) !important;
  box-shadow: 0 4px 12px rgba(0,0,0,0.05) !important;
}

/* 退出登录确认弹窗的毛玻璃背景特效 */
:global(.logout-confirm-dialog) {
  background: rgba(255, 255, 255, 0.6) !important;
  backdrop-filter: blur(12px) !important;
  border: 1px solid rgba(255, 255, 255, 0.5) !important;
  border-radius: 1rem !important;
  box-shadow: 0 8px 32px rgba(0, 0, 0, 0.1) !important;
}
:global(.logout-confirm-dialog .el-message-box__header),
:global(.logout-confirm-dialog .el-message-box__content),
:global(.logout-confirm-dialog .el-message-box__btns) {
  background: transparent !important;
}
</style>

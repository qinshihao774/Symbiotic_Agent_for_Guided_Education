<template>
  <div class="relative w-screen h-screen overflow-hidden bg-transparent font-sans">
    <FloatingLines class="fixed inset-0 z-0" mixBlendMode="normal" />

    <button
      @click="toggleMenu"
      class="fixed top-6 left-6 z-50 p-3 rounded-2xl bg-white/60 backdrop-blur-xl border border-white/50 shadow-lg hover:bg-white/90 hover:scale-105 transition-all cursor-pointer flex items-center justify-center group"
      title="控制面板"
    >
      <LayoutGrid class="w-6 h-6 text-gray-700 group-hover:text-blue-500 transition-colors" />
    </button>

    <button
      @click="handleLogout"
      class="fixed top-6 right-6 z-50 p-3 rounded-2xl bg-white/60 backdrop-blur-xl border border-white/50 shadow-lg hover:bg-red-50 hover:scale-105 transition-all cursor-pointer flex items-center justify-center group"
      title="退出登录"
    >
      <LogOut class="w-6 h-6 text-gray-500 group-hover:text-red-500 transition-colors" />
    </button>

    <div class="relative z-10 w-full h-full overflow-auto pt-24 px-8 pb-8">
      <router-view />
    </div>

    <transition name="fade-scale">
      <div
        v-show="isMenuOpen"
        class="fixed inset-0 z-40 flex items-center justify-center bg-black/20 backdrop-blur-md"
        @click.self="toggleMenu"
      >
        <div
          ref="bentoRef"
          class="grid gap-6 w-[75%] max-w-[1200px] min-w-[800px] aspect-[2/1]"
          :style="{ gridTemplateColumns: `repeat(${gridCols}, 1fr)` }"
          @mousemove="handleMouseMove"
        >
          <div
            v-for="item in menuItems"
            :key="item.path"
            @click="handleNav(item.path)"
            class="bento-card group"
          >
            <div class="bento-card-inner">
              <span class="text-2xl font-bold text-gray-800 tracking-wider group-hover:text-blue-600 transition-colors">
                {{ item.name }}
              </span>
            </div>
          </div>
        </div>
      </div>
    </transition>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { LayoutGrid, LogOut } from 'lucide-vue-next'
import FloatingLines from '@/components/FloatingLines.vue'
import { useAuthStore } from '@/stores/auth'

const router = useRouter()
const route = useRoute()
const authStore = useAuthStore()

const isMenuOpen = ref(true)

onMounted(() => {
  if (route.path !== '/admin') {
    isMenuOpen.value = false
  }
})

const menuItems = [
  { name: '文档解析',   path: '/admin/ocr' },
  { name: '图谱构建',   path: '/admin/kg-pipeline' },
  { name: '学生管理',   path: '/admin/students' },
  { name: '预警面板',   path: '/admin/alerts' },
]

const gridCols = computed(() => {
  const n = menuItems.length
  if (n <= 3) return n
  if (n <= 6) return 3
  return 4
})

const handleNav = (path: string) => {
  isMenuOpen.value = false
  router.push(path)
}

const toggleMenu = () => {
  isMenuOpen.value = !isMenuOpen.value
}

const handleLogout = () => {
  authStore.logout()
  router.push('/login')
}

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
.fade-scale-enter-active,
.fade-scale-leave-active {
  transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
}
.fade-scale-enter-from,
.fade-scale-leave-to {
  opacity: 0;
  transform: scale(0.95);
}

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

.bento-card:hover {
  transform: translateY(-4px);
  box-shadow: 0 12px 48px rgba(0, 0, 0, 0.15);
  border-color: rgba(255, 255, 255, 0.9);
}

.bento-card::before {
  content: "";
  position: absolute;
  top: 0; left: 0; right: 0; bottom: 0;
  border-radius: inherit;
  opacity: 0;
  transition: opacity 0.3s ease;
  background: radial-gradient(
    300px circle at var(--mouse-x, 50%) var(--mouse-y, 50%),
    rgba(255, 255, 255, 0.9),
    transparent 40%
  );
  z-index: 1;
  pointer-events: none;
}

.bento-card:hover::before {
  opacity: 1;
}

.bento-card-inner {
  position: relative;
  z-index: 2;
  width: 100%;
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  background: linear-gradient(135deg, rgba(255,255,255,0.4) 0%, rgba(255,255,255,0.1) 100%);
  backdrop-filter: blur(12px);
}

:deep(.chat-page),
:deep(.kgp-page),
:deep(.ocr-page) {
  background: transparent !important;
}

:deep(.chat-header),
:deep(.chat-messages) {
  background: rgba(255, 255, 255, 0.6) !important;
  backdrop-filter: blur(10px);
}

:deep(.el-card) {
  background: rgba(255, 255, 255, 0.7) !important;
  backdrop-filter: blur(12px);
  border: 1px solid rgba(255, 255, 255, 0.5) !important;
  box-shadow: 0 4px 12px rgba(0,0,0,0.05) !important;
}
</style>

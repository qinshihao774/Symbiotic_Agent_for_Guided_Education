<template>
  <el-aside :width="collapsed ? '64px' : '220px'" class="sidebar-aside">
    <div class="sidebar-header">
      <span v-if="!collapsed" class="sidebar-title">{{ title }}</span>
      <span v-else class="sidebar-title-collapsed">{{ title.charAt(0) }}</span>
    </div>

    <el-menu
      :default-active="activePath"
      :router="true"
      :collapse="collapsed"
      class="sidebar-menu"
      background-color="transparent"
    >
      <el-menu-item
        v-for="item in items"
        :key="item.path"
        :index="item.path"
        class="sidebar-menu-item"
      >
        <el-icon>
          <component :is="iconMap[item.icon]" />
        </el-icon>
        <template #title>
          <span class="menu-item-label">{{ item.label }}</span>
        </template>
      </el-menu-item>
    </el-menu>

    <div class="sidebar-footer">
      <el-button
        text
        class="collapse-btn"
        @click="$emit('toggleCollapse')"
      >
        <el-icon><component :is="collapsed ? PanelLeftOpen : PanelLeftClose" /></el-icon>
      </el-button>
      <el-button
        v-if="!collapsed"
        text
        class="logout-btn"
        @click="handleLogout"
      >
        <el-icon><LogOut /></el-icon>
        <span>退出登录</span>
      </el-button>
      <el-button
        v-else
        text
        class="logout-btn"
        @click="handleLogout"
      >
        <el-icon><LogOut /></el-icon>
      </el-button>
    </div>
  </el-aside>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import {
  LayoutDashboard, GitGraph, PenLine, FileText,
  MessageCircle, Route, Users, Bell, ScanLine,
  Workflow, BookOpen, Bot, FilePlus, ClipboardList,
  LogOut, PanelLeftOpen, PanelLeftClose
} from 'lucide-vue-next'

export interface MenuItem {
  path: string
  label: string
  icon: string
}

const props = defineProps<{
  items: MenuItem[]
  title: string
  collapsed: boolean
}>()

defineEmits<{
  toggleCollapse: []
}>()

const route = useRoute()
const router = useRouter()
const authStore = useAuthStore()

const activePath = computed(() => route.path)

// Map icon names to lucide-vue-next components
const iconMap: Record<string, any> = {
  LayoutDashboard, GitGraph, PenLine, FileText,
  MessageCircle, Route, Users, Bell, ScanLine,
  Workflow, BookOpen, Bot, FilePlus, ClipboardList,
  LogOut
}

function handleLogout() {
  try {
    authStore.logout()
  } finally {
    router.push('/login')
  }
}
</script>

<style scoped>
.sidebar-aside {
  height: 100vh;
  flex-shrink: 0;
  display: flex;
  flex-direction: column;
  background: rgba(255, 255, 255, 0.75);
  backdrop-filter: blur(16px);
  border-right: 1px solid rgba(0, 0, 0, 0.06);
  transition: width 0.3s ease;
  overflow: hidden;
}

.sidebar-header {
  padding: 20px 16px;
  text-align: center;
  border-bottom: 1px solid rgba(0, 0, 0, 0.06);
}

.sidebar-title {
  font-size: 1.05rem;
  font-weight: 700;
  color: #333;
  white-space: nowrap;
}

.sidebar-title-collapsed {
  font-size: 1.2rem;
  font-weight: 700;
  color: #333;
}

.sidebar-menu {
  flex: 1;
  border-right: none;
  padding-top: 8px;
}

.sidebar-menu-item {
  margin: 2px 8px;
  border-radius: 8px;
}

.sidebar-menu-item:hover {
  background: rgba(0, 0, 0, 0.04);
}

.sidebar-menu-item.is-active {
  background: rgba(64, 158, 255, 0.1);
  color: #409eff;
}

.menu-item-label {
  margin-left: 4px;
}

.sidebar-footer {
  padding: 12px;
  border-top: 1px solid rgba(0, 0, 0, 0.06);
  display: flex;
  flex-direction: column;
  gap: 4px;
  align-items: center;
}

.collapse-btn {
  width: 100%;
}

.logout-btn {
  width: 100%;
  justify-content: flex-start;
  gap: 8px;
  color: #999;
}

.logout-btn:hover {
  color: #f56c6c;
}
</style>

<template>
  <div class="chat-page teacher-page h-full flex flex-col bg-transparent">
    <!-- 顶部栏 -->
    <div class="chat-header flex justify-between items-center px-5 py-3 border-b border-gray-200/50 bg-white/60 backdrop-blur-md text-gray-800">
      <h3 class="m-0 text-base font-bold">AI 助教</h3>
      <div class="header-actions flex gap-4 items-center">
        <StarBorder as="div" color="#4ecdc4" speed="4s" class="nav-wrapper rounded-full">
          <GooeyNav 
            :items="navItems"
            v-model="chatMode"
            :particle-count="15"
            :particle-distances="[90, 10]"
            :particle-r="100"
            :animation-time="600"
            :time-variance="300"
            :colors="[1, 2, 3, 1, 2, 3, 1, 4]"
          />
        </StarBorder>
        <StarBorder as="div" color="#f56c6c" speed="4s" class="clear-btn-wrapper">
          <el-button text @click="clearMessages" :disabled="messages.length === 0" class="clear-btn px-4 py-2 bg-[#e5e8e4]">
            清空对话
          </el-button>
        </StarBorder>
      </div>
    </div>

    <div class="flex-1 flex overflow-hidden">
      <!-- 左侧历史对话记录（可展开/收起） -->
      <div class="history-panel w-64 border-r border-gray-200/50 bg-white/40 backdrop-blur-md flex flex-col transition-all duration-300" :class="{ 'w-12': isHistoryCollapsed }">
        <div class="p-2 border-b border-gray-200/50 flex justify-between items-center">
          <span v-if="!isHistoryCollapsed" class="font-bold text-gray-700 text-sm">历史对话记录</span>
          <el-button size="small" circle @click="isHistoryCollapsed = !isHistoryCollapsed">
            <el-icon><component :is="isHistoryCollapsed ? 'ArrowRight' : 'ArrowLeft'" /></el-icon>
          </el-button>
        </div>
        <div v-if="!isHistoryCollapsed" class="flex-1 overflow-y-auto p-2">
          <!-- 历史记录占位 -->
          <div class="text-xs text-gray-500 p-2 hover:bg-white/50 rounded cursor-pointer truncate mb-1">
            如何给差生布置作业...
          </div>
          <div class="text-xs text-gray-500 p-2 hover:bg-white/50 rounded cursor-pointer truncate mb-1">
            生成一份Python期中卷...
          </div>
        </div>
      </div>

      <!-- 右侧对话主面板 -->
      <div class="flex-1 flex flex-col relative">
        <!-- 消息列表 -->
        <div class="chat-messages flex-1 overflow-y-auto p-5" ref="messagesRef">
          <div v-if="messages.length === 0" class="empty-state flex flex-col items-center justify-center h-full text-gray-500">
            <el-icon :size="48" color="#c0c4cc"><ChatDotRound /></el-icon>
            <p class="mt-2 text-sm text-gray-600">我是您的专属 AI 助教，可以帮您解答问题或辅助备课。</p>
            <p class="hint text-xs text-gray-400 mt-1">支持轻度思考、深度思考、以及辅助备课模式</p>
          </div>
          <ChatMessage
            v-for="(msg, i) in messages"
            :key="i"
            :message="msg"
            :loading="loading && i === messages.length - 1"
          />
        </div>

        <!-- 输入框 -->
        <ChatInput :loading="loading" @send="sendMessage" />
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, watch, nextTick } from 'vue'
import { ChatDotRound, ArrowLeft, ArrowRight } from '@element-plus/icons-vue'
import { useChat } from '@/composables/useChat'
import ChatMessage from '@/components/ChatMessage.vue'
import ChatInput from '@/components/ChatInput.vue'
import GooeyNav from '@/components/GooeyNav.vue'
import StarBorder from '@/components/StarBorder.vue'

const { messages, loading, sendMessage, clearMessages, chatMode } = useChat()
const messagesRef = ref<HTMLElement>()
const isHistoryCollapsed = ref(false)

// 教师端模式配置：轻度思考、深度思考、辅助备课
const navItems = [
  { label: '轻度思考', value: 'quick' },
  { label: '深度思考', value: 'deep' },
  { label: '辅助备课', value: 'agent' }
]

// 自动滚动到底部
watch(
  () => messages.value.length,
  async () => {
    await nextTick()
    if (messagesRef.value) {
      messagesRef.value.scrollTop = messagesRef.value.scrollHeight
    }
  },
)
// 流式输出时也要滚动
watch(
  () => messages.value[messages.value.length - 1]?.content,
  async () => {
    await nextTick()
    if (messagesRef.value) {
      messagesRef.value.scrollTop = messagesRef.value.scrollHeight
    }
  },
)
</script>

<style scoped>
.chat-page {
  --color-1: #ff6b6b;
  --color-2: #4ecdc4;
  --color-3: #45b7d1;
  --color-4: #f9ca24;
}

.nav-wrapper :deep(.inner-content) {
  background: #e5e8e4;
  border-radius: 9999px;
}
.clear-btn-wrapper :deep(.inner-content) {
  background: #e5e8e4;
}

/* 自定义滚动条样式 */
.chat-messages::-webkit-scrollbar,
.history-panel .overflow-y-auto::-webkit-scrollbar {
  width: 8px;
}

.chat-messages::-webkit-scrollbar-track,
.history-panel .overflow-y-auto::-webkit-scrollbar-track {
  background: rgba(0, 0, 0, 0.02);
  border-radius: 4px;
}

.chat-messages::-webkit-scrollbar-thumb,
.history-panel .overflow-y-auto::-webkit-scrollbar-thumb {
  background: rgba(0, 0, 0, 0.15);
  border-radius: 4px;
}

.chat-messages::-webkit-scrollbar-thumb:hover,
.history-panel .overflow-y-auto::-webkit-scrollbar-thumb:hover {
  background: rgba(0, 0, 0, 0.25);
}
</style>

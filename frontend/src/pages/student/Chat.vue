<template>
  <div class="chat-page">
    <div class="chat-header">
      <div>
        <h3>AI 助学</h3>
        <span class="mode-description">可查看任务规划、工具调用和知识来源</span>
      </div>
      <div class="header-actions">
        <StarBorder as="div" color="#f56c6c" speed="4s" class="clear-btn-wrapper">
          <el-button text @click="clearMessages" :disabled="messages.length === 0" class="clear-btn">
            清空对话
          </el-button>
        </StarBorder>
      </div>
    </div>

    <div class="chat-body">
      <aside class="conversation-sidebar" :class="{ collapsed: sidebarCollapsed }">
        <div class="sidebar-header">
          <span v-if="!sidebarCollapsed" class="sidebar-title">历史对话</span>
          <el-button
            text
            class="sidebar-toggle"
            :title="sidebarCollapsed ? '展开历史对话' : '收起历史对话'"
            @click="sidebarCollapsed = !sidebarCollapsed"
          >
            <el-icon><component :is="sidebarCollapsed ? ArrowRight : ArrowLeft" /></el-icon>
          </el-button>
        </div>

        <template v-if="!sidebarCollapsed">
          <el-button
            class="new-chat-btn"
            type="primary"
            plain
            :icon="Plus"
            @click="handleNewConversation"
          >
            新建对话
          </el-button>

          <div class="conversation-list" v-loading="conversationsLoading">
            <div v-if="conversations.length === 0 && !conversationsLoading" class="sidebar-empty">
              <p>暂无历史对话</p>
            </div>
            <div
              v-for="conv in conversations"
              :key="conv.conversation_id"
              class="conversation-item"
              :class="{ active: conv.conversation_id === conversationId }"
              @click="handleSelectConversation(conv.conversation_id)"
            >
              <span class="conversation-title" :title="conv.title">{{ conv.title }}</span>
              <span class="conversation-date">{{ formatDate(conv.created_at) }}</span>
              <el-button
                text
                class="conversation-delete"
                :icon="Delete"
                @click.stop="handleDeleteConversation(conv.conversation_id)"
              />
            </div>
          </div>
        </template>
      </aside>

      <div class="messages-shell">
        <div class="chat-messages" ref="messagesRef" @scroll="handleMessagesScroll">
          <div v-if="messages.length === 0" class="empty-state">
            <el-icon :size="48" color="#c0c4cc"><ChatDotRound /></el-icon>
            <p>开始向 AI 助学提问吧！</p>
            <p class="hint">AI 助学将展示任务规划、资料查询和答案生成进度</p>
          </div>
          <ChatMessage
            v-for="msg in messages"
            :key="msg.id"
            :message="msg"
            :loading="loading && msg.id === lastMessageId"
            :suggesting="suggesting && msg.id === lastMessageId && msg.mode === 'agent'"
            @select-question="handleSelectQuestion"
          />
        </div>
        <transition name="jump">
          <button v-if="showJumpToLatest" class="jump-latest" type="button" @click="scrollToLatest(true)">
            返回最新
            <span aria-hidden="true">↓</span>
          </button>
        </transition>
      </div>

      <ChatSubgraphPanel
        :visible="subgraphPanelVisible"
        :hit-nodes="kgHitNodes"
        :active-index="activeKgHitIndex"
        :subgraphs="activeSubgraph"
        :loading="activeSubgraphLoading"
        :error="activeSubgraphError"
        @close="closeSubgraphPanel"
        @open="openSubgraphPanel"
        @select-page="selectKgHitPage"
        @retry="handleRetrySubgraph"
      />
    </div>

    <ChatInput :loading="loading" @send="handleSend" @cancel="cancelCurrentRun" />
  </div>
</template>

<script setup lang="ts">
import { computed, nextTick, onMounted, ref, watch } from 'vue'
import { ChatDotRound, ArrowLeft, ArrowRight, Plus, Delete } from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { useChat } from '@/composables/useChat'
import ChatMessage from '@/components/ChatMessage.vue'
import ChatInput from '@/components/ChatInput.vue'
import StarBorder from '@/components/StarBorder.vue'
import ChatSubgraphPanel from '@/components/ChatSubgraphPanel.vue'
import type { SuggestedQuestion } from '@/api/ai'

const {
  messages,
  loading,
  sendMessage,
  cancelCurrentRun,
  clearMessages,
  kgHitNodes,
  activeKgHitIndex,
  subgraphPanelVisible,
  closeSubgraphPanel,
  openSubgraphPanel,
  selectKgHitPage,
  subgraphs,
  subgraphLoading,
  subgraphErrors,
  extractSubgraphs,
  suggesting,
  selectSuggestedQuestion,
  conversationId,
  conversations,
  conversationsLoading,
  loadConversations,
  loadConversation,
  newConversation,
  deleteConversationById,
} = useChat()

const messagesRef = ref<HTMLElement>()
const nearBottom = ref(true)
const showJumpToLatest = ref(false)
const sidebarCollapsed = ref(false)
const lastMessageId = computed(() => messages.value[messages.value.length - 1]?.id)
const activeSubgraph = computed(() => subgraphs.value[activeKgHitIndex.value] ?? null)
const activeSubgraphLoading = computed(() => subgraphLoading.value[activeKgHitIndex.value] ?? false)
const activeSubgraphError = computed(() => subgraphErrors.value[activeKgHitIndex.value] ?? null)

function formatDate(value: string): string {
  if (!value) return ''
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return ''
  const y = date.getFullYear()
  const m = String(date.getMonth() + 1).padStart(2, '0')
  const d = String(date.getDate()).padStart(2, '0')
  return `${y}-${m}-${d}`
}

onMounted(() => {
  loadConversations()
})

function handleSelectQuestion(question: SuggestedQuestion) {
  nearBottom.value = true
  showJumpToLatest.value = false
  selectSuggestedQuestion(question)
}

function handleSend(content: string) {
  nearBottom.value = true
  showJumpToLatest.value = false
  sendMessage(content)
  scrollToLatest(true)
}

function handleNewConversation() {
  newConversation()
  nearBottom.value = true
  showJumpToLatest.value = false
}

function handleSelectConversation(id: number) {
  if (id === conversationId.value) return
  loadConversation(id)
  nearBottom.value = true
  showJumpToLatest.value = false
}

async function handleDeleteConversation(id: number) {
  try {
    await ElMessageBox.confirm('确定删除这段历史对话吗？删除后不可恢复。', '删除对话', {
      confirmButtonText: '删除',
      cancelButtonText: '取消',
      type: 'warning',
    })
  } catch {
    return
  }
  await deleteConversationById(id)
  ElMessage.success('对话已删除')
}

function handleRetrySubgraph() {
  const hitNode = kgHitNodes.value[activeKgHitIndex.value]
  if (hitNode) extractSubgraphs(hitNode, activeKgHitIndex.value)
}

function handleMessagesScroll() {
  const element = messagesRef.value
  if (!element) return
  const distanceToBottom = element.scrollHeight - element.scrollTop - element.clientHeight
  nearBottom.value = distanceToBottom < 96
  if (nearBottom.value) showJumpToLatest.value = false
}

async function scrollToLatest(force = false) {
  await nextTick()
  const element = messagesRef.value
  if (!element) return
  if (!force && !nearBottom.value) {
    showJumpToLatest.value = true
    return
  }
  element.scrollTo({ top: element.scrollHeight, behavior: force ? 'smooth' : 'auto' })
  nearBottom.value = true
  showJumpToLatest.value = false
}

watch(
  () => messages.value.length,
  () => scrollToLatest(),
)

watch(
  () => {
    const last = messages.value[messages.value.length - 1]
    return [
      last?.content.length || 0,
      last?.agentRun?.steps.length || 0,
      last?.agentRun?.steps.map(step => step.status).join(',') || '',
      last?.suggestedQuestions?.length || 0,
    ]
  },
  () => scrollToLatest(),
)
</script>

<style scoped>
.chat-page {
  height: 100%;
  display: flex;
  flex-direction: column;
  background: transparent;
}
.chat-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px 20px;
  border-bottom: 1px solid rgba(0, 0, 0, 0.05);
  background: rgba(255, 255, 255, 0.6);
  backdrop-filter: blur(10px);
  color: #1f2937;
}
.chat-header h3 { margin: 0; font-size: 16px; }
.mode-description { display: block; margin-top: 2px; color: #94a3b8; font-size: 11px; }
.header-actions { display: flex; gap: 16px; align-items: center; }
.clear-btn { margin-left: 0; padding: 8px 16px; }
.clear-btn-wrapper :deep(.inner-content) { background: #e5e8e4; }
.chat-body { display: flex; flex: 1; min-height: 0; overflow: hidden; }
.conversation-sidebar {
  width: 260px;
  flex-shrink: 0;
  display: flex;
  flex-direction: column;
  border-right: 1px solid rgba(0, 0, 0, 0.05);
  background: rgba(255, 255, 255, 0.6);
  backdrop-filter: blur(10px);
  transition: width 0.2s ease;
  overflow: hidden;
}
.conversation-sidebar.collapsed {
  width: 48px;
  border-right: 1px solid rgba(0, 0, 0, 0.05);
}
.sidebar-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px 12px 8px;
  min-height: 44px;
}
.sidebar-title {
  font-size: 14px;
  font-weight: 600;
  color: #1f2937;
  white-space: nowrap;
}
.sidebar-toggle { padding: 6px; color: #64748b; }
.sidebar-toggle:hover { color: #1f2937; }
.new-chat-btn {
  margin: 0 12px 10px;
  width: calc(100% - 24px);
}
.conversation-list {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
  padding: 0 8px 12px;
}
.conversation-list::-webkit-scrollbar { width: 6px; }
.conversation-list::-webkit-scrollbar-track { background: transparent; }
.conversation-list::-webkit-scrollbar-thumb { background: rgba(0, 0, 0, 0.12); border-radius: 3px; }
.conversation-list::-webkit-scrollbar-thumb:hover { background: rgba(0, 0, 0, 0.22); }
.sidebar-empty { padding: 24px 8px; text-align: center; color: #9ca3af; font-size: 12px; }
.sidebar-empty p { margin: 0; }
.conversation-item {
  display: flex;
  align-items: center;
  gap: 4px;
  padding: 8px 10px;
  margin-bottom: 2px;
  border-radius: 8px;
  cursor: pointer;
  transition: background 0.15s ease;
}
.conversation-item:hover { background: rgba(0, 0, 0, 0.04); }
.conversation-item.active { background: rgba(64, 158, 255, 0.12); }
.conversation-title {
  flex: 1;
  min-width: 0;
  font-size: 13px;
  color: #374151;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.conversation-item.active .conversation-title { color: #1f6feb; font-weight: 500; }
.conversation-date {
  flex-shrink: 0;
  font-size: 11px;
  color: #9ca3af;
  white-space: nowrap;
}
.conversation-delete {
  flex-shrink: 0;
  padding: 4px;
  color: #9ca3af;
  opacity: 0;
  transition: opacity 0.15s ease;
}
.conversation-item:hover .conversation-delete { opacity: 1; }
.conversation-delete:hover { color: #f56c6c; }
.messages-shell { position: relative; flex: 1; min-width: 0; }
.chat-messages { height: 100%; overflow-y: auto; padding: 20px; box-sizing: border-box; scroll-behavior: smooth; }
.chat-messages::-webkit-scrollbar { width: 8px; }
.chat-messages::-webkit-scrollbar-track { background: rgba(0, 0, 0, 0.02); border-radius: 4px; }
.chat-messages::-webkit-scrollbar-thumb { background: rgba(0, 0, 0, 0.15); border-radius: 4px; }
.chat-messages::-webkit-scrollbar-thumb:hover { background: rgba(0, 0, 0, 0.25); }
.empty-state { display: flex; flex-direction: column; align-items: center; justify-content: center; height: 100%; color: #6b7280; }
.empty-state p { margin: 8px 0 0; font-size: 14px; color: #4b5563; }
.hint { font-size: 12px !important; color: #9ca3af !important; }
.jump-latest {
  position: absolute;
  left: 50%;
  bottom: 18px;
  transform: translateX(-50%);
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 7px 12px;
  border: 1px solid #dbe3ec;
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.96);
  color: #475569;
  box-shadow: 0 8px 24px rgba(15, 23, 42, 0.12);
  cursor: pointer;
  font-size: 12px;
}
.jump-enter-active, .jump-leave-active { transition: opacity 0.18s ease, transform 0.18s ease; }
.jump-enter-from, .jump-leave-to { opacity: 0; transform: translate(-50%, 8px); }
@media (max-width: 800px) {
  .chat-header { align-items: flex-start; gap: 8px; }
  .header-actions { gap: 8px; }
  .mode-description { display: none; }
  .chat-messages { padding: 14px 10px; }
}
@media (prefers-reduced-motion: reduce) {
  .chat-messages { scroll-behavior: auto; }
  .jump-enter-active, .jump-leave-active { transition: none; }
}
</style>

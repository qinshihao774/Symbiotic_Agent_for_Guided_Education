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
import { computed, nextTick, ref, watch } from 'vue'
import { ChatDotRound } from '@element-plus/icons-vue'
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
} = useChat()

const messagesRef = ref<HTMLElement>()
const nearBottom = ref(true)
const showJumpToLatest = ref(false)
const lastMessageId = computed(() => messages.value[messages.value.length - 1]?.id)
const activeSubgraph = computed(() => subgraphs.value[activeKgHitIndex.value] ?? null)
const activeSubgraphLoading = computed(() => subgraphLoading.value[activeKgHitIndex.value] ?? false)
const activeSubgraphError = computed(() => subgraphErrors.value[activeKgHitIndex.value] ?? null)

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

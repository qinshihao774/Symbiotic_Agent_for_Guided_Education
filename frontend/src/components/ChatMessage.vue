<template>
  <div class="chat-message" :class="message.role">
    <div class="avatar">
      <el-icon v-if="message.role === 'user'" :size="20"><User /></el-icon>
      <el-icon v-else :size="20"><Monitor /></el-icon>
    </div>
    <div class="bubble" :class="{ 'agent-bubble': message.mode === 'agent' }">
      <div
        v-if="loading && message.role === 'assistant' && message.mode !== 'agent' && !message.content && !message.reasoning"
        class="typing"
      >
        <span class="dot" /><span class="dot" /><span class="dot" />
      </div>
      <template v-else>
        <AgentRunPanel
          v-if="message.mode === 'agent' && message.agentRun"
          :run="message.agentRun"
        />

        <div v-if="message.mode !== 'agent' && message.reasoning" class="reasoning-section">
          <button class="reasoning-header" type="button" @click="toggleReasoning">
            <el-icon :size="14">
              <ArrowRight v-if="!showReasoning" />
              <ArrowDown v-else />
            </el-icon>
            <span>分析过程</span>
            <span v-if="isThinking" class="thinking-indicator">分析中...</span>
          </button>
          <div v-show="showReasoning" class="reasoning-content">
            <pre>{{ message.reasoning }}</pre>
          </div>
        </div>

        <div v-if="message.content" class="markdown-body" v-html="renderedContent" />

        <div v-if="suggesting && !message.suggestedQuestions?.length" class="suggesting-dots">
          <span class="suggesting-text">正在生成后续学习建议</span>
          <span class="dot dot-1">·</span>
          <span class="dot dot-2">·</span>
          <span class="dot dot-3">·</span>
        </div>

        <KnowledgeCard
          v-if="message.suggestedQuestions?.length"
          :questions="message.suggestedQuestions"
          @select="$emit('selectQuestion', $event)"
        />
      </template>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { User, Monitor, ArrowRight, ArrowDown } from '@element-plus/icons-vue'
import { marked } from 'marked'
import katex from 'katex'
import type { ChatMessage } from '@/composables/useChat'
import type { SuggestedQuestion } from '@/api/ai'
import KnowledgeCard from './KnowledgeCard.vue'
import AgentRunPanel from './chat/AgentRunPanel.vue'

const props = defineProps<{
  message: ChatMessage
  loading?: boolean
  suggesting?: boolean
}>()

defineEmits<{
  selectQuestion: [question: SuggestedQuestion]
}>()

const showReasoning = ref(true)
const userToggled = ref(false)
const isThinking = computed(() =>
  props.message.mode !== 'agent' && props.loading && !!props.message.reasoning && !props.message.content,
)
const thinkingDone = computed(() =>
  props.message.mode !== 'agent' && !!props.message.reasoning && !!props.message.content,
)

watch(isThinking, value => {
  if (value && !userToggled.value) showReasoning.value = true
})
watch(thinkingDone, value => {
  if (value && !userToggled.value) showReasoning.value = false
})

function toggleReasoning() {
  userToggled.value = true
  showReasoning.value = !showReasoning.value
}

function renderMarkdown(content: string): string {
  const result = marked.parse(content, { breaks: true, gfm: true })
  return typeof result === 'string' ? result : ''
}

function renderMath(text: string): string {
  text = text.replace(/\$\$([\s\S]+?)\$\$/g, (_, math) => {
    try {
      return katex.renderToString(math.trim(), { displayMode: true, throwOnError: false })
    } catch {
      return `$$${math}$$`
    }
  })
  return text.replace(/\$([^\$\n]+?)\$/g, (_, math) => {
    try {
      return katex.renderToString(math.trim(), { displayMode: false, throwOnError: false })
    } catch {
      return `$${math}$`
    }
  })
}

const renderedContent = computed(() => renderMath(renderMarkdown(props.message.content || '')))
</script>

<style scoped>
.chat-message { display: flex; gap: 12px; margin-bottom: 16px; }
.chat-message.user { flex-direction: row-reverse; }
.avatar {
  width: 36px;
  height: 36px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}
.chat-message.user .avatar { background: #409eff; color: #fff; }
.chat-message.assistant .avatar { background: #e4e7ed; color: #606266; }
.bubble {
  max-width: 70%;
  padding: 12px 16px;
  border-radius: 12px;
  line-height: 1.6;
  font-size: 14px;
  word-break: break-word;
}
.bubble.agent-bubble { width: min(760px, 82%); max-width: 82%; }
.chat-message.user .bubble { background: #409eff; color: #fff; border-top-right-radius: 4px; }
.chat-message.assistant .bubble { background: #f4f4f5; color: #303133; border-top-left-radius: 4px; }
.typing { display: flex; gap: 4px; padding: 4px 0; }
.typing .dot { width: 8px; height: 8px; border-radius: 50%; background: #c0c4cc; animation: bounce 1.4s infinite ease-in-out; }
.typing .dot:nth-child(1) { animation-delay: -0.32s; }
.typing .dot:nth-child(2) { animation-delay: -0.16s; }
@keyframes bounce { 0%, 80%, 100% { transform: scale(0); } 40% { transform: scale(1); } }

.reasoning-section { margin-bottom: 12px; border: 1px solid #dcdfe6; border-radius: 8px; background: #fafafa; }
.reasoning-header {
  width: 100%;
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 12px;
  border: 0;
  background: transparent;
  cursor: pointer;
  font-size: 13px;
  color: #909399;
  font-weight: 500;
}
.reasoning-header:hover { background: #f5f7fa; }
.thinking-indicator { font-size: 12px; color: #909399; animation: pulse 1.5s ease-in-out infinite; }
.reasoning-content { padding: 0 12px 12px; }
.reasoning-content pre {
  margin: 0;
  padding: 10px;
  background: #f5f7fa;
  border-radius: 4px;
  font-size: 13px;
  line-height: 1.5;
  color: #606266;
  white-space: pre-wrap;
  max-height: 400px;
  overflow-y: auto;
}
@keyframes pulse { 50% { opacity: 0.4; } }

.markdown-body :deep(h1), .markdown-body :deep(h2), .markdown-body :deep(h3), .markdown-body :deep(h4) { margin: 12px 0 8px; font-weight: 600; }
.markdown-body :deep(h1) { font-size: 1.4em; }
.markdown-body :deep(h2) { font-size: 1.2em; }
.markdown-body :deep(h3) { font-size: 1.1em; }
.markdown-body :deep(p) { margin: 8px 0; }
.markdown-body :deep(ul), .markdown-body :deep(ol) { padding-left: 20px; margin: 8px 0; }
.markdown-body :deep(li) { margin: 4px 0; }
.markdown-body :deep(code) { background: #e8e8e8; padding: 2px 6px; border-radius: 4px; font-family: Consolas, Monaco, monospace; font-size: 0.9em; }
.markdown-body :deep(pre) { background: #1e1e1e; color: #d4d4d4; padding: 12px; border-radius: 8px; overflow-x: auto; margin: 8px 0; }
.markdown-body :deep(pre code) { background: none; padding: 0; color: inherit; font-size: 0.85em; }
.markdown-body :deep(blockquote) { border-left: 4px solid #409eff; padding-left: 12px; margin: 8px 0; color: #606266; }
.markdown-body :deep(table) { border-collapse: collapse; margin: 8px 0; width: 100%; }
.markdown-body :deep(th), .markdown-body :deep(td) { border: 1px solid #e4e7ed; padding: 8px 12px; text-align: left; }
.markdown-body :deep(th) { background: #f5f7fa; font-weight: 600; }
.markdown-body :deep(a) { color: #409eff; text-decoration: none; }
.markdown-body :deep(a:hover) { text-decoration: underline; }
.markdown-body :deep(.katex-display) { margin: 8px 0; overflow-x: auto; }

.suggesting-dots { display: flex; align-items: center; gap: 2px; margin-top: 12px; padding: 8px 0; }
.suggesting-text { font-size: 13px; color: #94a3b8; margin-right: 4px; }
.suggesting-dots .dot { font-size: 20px; color: #94a3b8; animation: dot-pulse 1.4s infinite ease-in-out; }
.dot-2 { animation-delay: 0.2s; }
.dot-3 { animation-delay: 0.4s; }
@keyframes dot-pulse { 0%, 80%, 100% { opacity: 0.3; transform: scale(0.8); } 40% { opacity: 1; transform: scale(1.2); } }
@media (prefers-reduced-motion: reduce) {
  .typing .dot, .thinking-indicator, .suggesting-dots .dot { animation: none; }
}
</style>

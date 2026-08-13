<template>
  <section class="agent-run" :class="run.status" aria-label="智能体执行过程">
    <button class="run-header" type="button" @click="togglePanel" :aria-expanded="expanded">
      <div class="run-heading">
        <AgentStatusIcon :status="runStatus" />
        <div>
          <div class="run-title">{{ runTitle }}</div>
          <div class="run-subtitle">{{ runSubtitle }}</div>
        </div>
      </div>
      <span class="expand-icon" :class="{ expanded }">⌄</span>
    </button>

    <transition name="panel">
      <div v-if="expanded" class="run-body" aria-live="polite">
        <AgentStepItem
          v-for="(step, index) in run.steps"
          :key="step.id"
          :step="step"
          :last="index === run.steps.length - 1"
        />
      </div>
    </transition>
  </section>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import type { AgentRun, AgentStepStatus } from '@/types/agent'
import AgentStatusIcon from './AgentStatusIcon.vue'
import AgentStepItem from './AgentStepItem.vue'

const props = defineProps<{ run: AgentRun }>()
const expanded = ref(props.run.status === 'running')
const userToggled = ref(false)

const runStatus = computed<AgentStepStatus>(() => {
  if (props.run.status === 'success') return 'success'
  if (props.run.status === 'failed') return 'failed'
  if (props.run.status === 'cancelled') return 'cancelled'
  return 'running'
})

const runTitle = computed(() => ({
  running: '智能体正在执行',
  success: '执行完成',
  failed: '执行失败',
  cancelled: '执行已取消',
}[props.run.status]))

const runSubtitle = computed(() => {
  if (props.run.status === 'running') {
    return props.run.steps.find(step => step.status === 'running')?.title || props.run.summary || '正在处理'
  }
  const duration = props.run.durationMs !== undefined ? ` · ${formatDuration(props.run.durationMs)}` : ''
  return `${props.run.steps.length} 个步骤${duration}`
})

watch(() => props.run.status, status => {
  if (userToggled.value) return
  expanded.value = status === 'running' || status === 'failed'
})

function togglePanel() {
  userToggled.value = true
  expanded.value = !expanded.value
}

function formatDuration(milliseconds: number): string {
  if (milliseconds < 1000) return `${milliseconds}ms`
  return `${(milliseconds / 1000).toFixed(milliseconds < 10000 ? 1 : 0)}s`
}
</script>

<style scoped>
.agent-run {
  margin-bottom: 12px;
  border: 1px solid #dbe3ec;
  border-radius: 12px;
  background: rgba(255, 255, 255, 0.82);
  overflow: hidden;
}
.agent-run.failed { border-color: #fecaca; }
.run-header {
  width: 100%;
  padding: 10px 12px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  border: 0;
  background: transparent;
  cursor: pointer;
  text-align: left;
  font: inherit;
}
.run-header:hover { background: #f8fafc; }
.run-heading { display: flex; align-items: center; gap: 9px; min-width: 0; }
.run-title { color: #334155; font-size: 13px; font-weight: 600; }
.run-subtitle { margin-top: 1px; color: #94a3b8; font-size: 11px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.expand-icon { color: #94a3b8; font-size: 17px; transition: transform 0.2s ease; }
.expand-icon.expanded { transform: rotate(180deg); }
.run-body { padding: 6px 12px 4px; border-top: 1px solid #eef2f7; }
.panel-enter-active, .panel-leave-active { transition: opacity 0.18s ease; }
.panel-enter-from, .panel-leave-to { opacity: 0; }
@media (prefers-reduced-motion: reduce) {
  .expand-icon, .panel-enter-active, .panel-leave-active { transition: none; }
}
</style>

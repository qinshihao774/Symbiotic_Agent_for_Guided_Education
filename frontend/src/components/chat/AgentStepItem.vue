<template>
  <div class="step-item" :class="step.status">
    <div class="timeline-column">
      <AgentStatusIcon :status="step.status" />
      <span v-if="!last" class="timeline-line" />
    </div>
    <div class="step-main">
      <button class="step-header" type="button" @click="expanded = !expanded" :aria-expanded="expanded">
        <span class="step-copy">
          <span class="step-title">{{ step.title }}</span>
          <span v-if="step.status === 'running'" class="running-label">正在执行</span>
        </span>
        <span class="step-meta">
          <span v-if="step.durationMs !== undefined">{{ formatDuration(step.durationMs) }}</span>
          <span v-if="hasDetails" class="chevron" :class="{ expanded }">⌄</span>
        </span>
      </button>
      <div v-if="expanded && hasDetails" class="step-details">
        <p v-if="step.description" class="description">{{ step.description }}</p>
        <AgentToolDetails v-if="step.tool" :tool="step.tool" />
        <div v-if="step.error" class="error-message">
          {{ step.error.message }}
          <span v-if="step.error.retryable">，可以稍后重试</span>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import type { AgentStep } from '@/types/agent'
import AgentStatusIcon from './AgentStatusIcon.vue'
import AgentToolDetails from './AgentToolDetails.vue'

const props = defineProps<{ step: AgentStep; last: boolean }>()
const expanded = ref(props.step.status === 'running' || props.step.status === 'failed')
const hasDetails = computed(() => !!(props.step.description || props.step.tool || props.step.error))

watch(() => props.step.status, status => {
  if (status === 'running' || status === 'failed') expanded.value = true
  else if (status === 'success') expanded.value = Boolean(props.step.tool?.documentExcerpt)
})

function formatDuration(milliseconds: number): string {
  if (milliseconds < 1000) return `${milliseconds}ms`
  return `${(milliseconds / 1000).toFixed(milliseconds < 10000 ? 1 : 0)}s`
}
</script>

<style scoped>
.step-item { display: flex; min-height: 42px; }
.timeline-column { width: 24px; display: flex; flex-direction: column; align-items: center; flex-shrink: 0; }
.timeline-line { width: 1px; flex: 1; min-height: 18px; margin: 3px 0; background: #dbe3ec; }
.step-main { flex: 1; min-width: 0; padding: 0 0 8px 8px; }
.step-header {
  width: 100%;
  min-height: 24px;
  padding: 0;
  border: 0;
  background: none;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  text-align: left;
  cursor: pointer;
  color: inherit;
  font: inherit;
}
.step-copy { min-width: 0; display: flex; align-items: center; gap: 8px; }
.step-title { font-size: 13px; font-weight: 600; color: #334155; }
.running-label { font-size: 11px; color: #2563eb; animation: agent-pulse 1.5s ease-in-out infinite; }
.step-meta { display: flex; align-items: center; gap: 8px; color: #94a3b8; font-size: 11px; flex-shrink: 0; }
.chevron { display: inline-block; transition: transform 0.2s ease; font-size: 15px; }
.chevron.expanded { transform: rotate(180deg); }
.step-details { padding: 4px 0 4px; }
.description { margin: 0; color: #64748b; font-size: 12px; line-height: 1.5; }
.error-message { margin-top: 7px; padding: 8px 10px; border-radius: 7px; background: #fef2f2; color: #b91c1c; font-size: 12px; }
@keyframes agent-pulse { 50% { opacity: 0.45; } }
@media (prefers-reduced-motion: reduce) {
  .running-label { animation: none; }
  .chevron { transition: none; }
}
</style>

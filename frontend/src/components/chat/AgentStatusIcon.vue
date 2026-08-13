<template>
  <span class="status-icon" :class="status" :aria-label="statusLabel" role="img">
    <span v-if="status === 'running'" class="spinner" />
    <span v-else-if="status === 'success'">✓</span>
    <span v-else-if="status === 'failed'">!</span>
    <span v-else-if="status === 'cancelled'">■</span>
    <span v-else>·</span>
  </span>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import type { AgentStepStatus } from '@/types/agent'

const props = defineProps<{ status: AgentStepStatus }>()

const statusLabel = computed(() => ({
  pending: '等待执行',
  running: '正在执行',
  success: '执行成功',
  failed: '执行失败',
  cancelled: '已取消',
}[props.status]))
</script>

<style scoped>
.status-icon {
  width: 20px;
  height: 20px;
  border-radius: 50%;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  box-sizing: border-box;
  flex-shrink: 0;
  font-size: 12px;
  font-weight: 700;
  background: #f1f5f9;
  color: #94a3b8;
  border: 1px solid #cbd5e1;
}
.status-icon.running { color: #2563eb; border-color: #93c5fd; background: #eff6ff; }
.status-icon.success { color: #15803d; border-color: #86efac; background: #f0fdf4; }
.status-icon.failed { color: #dc2626; border-color: #fca5a5; background: #fef2f2; }
.status-icon.cancelled { color: #64748b; border-color: #cbd5e1; background: #f8fafc; }
.spinner {
  width: 10px;
  height: 10px;
  border: 2px solid #bfdbfe;
  border-top-color: #2563eb;
  border-radius: 50%;
  animation: agent-spin 0.8s linear infinite;
}
@keyframes agent-spin { to { transform: rotate(360deg); } }
@media (prefers-reduced-motion: reduce) {
  .spinner { animation: none; border-color: #2563eb; }
}
</style>

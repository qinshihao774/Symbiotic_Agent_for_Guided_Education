<template>
  <div class="tool-details">
    <p v-if="tool.purpose" class="purpose">{{ tool.purpose }}</p>
    <dl v-if="tool.inputSummary?.length" class="detail-list">
      <template v-for="field in tool.inputSummary" :key="field.label">
        <dt>{{ field.label }}</dt>
        <dd>{{ field.value }}</dd>
      </template>
    </dl>
    <div v-if="tool.resultSummary" class="result-summary">
      <span class="result-label">结果</span>
      <span>{{ tool.resultSummary }}</span>
    </div>
    <div v-if="tool.documentExcerpt" class="document-excerpt">
      <span class="excerpt-label">教材原文</span>
      <pre>{{ tool.documentExcerpt }}</pre>
    </div>
  </div>
</template>

<script setup lang="ts">
import type { AgentToolPresentation } from '@/types/agent'

defineProps<{ tool: AgentToolPresentation }>()
</script>

<style scoped>
.tool-details {
  margin-top: 8px;
  padding: 10px 12px;
  border-radius: 8px;
  background: #f8fafc;
  border: 1px solid #e2e8f0;
  color: #475569;
  font-size: 12px;
}
.purpose { margin: 0 0 8px; line-height: 1.5; }
.detail-list {
  display: grid;
  grid-template-columns: max-content 1fr;
  gap: 4px 10px;
  margin: 0;
}
.detail-list dt { color: #94a3b8; }
.detail-list dd { margin: 0; color: #334155; word-break: break-word; }
.result-summary {
  display: flex;
  gap: 10px;
  margin-top: 8px;
  padding-top: 8px;
  border-top: 1px solid #e2e8f0;
}
.result-label { color: #94a3b8; flex-shrink: 0; }
.document-excerpt {
  margin-top: 8px;
  padding-top: 8px;
  border-top: 1px solid #e2e8f0;
}
.excerpt-label { display: block; margin-bottom: 6px; color: #94a3b8; }
.document-excerpt pre {
  max-height: 320px;
  margin: 0;
  padding: 8px 10px;
  overflow: auto;
  border-radius: 6px;
  background: #fff;
  color: #334155;
  font: inherit;
  line-height: 1.65;
  white-space: pre-wrap;
  word-break: break-word;
}
</style>

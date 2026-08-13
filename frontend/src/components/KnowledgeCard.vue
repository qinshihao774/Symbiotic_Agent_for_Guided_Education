<template>
  <div class="knowledge-cards">
    <div class="cards-header">
      <span class="cards-icon">💡</span>
      <span class="cards-title">你接下来想要了解什么？</span>
    </div>
    <div class="cards-list">
      <div
        v-for="question in questions"
        :key="question.node_id"
        class="knowledge-card"
        :class="`relation-${question.relation}`"
        @click="$emit('select', question)"
      >
        <span class="card-dot" :style="{ backgroundColor: relationColor(question.relation) }"></span>
        <span class="card-text">{{ question.text }}</span>
        <el-icon class="card-arrow"><ArrowRight /></el-icon>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ArrowRight } from '@element-plus/icons-vue'
import type { SuggestedQuestion } from '@/api/ai'
import { TYPE_COLORS } from '@/constants/knowledgeColors'

defineProps<{
  questions: SuggestedQuestion[]
}>()

defineEmits<{
  select: [question: SuggestedQuestion]
}>()

const RELATION_COLORS: Record<string, string> = {
  upstream: '#7C3AED',   // 紫色 — 前置知识
  downstream: '#10B981', // 绿色 — 后续知识
  both: '#06B6D4',       // 青色 — 双向关联
}

function relationColor(relation: string): string {
  return RELATION_COLORS[relation] || TYPE_COLORS['Term'] || '#94A3B8'
}
</script>

<style scoped>
.knowledge-cards {
  margin-top: 12px;
  padding: 12px 16px;
  background: linear-gradient(135deg, #f8f9ff 0%, #f0f4ff 100%);
  border-radius: 12px;
  border: 1px solid #e2e8f0;
}

.cards-header {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-bottom: 10px;
}

.cards-icon {
  font-size: 16px;
}

.cards-title {
  font-size: 13px;
  color: #64748b;
  font-weight: 500;
}

.cards-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.knowledge-card {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 14px;
  background: #ffffff;
  border-radius: 8px;
  border: 1px solid #e2e8f0;
  cursor: pointer;
  transition: all 0.2s ease;
}

.knowledge-card:hover {
  transform: translateY(-1px);
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.08);
  border-color: #cbd5e1;
}

.knowledge-card:active {
  transform: translateY(0);
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.06);
}

.card-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  flex-shrink: 0;
}

.card-text {
  flex: 1;
  font-size: 14px;
  color: #334155;
  line-height: 1.5;
}

.card-arrow {
  color: #94a3b8;
  font-size: 14px;
  flex-shrink: 0;
  transition: color 0.2s;
}

.knowledge-card:hover .card-arrow {
  color: #64748b;
}
</style>

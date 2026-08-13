<template>
  <transition name="slide">
    <div v-if="node" class="detail-panel">
      <div class="panel-header">
        <h3>{{ node.name }}</h3>
        <el-tag :color="typeColor" effect="dark" size="small">{{ node.type }}</el-tag>
        <el-button class="close-btn" :icon="Close" text @click="$emit('close')" />
      </div>
      <div class="panel-body">
        <p class="description">{{ node.description || '暂无描述' }}</p>

        <div class="mastery-section">
          <div class="mastery-heading">
            <span>掌握度</span>
            <strong>{{ masteryPercentage }}%</strong>
          </div>
          <el-progress
            :percentage="masteryPercentage"
            :stroke-width="10"
            :show-text="false"
            color="#38BDF8"
          />
        </div>

        <div class="section">
          <h4>关系</h4>
          <div v-if="relations.length" class="relation-list">
            <div v-for="rel in relations" :key="`${rel.source}-${rel.target}-${rel.name}`"
                 class="relation-item">
              <span class="rel-direction">{{ rel.direction }}</span>
              <span class="rel-node">{{ rel.targetName }}</span>
              <span class="rel-name">{{ rel.name }}</span>
            </div>
          </div>
          <el-empty v-else description="暂无关联关系" :image-size="40" />
        </div>

        <div class="section">
          <h4>属性</h4>
          <div class="attr-list">
            <div class="attr-item">
              <span class="attr-key">Degree</span>
              <span class="attr-value">{{ node.degree }}</span>
            </div>
            <div class="attr-item">
              <span class="attr-key">ID</span>
              <span class="attr-value">{{ node.id }}</span>
            </div>
          </div>
        </div>

        <div v-if="canPractice" class="practice-section">
          <el-button
            type="primary"
            plain
            class="practice-button"
            @click="$emit('practice')"
          >
            查看关联题目
          </el-button>
          <p class="practice-hint">查看与“{{ node.name }}”关联的题目合集</p>
        </div>
      </div>
    </div>
  </transition>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { Close } from '@element-plus/icons-vue'
import type { GraphNode, GraphEdge } from '@/api/knowledge'
import { useKnowledgeStore } from '@/stores/knowledge'

const props = defineProps<{
  node: GraphNode
  relationNodeIds?: Set<string>
  courseId?: number | null
}>()

defineEmits<{ close: []; practice: [] }>()

const store = useKnowledgeStore()

const TYPE_COLORS: Record<string, string> = {
  Concept: '#7C3AED', Algorithm: '#F59E0B', DataStructure: '#10B981',
  Protocol: '#3B82F6', Principle: '#EC4899', Term: '#94A3B8',
  Technology: '#06B6D4', Model: '#F97316',
}

const typeColor = computed(() => TYPE_COLORS[props.node.type] || '#94A3B8')
const masteryPercentage = computed(() => Math.round(Math.max(0, Math.min(1, props.node.mastery || 0)) * 100))
const canPractice = computed(() => props.courseId != null)

const relations = computed(() => {
  const edges = store.graphData?.edges ?? []
  return edges
    .filter(e => (
      (e.source === props.node.id || e.target === props.node.id)
      && (!props.relationNodeIds || (
        props.relationNodeIds.has(e.source) && props.relationNodeIds.has(e.target)
      ))
    ))
    .map(e => {
      const isOutgoing = e.source === props.node.id
      const otherId = isOutgoing ? e.target : e.source
      const otherNode = store.graphData?.nodes.find(n => n.id === otherId)
      return {
        source: e.source,
        target: e.target,
        name: e.relationship_name,
        direction: isOutgoing ? '→' : '←',
        targetName: otherNode?.name || otherId,
      }
    })
    .slice(0, 20)
})
</script>

<style scoped>
.detail-panel {
  position: absolute;
  right: 16px;
  top: 16px;
  width: 320px;
  max-height: calc(100vh - 200px);
  background: #1a1a2e;
  border: 1px solid #333;
  border-radius: 12px;
  overflow-y: auto;
  z-index: 100;
}
.panel-header {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 16px;
  border-bottom: 1px solid #2a2a3e;
}
.panel-header h3 { margin: 0; font-size: 16px; color: #F4F4F4; flex: 1; }
.close-btn { color: #94A3B8; }
.panel-body { padding: 16px; }
.description { font-size: 13px; color: #aaa; line-height: 1.6; margin: 0 0 16px; }
.mastery-section { margin: 0 0 18px; }
.mastery-heading { display: flex; justify-content: space-between; margin-bottom: 7px; color: #CBD5E1; font-size: 12px; }
.mastery-heading strong { color: #38BDF8; font-size: 16px; }
.section { margin-bottom: 16px; }
.section h4 { font-size: 12px; color: #94A3B8; text-transform: uppercase; margin: 0 0 8px; letter-spacing: 0.05em; }
.relation-item { display: flex; align-items: center; gap: 6px; padding: 6px 0; font-size: 13px; }
.rel-direction { color: #3B82F6; font-weight: bold; }
.rel-node { color: #F4F4F4; }
.rel-name { color: #94A3B8; font-size: 11px; margin-left: auto; }
.attr-item { display: flex; justify-content: space-between; padding: 4px 0; font-size: 13px; }
.attr-key { color: #94A3B8; }
.attr-value { color: #F4F4F4; }
.practice-section { margin-top: 20px; padding-top: 16px; border-top: 1px solid #2a2a3e; }
.practice-button { width: 100%; }
.practice-hint { margin: 8px 0 0; color: #94A3B8; font-size: 12px; line-height: 1.5; text-align: center; }
.slide-enter-active, .slide-leave-active { transition: all 0.3s ease; }
.slide-enter-from, .slide-leave-to { transform: translateX(100%); opacity: 0; }
</style>

<template>
  <transition name="slide">
    <div v-if="visible" class="subgraph-panel">
      <!-- Header -->
      <div class="panel-header">
        <div class="hit-node-info">
          <span class="hit-node-name">{{ currentHit?.nodeName || '' }}</span>
          <el-tag size="small" :color="typeColor" effect="dark" style="margin-left: 8px">
            {{ currentHit?.nodeType || '' }}
          </el-tag>
        </div>
        <div class="header-actions">
          <el-button
            v-if="subgraphs && !loading && !error"
            :icon="FullScreen"
            size="small"
            circle
            @click="fullscreenDialogVisible = true"
            class="fullscreen-btn"
            title="全屏查看"
          />
          <el-button
            :icon="Close"
            size="small"
            circle
            @click="$emit('close')"
            class="close-btn"
          />
        </div>
      </div>

      <!-- Loading state -->
      <div v-if="loading" class="panel-body">
        <el-skeleton :rows="6" animated />
      </div>

      <!-- Error state -->
      <div v-else-if="error" class="panel-body error-state">
        <el-icon :size="32" color="#f56c6c"><WarningFilled /></el-icon>
        <p>{{ error }}</p>
        <el-button size="small" @click="$emit('retry')">重试</el-button>
      </div>

      <!-- Subgraph content -->
      <div v-else-if="subgraphs" class="panel-body">
        <div v-if="hitNodes.length > 1" class="hit-pagination">
          <span class="page-caption">命中节点</span>
          <el-pagination
            small
            background
            layout="prev, pager, next"
            :current-page="activeIndex + 1"
            :page-size="1"
            :total="hitNodes.length"
            @current-change="(page: number) => $emit('select-page', page - 1)"
          />
        </div>
        <div class="chart-container">
          <SubgraphChart
            :nodes="subgraphs.nodes"
            :edges="subgraphs.edges"
            :hit-node-id="subgraphs.hitNode.id"
            @node-click="onNodeClick"
          />
        </div>

        <!-- Legend -->
        <div class="legend">
          <span class="legend-item"><span class="legend-dot hit-dot" />命中</span>
          <span class="legend-item"><span class="legend-dot upstream-dot" />前置</span>
          <span class="legend-item"><span class="legend-dot downstream-dot" />后继</span>
          <span class="legend-item"><span class="legend-dot both-dot" />双向</span>
        </div>

        <!-- Node detail -->
        <div v-if="selectedDetail" class="detail-section">
          <h4 class="section-title">{{ selectedDetail.name }}</h4>
          <el-tag size="small" effect="plain">{{ selectedDetail.type }}</el-tag>
          <p class="detail-desc">{{ selectedDetail.description }}</p>
          <p class="detail-meta">度数: {{ selectedDetail.degree }}</p>
        </div>
      </div>
    </div>
  </transition>

  <button
    v-if="!visible && hitNodes.length"
    class="subgraph-panel-toggle"
    type="button"
    title="展开知识图谱"
    @click="$emit('open')"
  >
    知识图谱 <span aria-hidden="true">‹</span>
  </button>

  <!-- 全屏模态框 -->
  <el-dialog
    v-model="fullscreenDialogVisible"
    fullscreen
    :show-close="false"
    class="subgraph-fullscreen-dialog"
    destroy-on-close
  >
    <div class="fullscreen-content">
      <!-- Header -->
      <div class="fullscreen-header">
        <div class="fullscreen-hit-info">
          <span class="fullscreen-hit-name">{{ currentHit?.nodeName || '' }}</span>
          <el-tag size="small" :color="typeColor" effect="dark" style="margin-left: 8px">
            {{ currentHit?.nodeType || '' }}
          </el-tag>
        </div>
        <el-button
          :icon="Close"
          size="small"
          circle
          @click="fullscreenDialogVisible = false"
          class="fullscreen-close-btn"
        />
      </div>

      <!-- Body: single centered chart -->
      <div v-if="subgraphs" class="fullscreen-body">
        <div class="fullscreen-chart-container">
          <SubgraphChart
            :nodes="subgraphs.nodes"
            :edges="subgraphs.edges"
            :hit-node-id="subgraphs.hitNode.id"
            :roam="true"
            :fullscreen="true"
            @node-click="onNodeClick"
          />
        </div>
      </div>

      <!-- Legend -->
      <div class="fullscreen-legend">
        <span class="legend-item"><span class="legend-dot hit-dot" />命中节点</span>
        <span class="legend-item"><span class="legend-dot upstream-dot" />前置知识（上游）</span>
        <span class="legend-item"><span class="legend-dot downstream-dot" />后继知识（下游）</span>
        <span class="legend-item"><span class="legend-dot both-dot" />双向关联</span>
      </div>

      <!-- Footer: 节点详情 -->
      <div v-if="selectedDetail" class="fullscreen-detail">
        <h4 class="fullscreen-section-title">{{ selectedDetail.name }}</h4>
        <el-tag size="small" effect="plain">{{ selectedDetail.type }}</el-tag>
        <p class="fullscreen-detail-desc">{{ selectedDetail.description }}</p>
        <p class="fullscreen-detail-meta">度数: {{ selectedDetail.degree }}</p>
      </div>
    </div>
  </el-dialog>
</template>

<script setup lang="ts">
import { ref, computed, watch } from 'vue'
import { Close, WarningFilled, FullScreen } from '@element-plus/icons-vue'
import SubgraphChart from '@/components/SubgraphChart.vue'
import type { SubgraphData, SubgraphNode } from '@/composables/useSubgraph'
import type { KgHitNode } from '@/composables/useChat'
import { TYPE_COLORS } from '@/constants/knowledgeColors'

const props = defineProps<{
  visible: boolean
  hitNodes: KgHitNode[]
  activeIndex: number
  subgraphs: SubgraphData | null
  loading: boolean
  error: string | null
}>()

defineEmits<{
  close: []
  open: []
  retry: []
  'select-page': [index: number]
}>()

const selectedDetail = ref<SubgraphNode | null>(null)
const fullscreenDialogVisible = ref(false)

const currentHit = computed(() => props.hitNodes[props.activeIndex])
const typeColor = computed(() => TYPE_COLORS[currentHit.value?.nodeType || ''] || '#94A3B8')

function onNodeClick(node: SubgraphNode) {
  selectedDetail.value = node
}

// Auto-select hit node when subgraphs arrive
watch(() => props.subgraphs, (sg) => {
  if (sg) {
    selectedDetail.value = sg.hitNode
  }
}, { immediate: true })
</script>

<style scoped>
.subgraph-panel {
  width: 35%;
  min-width: 280px;
  max-width: 420px;
  background: rgba(255, 255, 255, 0.95);
  backdrop-filter: blur(10px);
  border-left: 1px solid rgba(0, 0, 0, 0.08);
  display: flex;
  flex-direction: column;
  overflow-y: auto;
}

.slide-enter-active, .slide-leave-active {
  transition: transform 0.3s ease, opacity 0.3s ease;
  will-change: transform, opacity;
  overflow: hidden;
}
.slide-enter-from, .slide-leave-to {
  transform: translateX(100%);
  opacity: 0;
}

.panel-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 16px;
  border-bottom: 1px solid rgba(0, 0, 0, 0.06);
}

.hit-node-info {
  display: flex;
  align-items: center;
}

.header-actions {
  display: flex;
  gap: 4px;
  align-items: center;
}

.hit-node-name {
  font-size: 16px;
  font-weight: 600;
  color: #FF8C00;
}

.panel-body {
  flex: 1;
  display: flex;
  flex-direction: column;
  padding: 12px 16px;
  overflow-y: auto;
}

.hit-pagination {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  margin-bottom: 10px;
}
.page-caption { color: #64748b; font-size: 12px; white-space: nowrap; }

.subgraph-panel-toggle {
  align-self: center;
  padding: 10px 8px;
  border: 1px solid rgba(0, 0, 0, 0.08);
  border-right: 0;
  border-radius: 10px 0 0 10px;
  background: rgba(255, 255, 255, 0.95);
  color: #475569;
  box-shadow: -4px 4px 14px rgba(15, 23, 42, 0.08);
  cursor: pointer;
  font-size: 12px;
  writing-mode: vertical-rl;
}
.subgraph-panel-toggle span { font-size: 20px; line-height: 1; }

.error-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 8px;
  color: #f56c6c;
  text-align: center;
}

.chart-container {
  flex: 1;
  min-height: 300px;
  border: 1px solid rgba(0, 0, 0, 0.06);
  border-radius: 8px;
  background: rgba(0, 0, 0, 0.02);
}

/* Legend */
.legend {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
  padding: 8px 0;
  font-size: 12px;
  color: #6b7280;
}
.legend-item {
  display: flex;
  align-items: center;
  gap: 4px;
}
.legend-dot {
  width: 10px;
  height: 10px;
  border-radius: 50%;
  display: inline-block;
}
.hit-dot { background: #FF8C00; }
.upstream-dot { background: #7c3aed; }
.downstream-dot { background: #059669; }
.both-dot { background: #0ea5e9; }

.detail-section {
  margin-top: 8px;
  padding: 12px;
  background: rgba(0, 0, 0, 0.03);
  border-radius: 8px;
}

.section-title {
  font-size: 13px;
  font-weight: 600;
  color: #374151;
  margin: 0 0 8px 0;
}

.detail-desc {
  font-size: 13px;
  color: #4b5563;
  margin: 8px 0 4px;
  line-height: 1.5;
}

.detail-meta {
  font-size: 12px;
  color: #9ca3af;
  margin: 0;
}

/* 全屏模态框样式 */
.fullscreen-content {
  display: flex;
  flex-direction: column;
  height: 100vh;
  background: #1a1a2e;
  color: #e0e0e0;
  padding: 16px 24px;
}

.fullscreen-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding-bottom: 16px;
  border-bottom: 1px solid rgba(255, 255, 255, 0.1);
}

.fullscreen-hit-info {
  display: flex;
  align-items: center;
}

.fullscreen-hit-name {
  font-size: 20px;
  font-weight: 700;
  color: #FF8C00;
}

.fullscreen-close-btn {
  color: #e0e0e0;
}

.fullscreen-body {
  flex: 1;
  display: flex;
  padding: 16px 0;
  min-height: 0;
}

.fullscreen-chart-container {
  flex: 1;
  border: 1px solid rgba(255, 255, 255, 0.1);
  border-radius: 12px;
  background: rgba(255, 255, 255, 0.05);
  min-height: 400px;
}

.fullscreen-section-title {
  font-size: 15px;
  font-weight: 600;
  color: #e0e0e0;
  margin: 0 0 12px 0;
}

.fullscreen-legend {
  display: flex;
  gap: 20px;
  padding: 10px 0;
  font-size: 13px;
  color: #a0a0a0;
  justify-content: center;
}

.fullscreen-detail {
  padding: 16px;
  background: rgba(255, 255, 255, 0.08);
  border-radius: 12px;
  margin-top: 12px;
}

.fullscreen-detail-desc {
  font-size: 14px;
  color: #b0b0b0;
  margin: 8px 0 4px;
  line-height: 1.6;
}

.fullscreen-detail-meta {
  font-size: 12px;
  color: #787878;
  margin: 0;
}
</style>

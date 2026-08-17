<template>
  <BorderGlow class="kg-page" background-color="transparent">
    <!-- 图谱选择器 - 在黑色大框上方 -->
    <div class="kg-header">
      <el-select
        v-model="selectedGraphId"
        placeholder="选择图谱"
        size="default"
        style="width: 260px"
        @change="onGraphSelect"
      >
        <el-option
          v-for="g in store.graphList"
          :key="g.id"
          :label="g.original_filename"
          :value="g.id"
        >
          <span>{{ g.original_filename }}</span>
          <span v-if="g.status === 'failed'" class="graph-status-tag">失败</span>
          <span v-else-if="g.status === 'pending'" class="graph-status-tag pending">构建中</span>
        </el-option>
      </el-select>
      <StarBorder as="div" color="#f56c6c" speed="3s">
        <el-button
          v-if="selectedGraphId"
          type="danger"
          plain
          size="small"
          :icon="Delete"
          @click="handleDelete"
        >
          删除
        </el-button>
      </StarBorder>
    </div>

    <!-- 图谱主体 -->
    <div class="kg-container">
      <!-- 加载状态 -->
      <div v-if="store.loading" class="kg-state">
        <el-skeleton :rows="5" animated />
        <p class="state-text">正在加载知识图谱...</p>
      </div>

      <!-- 错误状态 -->
      <div v-else-if="store.error" class="kg-state">
        <el-result
          icon="error"
          :title="store.error.type === 'network' ? '网络错误' : '加载失败'"
          :sub-title="store.error.message"
        >
          <template #extra>
            <StarBorder as="div" color="#409eff" speed="4s">
              <el-button type="primary" @click="store.loadGraphData(store.currentGraphName || undefined)">重试</el-button>
            </StarBorder>
          </template>
        </el-result>
      </div>

      <!-- 空状态 -->
      <div v-else-if="store.isEmpty" class="kg-state">
        <el-empty description="还没有构建知识图谱">
          <template #image>
            <div class="empty-graph-icon">🔍</div>
          </template>
          <StarBorder as="div" color="#409eff" speed="5s">
            <el-button type="primary" @click="$router.push('/student/kg-pipeline')">
              上传文档构建知识图谱
            </el-button>
          </StarBorder>
        </el-empty>
      </div>

      <!-- 图谱视图 -->
      <template v-else-if="store.graphData">
        <div class="kg-toolbar">
          <div class="chapter-selector">
            <el-cascader
              v-model="chapterPathIds"
              :options="chapterOptions"
              :props="chapterSelectorProps"
              clearable
              filterable
              size="small"
              placeholder="选择章 / 节"
              @change="onChapterPathChange"
            />
          </div>
          <div class="kg-search-wrapper">
            <el-autocomplete
              v-model="store.searchQuery"
              :fetch-suggestions="querySearch"
              placeholder="搜索实体..."
              :prefix-icon="Search"
              clearable
              size="small"
              @select="onSearchSelect"
            />
          </div>
          <div class="kg-controls">
            <span v-if="drillPath.length" class="current-scope-summary">{{ currentScopeSummary }}</span>
            <el-tooltip content="单击查看详情；双击章/节进入下一级；知识点不再展开局部图">
              <el-tag type="info" plain size="small">双击钻取</el-tag>
            </el-tooltip>
            <el-switch v-model="showLabels" active-text="标签" size="small" />
            <el-button-group size="small">
              <el-button :icon="ZoomIn" @click="zoomIn" />
              <el-button :icon="ZoomOut" @click="zoomOut" />
              <el-button :icon="Refresh" @click="resetView" />
            </el-button-group>
          </div>
        </div>

        <!-- 面包屑导航 -->
        <div v-if="drillPath.length > 0" class="kg-breadcrumb">
          <span class="breadcrumb-item" @click="drillPath = []">全部章节</span>
          <template v-for="(node, idx) in drillPath" :key="node.id">
            <span class="breadcrumb-sep">&gt;</span>
            <span
              class="breadcrumb-item"
              :class="{ active: idx === drillPath.length - 1 }"
              @click="drillPath = drillPath.slice(0, idx + 1)"
            >
              {{ node.name }}
            </span>
          </template>
        </div>

        <!-- 图例 -->
        <div class="kg-legend">
          <template v-if="isKnowledgePointLevel">
            <div
              v-for="(color, type) in TYPE_COLORS"
              :key="type"
              class="legend-item"
              style="cursor: default"
            >
              <span class="legend-dot" :style="{ background: color }" />
              <span class="legend-label">{{ type }}</span>
            </div>
            <div class="legend-item relation-legend-item">
              <span class="relation-line dependency-line" />
              <span class="legend-label">依赖 / 前提</span>
            </div>
            <div class="legend-item relation-legend-item">
              <span class="relation-line semantic-line" />
              <span class="legend-label">其他关系（按类型着色）</span>
            </div>
          </template>
          <template v-else>
            <div class="legend-item" style="cursor: default">
              <span class="legend-dot" :style="{ background: '#6366F1' }" />
              <span class="legend-label">Chapter</span>
            </div>
          </template>
        </div>

        <!-- 图容器 + 详情面板 -->
        <div class="kg-chart-wrapper">
          <KnowledgeGraph2D
            ref="graphRef2D"
            :data="currentGraphData!"
            :show-labels="showLabels"
            :show-mastery-wave="isKnowledgePointLevel"
            @node-click="handleNodeClick"
            @node-dbl-click="handleNodeDoubleClick"
          />
          <GraphDetailPanel
            v-if="store.selectedNode"
            :node="store.selectedNode"
            :relation-node-ids="visibleRelationNodeIds"
            :course-id="currentCourseId"
            @close="store.selectNode(null)"
            @practice="goToNodePractice"
          />
          <!-- 知识点层空状态 -->
          <div
            v-if="isKnowledgePointLevel && currentGraphData && currentGraphData.nodes.length === 0"
            class="kg-empty-overlay"
          >
            <div class="kg-empty-text">
              <span class="empty-icon">📭</span>
              <p>该节暂无知识点</p>
            </div>
          </div>
        </div>
      </template>
    </div>
  </BorderGlow>
</template>

<script setup lang="ts">
import { ref, computed, watch, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { Search, ZoomIn, ZoomOut, Refresh, Delete } from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { useKnowledgeStore } from '@/stores/knowledge'
import KnowledgeGraph2D from '@/components/KnowledgeGraph2D.vue'
import GraphDetailPanel from '@/components/GraphDetailPanel.vue'
import { useGraph } from '@/composables/useGraph'
import StarBorder from '@/components/StarBorder.vue'
import BorderGlow from '@/components/BorderGlow.vue'

import { parseHierarchy, getVisibleData, tryDrillInto } from '@/utils/kgHierarchy'
import type { GraphNode, GraphData } from '@/api/knowledge'
import { fetchMasteryHierarchy } from '@/api/learning'

const route = useRoute()
const $router = useRouter()
const store = useKnowledgeStore()
const graphRef2D = ref<InstanceType<typeof KnowledgeGraph2D>>()
const { showLabels, handleSearch } = useGraph()
const selectedGraphId = ref<number | null>(null)
const currentCourseId = computed(() => (
  store.graphList.find(graph => graph.id === selectedGraphId.value)?.course_id ?? null
))

// 掌握度映射：节点名 → 掌握度(0~1)，用于节点球"装水"可视化
const masteryMap = ref<Record<string, number>>({})
// 进度映射：节点名 → 进度(0~1)，用于章节/小节节点显示进度百分比
const processMap = ref<Record<string, number>>({})

// 根据当前图谱的 course_id 加载掌握度层级树，并构建 节点名→掌握度 映射
async function loadMastery() {
  masteryMap.value = {}
  processMap.value = {}
  const graph = store.graphList.find(g => g.id === selectedGraphId.value)
  if (!graph || graph.course_id == null) return
  try {
    const hierarchy = await fetchMasteryHierarchy(graph.course_id)
    const mMap: Record<string, number> = {}
    const pMap: Record<string, number> = {}
    for (const chapter of hierarchy.chapters) {
      mMap[chapter.name] = Math.max(0, Math.min(1, chapter.degree / 5))
      pMap[chapter.name] = Math.max(0, Math.min(1, (chapter.process ?? 0) / 100))
      for (const section of chapter.sections) {
        mMap[section.name] = Math.max(0, Math.min(1, section.degree / 5))
        pMap[section.name] = Math.max(0, Math.min(1, (section.process ?? 0) / 100))
        for (const kp of section.knowledge_points) {
          mMap[kp.name] = Math.max(0, Math.min(1, kp.degree / 5))
        }
      }
      for (const kp of chapter.knowledge_points) {
        mMap[kp.name] = Math.max(0, Math.min(1, kp.degree / 5))
      }
    }
    masteryMap.value = mMap
    processMap.value = pMap
  } catch (e) {
    console.error('加载掌握度失败:', e)
    masteryMap.value = {}
    processMap.value = {}
  }
}

// 钻取状态
const drillPath = ref<GraphNode[]>([])
const chapterPathIds = ref<string[]>([])
const chapterSelectorProps = {
  checkStrictly: true,
  emitPath: true,
  value: 'value',
  label: 'label',
  children: 'children',
}

// 钻取路径改变时回到本层完整视图。
watch(drillPath, () => {
  chapterPathIds.value = drillPath.value.map(node => node.id)
  store.selectNode(null)
})

const TYPE_COLORS: Record<string, string> = {
  Concept: '#7C3AED', Algorithm: '#F59E0B', DataStructure: '#10B981',
  Protocol: '#3B82F6', Principle: '#EC4899', Term: '#94A3B8',
  Technology: '#06B6D4', Model: '#F97316',
}

// 层级结构（依赖 store.graphData）
const hierarchy = computed(() => {
  if (!store.graphData) return null
  return parseHierarchy(store.graphData)
})

interface ChapterOption {
  value: string
  label: string
  children?: ChapterOption[]
}

const chapterOptions = computed<ChapterOption[]>(() => {
  if (!hierarchy.value) return []
  const buildOption = (node: GraphNode, visited: Set<string>): ChapterOption => {
    if (visited.has(node.id)) return { value: node.id, label: node.name }
    const nextVisited = new Set(visited).add(node.id)
    const children = (hierarchy.value?.chapterChildren.get(node.id) || [])
      .map(child => buildOption(child, nextVisited))
    return {
      value: node.id,
      label: node.name,
      ...(children.length ? { children } : {}),
    }
  }
  return hierarchy.value.topLevelChapters.map(node => buildOption(node, new Set()))
})

function onChapterPathChange(value: string[] | string | null) {
  if (!hierarchy.value || !Array.isArray(value) || value.length === 0) {
    drillPath.value = []
    return
  }
  drillPath.value = value
    .map(id => hierarchy.value?.nodeMap.get(id))
    .filter((node): node is GraphNode => Boolean(node))
}

// 当前层级应展示的图谱数据。进入具体小节后切换为“知识点掌握度 + 关系”视图。
const currentGraphData = computed<GraphData | null>(() => {
  if (!store.graphData || !hierarchy.value) return store.graphData
  const base = getVisibleData(store.graphData, drillPath.value, hierarchy.value)
  const projectedBase = base

  // 注入掌握度与进度（节点名 → 0~1），用于节点可视化
  const injectMastery = (nodes: GraphNode[]) =>
    nodes.map(n => ({
      ...n,
      mastery: masteryMap.value[n.name] ?? 0,
      progress: processMap.value[n.name] ?? 0,
    }))

  const currentChapter = drillPath.value[drillPath.value.length - 1]
  const isSectionView = drillPath.value.length >= 2
    || (drillPath.value.length === 1
      && (hierarchy.value.chapterChildren.get(currentChapter?.id || '')?.length || 0) === 0)

  if (isSectionView) {
    const nodes = injectMastery(projectedBase.nodes).filter(node => node.type !== 'Chapter')
    const nodeIds = new Set(nodes.map(node => node.id))
    const edges = projectedBase.edges.filter(edge => (
      nodeIds.has(edge.source)
      && nodeIds.has(edge.target)
    ))
    const nodeTypes: Record<string, number> = {}
    for (const node of nodes) nodeTypes[node.type] = (nodeTypes[node.type] || 0) + 1
    return {
      nodes,
      edges,
      stats: {
        total_nodes: nodes.length,
        total_edges: edges.length,
        node_types: nodeTypes,
      },
    }
  }

  return {
    ...projectedBase,
    nodes: injectMastery(projectedBase.nodes),
  }
})

const currentScopeSummary = computed(() => {
  const data = currentGraphData.value
  if (!data) return ''
  const knowledgeCount = data.nodes.filter(node => node.type !== 'Chapter').length
  if (isKnowledgePointLevel.value) {
    const connectedIds = new Set<string>()
    for (const edge of data.edges) {
      connectedIds.add(edge.source)
      connectedIds.add(edge.target)
    }
    const isolatedCount = data.nodes.filter(node => !connectedIds.has(node.id)).length
    const dependencyCount = data.edges.filter(edge => (
      edge.relationship_name === '依赖' || edge.relationship_name === '前提'
    )).length
    const semanticCount = data.edges.length - dependencyCount
    return `本节 ${knowledgeCount} 个知识点 · 前置/后置 ${dependencyCount} 条 · 其他关系 ${semanticCount} 条${isolatedCount ? ` · ${isolatedCount} 个节点暂无直接关系` : ''}`
  }
  return `${data.nodes.filter(node => node.type === 'Chapter').length} 个下级章节`
})

const visibleRelationNodeIds = computed(() => new Set(
  (currentGraphData.value?.nodes ?? []).map(node => node.id),
))

// 是否在知识点层（控制图例和类型筛选）
const isKnowledgePointLevel = computed(() => {
  if (drillPath.value.length === 0) return false
  const currentChapter = drillPath.value[drillPath.value.length - 1]
  const subSections = hierarchy.value?.chapterChildren.get(currentChapter.id)
  // 知识点层：进入任意具体小节（支持更深层级）或无子节的章节。
  return drillPath.value.length >= 2 || (drillPath.value.length === 1 && (subSections?.length || 0) === 0)
})

function handleNodeClick(node: GraphNode) {
  // 与教师端一致：单击只负责选中并查看详情。
  store.selectNode(node)
}

function handleNodeDoubleClick(node: GraphNode) {
  if (!hierarchy.value) return
  if (node.type === 'Chapter') {
    const newPath = tryDrillInto(node, drillPath.value, hierarchy.value)
    if (newPath !== null) drillPath.value = newPath
    store.selectNode(null)
    return
  }
  store.selectNode(node)
}

function goToNodePractice() {
  const node = store.selectedNode
  const courseId = currentCourseId.value
  if (!node || courseId == null) {
    ElMessage.warning('当前节点暂无对应题目合集')
    return
  }

  $router.push({
    path: '/student/practice/panel',
    query: {
      module: String(courseId),
      kgNodeName: node.name,
    },
  })
}

function querySearch(query: string, cb: (results: any[]) => void) {
  if (!query.trim()) return cb([])
  handleSearch(query).then(() => {
    const data = currentGraphData.value
    const results = (data?.nodes ?? [])
      .filter((n: { name: string }) => n.name.toLowerCase().includes(query.toLowerCase()))
      .slice(0, 10)
      .map((n: { name: string; id: string }) => ({ value: n.name, nodeId: n.id }))
    cb(results)
  })
}

function onSearchSelect(item: { value: string; nodeId: string }) {
  const data = currentGraphData.value
  const node = data?.nodes.find((n: { id: string }) => n.id === item.nodeId)
  if (node) {
    handleNodeClick(node)
  }
}

function zoomIn() {
  graphRef2D.value?.zoomIn()
}

function zoomOut() {
  graphRef2D.value?.zoomOut()
}

function resetView() {
  graphRef2D.value?.resetView()
}

function onGraphSelect(graphId: number) {
  drillPath.value = []  // 切换图谱时重置钻取路径
  const graph = store.graphList.find(g => g.id === graphId)
  if (graph && graph.status === 'completed') {
    $router.push({ query: { graphId } })
  }
  loadMastery()
}

async function handleDelete() {
  if (!selectedGraphId.value) return
  const graph = store.graphList.find(g => g.id === selectedGraphId.value)
  if (!graph) return
  try {
    await ElMessageBox.confirm(
      `确定要删除图谱"${graph.original_filename}"吗？此操作不可恢复。`,
      '确认删除',
      { confirmButtonText: '删除', cancelButtonText: '取消', type: 'warning' }
    )
    await store.deleteKgGraph(graph.id, graph.graph_name)
    ElMessage.success('图谱已删除')
    selectedGraphId.value = null
  } catch {
    // 用户取消
  }
}

async function loadGraphByRoute() {
  // 优先处理学科跳转：module 为学科（course_id），通过 kg_graphs.course_id 找到对应图谱
  const moduleId = route.query.module ? Number(route.query.module) : null
  if (moduleId) {
    await selectGraphByCourse(moduleId)
    return
  }

  const graphId = route.query.graphId ? Number(route.query.graphId) : null
  if (graphId) {
    store.currentGraphId = graphId
    selectedGraphId.value = graphId
    const graph = store.graphList.find(g => g.id === graphId)
    if (graph && graph.status === 'completed') {
      await store.loadGraphData(graph.graph_name)
    } else if (graph && graph.status === 'failed') {
      store.error = { type: 'not_found', message: '该图谱构建失败，请重新上传文档' }
    } else {
      store.error = { type: 'not_found', message: '该图谱还没有构建完成' }
    }
  } else {
    const recentCompleted = store.graphList.find(g => g.status === 'completed')
    if (recentCompleted) {
      store.currentGraphId = recentCompleted.id
      selectedGraphId.value = recentCompleted.id
      await store.loadGraphData(recentCompleted.graph_name)
    } else {
      const recent = store.graphList[0]
      if (recent) {
        store.currentGraphId = recent.id
        selectedGraphId.value = recent.id
        if (recent.status === 'completed') {
          await store.loadGraphData(recent.graph_name)
        } else if (recent.status === 'failed') {
          store.error = { type: 'not_found', message: '该图谱构建失败，请重新上传文档' }
        }
      }
    }
  }
}

/**
 * 根据学科（course_id）选择对应知识图谱。
 * 通过 kg_graphs.course_id 建立 学科 → 图谱 的映射关系。
 */
async function selectGraphByCourse(courseId: number) {
  const graph = store.graphList.find(g => g.course_id === courseId)
  if (!graph) {
    store.error = { type: 'not_found', message: '该学科还没有绑定知识图谱，请先上传文档构建' }
    return
  }

  store.currentGraphId = graph.id
  selectedGraphId.value = graph.id
  if (graph.status === 'completed') {
    await store.loadGraphData(graph.graph_name)
  } else if (graph.status === 'failed') {
    store.error = { type: 'not_found', message: '该图谱构建失败，请重新上传文档' }
  } else {
    store.error = { type: 'not_found', message: '该图谱还没有构建完成' }
  }
}

watch(() => [route.query.graphId, route.query.module], () => {
  drillPath.value = []
  loadGraphByRoute()
  loadMastery()
})

onMounted(async () => {
  await store.loadGraphList()
  drillPath.value = []
  await loadGraphByRoute()
  await loadMastery()
})
</script>

<style scoped>
:deep(.el-empty__description p) { color: #080808; }
:deep(.el-result__title p) { color: #1f2937; }
:deep(.el-result__subtitle p) { color: #6b7280; }
:deep(.el-select__wrapper) { background: rgba(255, 255, 255, 0.5); border-color: rgba(0, 0, 0, 0.1); color: #1f2937; }
:deep(.el-input__inner) { color: #1f2937; }
.kg-page {
  height: calc(100vh - 170px);
  margin: 16px;
}
.kg-header {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 0 4px;
  margin-bottom: 12px;
}
.graph-status-tag {
  color: #f56c6c;
  margin-left: 8px;
  font-size: 12px;
}
.graph-status-tag.pending {
  color: #e6a23c;
}
.kg-container {
  display: flex;
  flex-direction: column;
  flex: 1;
  background: rgba(255, 255, 255, 0.4);
  backdrop-filter: blur(10px);
  border-radius: 12px;
  overflow: hidden;
}
.kg-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  height: 100%;
  padding: 48px;
}
.state-text {
  color: #4b5563;
  margin-top: 16px;
  font-size: 14px;
}
.kg-toolbar {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 16px;
  padding: 12px 20px;
  background: rgba(255, 255, 255, 0.5);
  backdrop-filter: blur(8px);
  border-bottom: 1px solid rgba(0, 0, 0, 0.05);
}
.kg-stats {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 12px;
  color: #4b5563;
  font-variant-numeric: tabular-nums;
}
.chapter-selector {
  width: 300px;
  flex-shrink: 0;
}
.chapter-selector :deep(.el-cascader) {
  width: 100%;
}
.current-scope-summary {
  color: #475569;
  font-size: 12px;
  white-space: nowrap;
}
.stat-divider { width: 1px; height: 16px; background: #d1d5db; }
.kg-search-wrapper { flex: 1; max-width: 320px; }
.kg-controls { display: flex; align-items: center; justify-content: flex-end; flex-wrap: wrap; gap: 12px; }
.projection-modes { flex-shrink: 0; }
.kg-legend {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
  padding: 8px 20px;
  background: rgba(255, 255, 255, 0.5);
  backdrop-filter: blur(8px);
  border-bottom: 1px solid rgba(0, 0, 0, 0.05);
}
.legend-item {
  display: flex;
  align-items: center;
  gap: 4px;
  padding: 2px 8px;
  border-radius: 4px;
  cursor: pointer;
  font-size: 11px;
  color: #4b5563;
  transition: all 0.2s;
}
.legend-item:hover { background: rgba(0,0,0,0.05); }
.legend-item.inactive { opacity: 0.4; }
.legend-dot { width: 8px; height: 8px; border-radius: 50%; }
.relation-line { width: 20px; height: 2px; border-radius: 2px; }
.dependency-line { background: #38BDF8; box-shadow: 0 0 6px #38BDF8; }
.semantic-line { background: #A78BFA; box-shadow: 0 0 6px #A78BFA; }
.kg-chart-wrapper {
  flex: 1;
  position: relative;
  overflow: hidden;
}
.kg-breadcrumb {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 8px 20px;
  background: rgba(15, 15, 15, 0.85);
  backdrop-filter: blur(8px);
  border-bottom: 1px solid rgba(255, 255, 255, 0.05);
  font-size: 13px;
}
.breadcrumb-item {
  color: #94A3B8;
  cursor: pointer;
  transition: color 0.2s;
  max-width: 240px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.breadcrumb-item:hover {
  color: #F4F4F4;
}
.breadcrumb-item.active {
  color: #F4F4F4;
  font-weight: 600;
}
.breadcrumb-sep {
  color: #555;
  font-size: 11px;
}

.kg-empty-overlay {
  position: absolute;
  inset: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  background: rgba(15, 15, 15, 0.6);
  backdrop-filter: blur(2px);
  z-index: 50;
  pointer-events: none;
}
.kg-empty-text {
  text-align: center;
  color: #94A3B8;
}
.kg-empty-text .empty-icon {
  font-size: 40px;
  display: block;
  margin-bottom: 8px;
}
.kg-empty-text p {
  margin: 0;
  font-size: 14px;
}
</style>
